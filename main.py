import asyncio
import sys
import os
from db import (init_db, add_to_history, get_history, clear_history,
                add_to_favorites, get_favorites, remove_from_favorites,
                export_favorites_csv, get_history_stats)
from api import search_all
from logger import get_logger

logger = get_logger(__name__)

# ─── Цвета для консоли (ANSI) ─────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
DIM    = "\033[2m"
MAGENTA = "\033[95m"

def color(text: str, c: str) -> str:
    return f"{c}{text}{RESET}"

def header(text: str):
    print(f"\n{BOLD}{CYAN}{'─' * 52}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 52}{RESET}\n")

def print_result(index: int, item: dict):
    print(f"  {color(f'[{index}]', YELLOW)} {color(item['title'], BOLD)}")
    print(f"      Год: {item['year']}  |  Оценка: {item['score']}")
    if item["genres"] != "—":
        print(f"      Жанры: {color(item['genres'], DIM)}")
    print(f"      Источник: {color(item['source'], GREEN)}")
    print()

def print_menu():
    header("ПОИСК ФИЛЬМОВ / АНИМЕ / ИГР")
    print(f"  {color('1', YELLOW)} — Поиск")
    print(f"  {color('2', YELLOW)} — История поиска")
    print(f"  {color('3', YELLOW)} — Избранное")
    print(f"  {color('4', YELLOW)} — Статистика")
    print(f"  {color('5', YELLOW)} — Экспорт избранного в CSV")
    print(f"  {color('6', YELLOW)} — Очистить историю")
    print(f"  {color('0', RED)}   — Выход\n")


# ─── Сценарий поиска ──────────────────────────────────────────────────────────

async def do_search():
    query = input(f"\n  {color('Введите запрос:', CYAN)} ").strip()
    if not query:
        print(color("  Запрос не может быть пустым.", RED))
        return

    # Фильтры
    print(f"  {color('Фильтры (Enter — пропустить):', DIM)}")
    genre = input(f"  Жанр (например: action, comedy, rpg): ").strip()
    year  = input(f"  Год выпуска (например: 2020): ").strip()

    page = 1
    last_query_args = (query, genre, year)  # запомним чтобы не спрашивать снова при "ещё"

    while True:
        print(color(f"\n  Ищем по всем источникам параллельно... (стр. {page})\n", DIM))
        logger.info("Поиск: query='%s' genre='%s' year='%s' page=%d", query, genre, year, page)

        results = await search_all(query, page=page, genre=genre, year=year)

        sources = ", ".join(k for k, v in results.items() if v)
        if sources and page == 1:
            add_to_history(query, sources)

        all_items: list[dict] = []
        for category, items in results.items():
            label = {"anime": "🎌 Аниме", "movies": "🎬 Фильмы", "games": "🎮 Игры"}[category]
            if items:
                header(label)
                for item in items:
                    all_items.append(item)
                    print_result(len(all_items), item)
            else:
                print(color(f"  Нет результатов в категории «{label}».\n", DIM))

        if not all_items:
            print(color("  Ничего не найдено ни в одном источнике.", RED))
            return

        # Навигация
        print(f"  {color('[f]', YELLOW)} добавить в избранное  "
              f"{color('[n]', YELLOW)} следующая страница  "
              f"{color('[q]', YELLOW)} назад в меню")
        nav = input(f"\n  {color('Действие:', CYAN)} ").strip().lower()

        if nav == "n":
            page += 1
            continue
        elif nav == "f":
            _add_to_fav(all_items)
        # любой другой ввод — выход из цикла
        break


def _add_to_fav(all_items: list[dict]):
    choice = input("  Введите номер результата для добавления в избранное: ").strip()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(all_items):
            item = all_items[idx]
            add_to_favorites(
                item["title"], item["source"],
                f"Год: {item['year']}, Оценка: {item['score']}"
            )
            logger.info("Добавлено в избранное: %s", item['title'])
            print(color(f"\n  ✓ «{item['title']}» добавлено в избранное!", GREEN))
        else:
            print(color("  Неверный номер.", RED))
    else:
        print(color("  Отменено.", DIM))


# ─── История ──────────────────────────────────────────────────────────────────

def show_history():
    header("📋 История поиска")
    rows = get_history()
    if not rows:
        print(color("  История пуста.\n", DIM))
        return
    for row in rows:
        print(f"  {color(row['searched_at'], DIM)}  "
              f"{color(row['query'], BOLD)}  "
              f"{color('(' + row['source'] + ')', DIM)}")
    print()


# ─── Избранное ────────────────────────────────────────────────────────────────

def show_favorites():
    header("⭐ Избранное")
    rows = get_favorites()
    if not rows:
        print(color("  Избранное пусто.\n", DIM))
        return
    for row in rows:
        print(f"  {color(f'[{row[\"id\"]}]', YELLOW)} {color(row['title'], BOLD)}")
        print(f"      {row['source']}  |  {row['extra_info']}")
        print(f"      Добавлено: {color(row['added_at'], DIM)}\n")

    choice = input("  Введите id записи для удаления (или Enter — назад): ").strip()
    if choice.isdigit():
        remove_from_favorites(int(choice))
        print(color("  ✓ Запись удалена.", GREEN))


# ─── Статистика ───────────────────────────────────────────────────────────────

def show_stats():
    header("📊 Статистика поиска")
    stats = get_history_stats()
    print(f"  Всего запросов: {color(str(stats['total']), BOLD)}\n")

    if stats["top_queries"]:
        print(f"  {color('Топ запросов:', CYAN)}")
        for row in stats["top_queries"]:
            bar = "█" * row["cnt"]
            print(f"    {color(row['query'], BOLD):30s} {color(bar, YELLOW)} {row['cnt']}")
        print()

    if stats["by_source"]:
        print(f"  {color('По источникам:', CYAN)}")
        for row in stats["by_source"]:
            print(f"    {row['source']:20s} — {color(str(row['cnt']), YELLOW)} раз")
    print()


# ─── Экспорт в CSV ────────────────────────────────────────────────────────────

def do_export():
    path = os.path.join(os.path.dirname(__file__), "favorites.csv")
    count = export_favorites_csv(path)
    if count == 0:
        print(color("\n  Избранное пусто, экспортировать нечего.\n", DIM))
    else:
        logger.info("Экспортировано %d записей в %s", count, path)
        print(color(f"\n  ✓ Экспортировано {count} записей → {path}\n", GREEN))


# ─── Главный цикл ─────────────────────────────────────────────────────────────

async def main():
    init_db()
    logger.info("Приложение запущено")

    while True:
        print_menu()
        choice = input(f"  {color('Выберите действие:', CYAN)} ").strip()

        if choice == "1":
            await do_search()
        elif choice == "2":
            show_history()
        elif choice == "3":
            show_favorites()
        elif choice == "4":
            show_stats()
        elif choice == "5":
            do_export()
        elif choice == "6":
            clear_history()
            logger.info("История очищена")
            print(color("\n  ✓ История очищена.\n", GREEN))
        elif choice == "0":
            logger.info("Приложение завершено")
            print(color("\n  До свидания!\n", CYAN))
            sys.exit(0)
        else:
            print(color("\n  Неверный выбор. Попробуйте снова.\n", RED))


if __name__ == "__main__":
    asyncio.run(main())
