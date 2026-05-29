import aiohttp
import asyncio
import os
from dotenv import load_dotenv
from decorators import cache, timer, retry
from logger import get_logger

load_dotenv()

logger = get_logger(__name__)

# Ключи из .env
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "trilogy")
RAWG_API_KEY = os.getenv("RAWG_API_KEY", "free")

JIKAN_URL = "https://api.jikan.moe/v4/anime"
OMDB_URL  = "https://www.omdbapi.com/"
RAWG_URL  = "https://api.rawg.io/api/games"

PAGE_SIZE = 5  # результатов на страницу


# парсеры ответов

def parse_anime(data: dict) -> list[dict]:
    results = []
    for item in data.get("data", []):
        results.append({
            "title":  item.get("title_english") or item.get("title", "—"),
            "year":   str(item.get("year") or "—"),
            "score":  str(item.get("score") or "—"),
            "status": item.get("status", "—"),
            "genres": ", ".join(g["name"] for g in item.get("genres", [])),
            "source": "Аниме (MyAnimeList)",
        })
    return results


def parse_movies(data: dict) -> list[dict]:
    results = []
    for item in data.get("Search", []):
        results.append({
            "title":  item.get("Title", "—"),
            "year":   item.get("Year", "—"),
            "score":  "—",
            "status": item.get("Type", "—"),
            "genres": "—",
            "source": "Фильмы (OMDB)",
        })
    return results


def parse_games(data: dict) -> list[dict]:
    results = []
    for item in data.get("results", []):
        genres = ", ".join(g["name"] for g in item.get("genres", []))
        results.append({
            "title":  item.get("name", "—"),
            "year":   (item.get("released") or "—")[:4],
            "score":  str(item.get("rating") or "—"),
            "status": "game",
            "genres": genres,
            "source": "Игры (RAWG)",
        })
    return results


# Запросы к API

@retry(attempts=3, delay=1.0)
@cache(ttl=300)
async def search_anime(
    query: str,
    session: aiohttp.ClientSession,
    page: int = 1,
    genre: str = "",
    year: str = "",
) -> list[dict]:
    """Поиск аниме через Jikan API"""
    params = {"q": query, "limit": PAGE_SIZE, "page": page}
    if year:
        params["start_date"] = f"{year}-01-01"
        params["end_date"]   = f"{year}-12-31"
    logger.debug("Jikan запрос: query=%s page=%s year=%s", query, page, year)
    async with session.get(JIKAN_URL, params=params) as resp:
        resp.raise_for_status()
        data = await resp.json()
    results = parse_anime(data)
    # Фильтр по жанру делаем на нашей стороне — Jikan принимает genre_id,
    # а не название, поэтому проще отфильтровать уже распарсенный список
    if genre:
        results = [r for r in results if genre.lower() in r["genres"].lower()]
    logger.info("Jikan вернул %d результатов для '%s'", len(results), query)
    return results


@retry(attempts=3, delay=1.0)
@cache(ttl=300)
async def search_movies(
    query: str,
    session: aiohttp.ClientSession,
    page: int = 1,
    genre: str = "",
    year: str = "",
) -> list[dict]:
    """Поиск фильмов через OMDB API."""
    params = {"s": query, "apikey": OMDB_API_KEY, "page": page}
    if year:
        params["y"] = year
    logger.debug("OMDB запрос: query=%s page=%s year=%s", query, page, year)
    async with session.get(OMDB_URL, params=params) as resp:
        resp.raise_for_status()
        data = await resp.json()
    results = parse_movies(data)
    logger.info("OMDB вернул %d результатов для '%s'", len(results), query)
    return results


@retry(attempts=3, delay=1.0)
@cache(ttl=300)
async def search_games(
    query: str,
    session: aiohttp.ClientSession,
    page: int = 1,
    genre: str = "",
    year: str = "",
) -> list[dict]:
    """Поиск игр через RAWG API."""
    params = {
        "search": query,
        "key": RAWG_API_KEY,
        "page_size": PAGE_SIZE,
        "page": page,
    }
    if genre:
        params["genres"] = genre.lower()
    if year:
        params["dates"] = f"{year}-01-01,{year}-12-31"
    logger.debug("RAWG запрос: query=%s page=%s genre=%s year=%s", query, page, genre, year)
    async with session.get(RAWG_URL, params=params) as resp:
        resp.raise_for_status()
        data = await resp.json()
    results = parse_games(data)
    logger.info("RAWG вернул %d результатов для '%s'", len(results), query)
    return results


@timer
async def search_all(
    query: str,
    page: int = 1,
    genre: str = "",
    year: str = "",
) -> dict[str, list[dict]]:
    """
    Параллельный поиск по всем трём источникам через asyncio.gather.
    """
    logger.debug("search_all: query='%s' page=%d genre='%s' year='%s'", query, page, genre, year)
    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            search_anime(query, session, page, genre, year),
            search_movies(query, session, page, genre, year),
            search_games(query, session, page, genre, year),
            return_exceptions=True,
        )

    for i, r in enumerate(results):
        if isinstance(r, Exception):
            logger.error("Ошибка в источнике %d: %s", i, r)

    return {
        "anime":  results[0] if not isinstance(results[0], Exception) else [],
        "movies": results[1] if not isinstance(results[1], Exception) else [],
        "games":  results[2] if not isinstance(results[2], Exception) else [],
    }
