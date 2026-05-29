import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")


def get_connection() -> sqlite3.Connection:
    """Возвращает соединение с БД. Создаёт файл если его нет."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # доступ к колонкам по имени
    return conn


def init_db():
    """
    Создаёт таблицы при первом запуске.
    Вызывается один раз при старте приложения.
    """
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                query     TEXT NOT NULL,
                source    TEXT NOT NULL,
                searched_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                source     TEXT NOT NULL,
                extra_info TEXT,
                added_at   TEXT NOT NULL
            )
        """)
        conn.commit()


def add_to_history(query: str, source: str):
    """Сохраняет поисковый запрос в историю."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO history (query, source, searched_at) VALUES (?, ?, ?)",
            (query, source, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()


def get_history(limit: int = 20) -> list[dict]:
    """Возвращает последние `limit` записей истории."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT query, source, searched_at FROM history ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def add_to_favorites(title: str, source: str, extra_info: str = ""):
    """Добавляет запись в избранное."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO favorites (title, source, extra_info, added_at) VALUES (?, ?, ?, ?)",
            (title, source, extra_info, datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()


def get_favorites() -> list[dict]:
    """Возвращает всё избранное."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, title, source, extra_info, added_at FROM favorites ORDER BY id DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def remove_from_favorites(fav_id: int):
    """Удаляет запись из избранного по id."""
    with get_connection() as conn:
        conn.execute("DELETE FROM favorites WHERE id = ?", (fav_id,))
        conn.commit()


def clear_history():
    """Очищает всю историю поиска."""
    with get_connection() as conn:
        conn.execute("DELETE FROM history")
        conn.commit()


# ─── Экспорт и статистика ─────────────────────────────────────────────────────

def export_favorites_csv(path: str) -> int:
    """
    Экспортирует избранное в CSV-файл.
    Возвращает количество записанных строк.
    """
    import csv
    rows = get_favorites()
    if not rows:
        return 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "title", "source", "extra_info", "added_at"])
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def get_history_stats() -> dict:
    """
    Статистика по истории: топ-5 запросов и разбивка по источникам.
    Использует GROUP BY и COUNT в SQL.
    """
    with get_connection() as conn:
        top_queries = conn.execute("""
            SELECT query, COUNT(*) as cnt
            FROM history
            GROUP BY query
            ORDER BY cnt DESC
            LIMIT 5
        """).fetchall()

        by_source = conn.execute("""
            SELECT source, COUNT(*) as cnt
            FROM history
            GROUP BY source
            ORDER BY cnt DESC
        """).fetchall()

        total = conn.execute("SELECT COUNT(*) FROM history").fetchone()[0]

    return {
        "total": total,
        "top_queries": [dict(r) for r in top_queries],
        "by_source": [dict(r) for r in by_source],
    }
