"""
seed_sample_data.py
-----------------------
Not part of the graded pipeline itself - a convenience script that
inserts a handful of realistic rows so the whole pipeline (fuzzy
matching -> price summarization -> future Streamlit UI) can be
demoed and unit-tested without needing a live RAWG key or hitting
Steam's rate limits, e.g. while offline or during a live demo.

Usage:
    python scripts/seed_sample_data.py
"""

import sqlite3

from config import DB_PATH, get_logger

logger = get_logger("seed_sample_data")

SAMPLE_GAMES = [
    (3328, "The Witcher 3: Wild Hunt", "2015-05-18", "RPG,Adventure", "CD PROJEKT RED", 92, "https://example.com/witcher3.jpg"),
    (28, "Red Dead Redemption 2", "2018-10-26", "Action,Adventure", "Rockstar Games", 96, "https://example.com/rdr2.jpg"),
    (4200, "Portal 2", "2011-04-18", "Puzzle,Shooter", "Valve", 95, "https://example.com/portal2.jpg"),
]

SAMPLE_PRICES = [
    # (store, store_game_title, store_app_id, price, discount_percent, currency, url)
    ("Steam", "The Witcher 3: Wild Hunt - Complete Edition", "292030", 14.99, 30.0, "USD", "https://store.steampowered.com/app/292030/"),
    ("Epic Games", "The Witcher 3: Wild Hunt Complete Edition", None, 19.99, 0.0, "USD", "https://store.epicgames.com/witcher3"),
    ("Steam", "Red Dead Redemption 2", "1174180", 39.99, 20.0, "USD", "https://store.steampowered.com/app/1174180/"),
    ("Steam", "Portal 2", "620", 4.99, 50.0, "USD", "https://store.steampowered.com/app/620/"),
    ("Epic Games", "Portal 2", None, 9.99, 0.0, "USD", "https://store.epicgames.com/portal2"),
]


def seed(db_path: str = DB_PATH) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.executemany(
            """
            INSERT INTO Games (game_id, title, release_date, genres, developer, metacritic, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(game_id) DO NOTHING;
            """,
            SAMPLE_GAMES,
        )
        cur.executemany(
            """
            INSERT INTO Prices (game_id, store, store_game_title, store_app_id, price, discount_percent, currency, url)
            VALUES (NULL, ?, ?, ?, ?, ?, ?, ?);
            """,
            SAMPLE_PRICES,
        )
        conn.commit()
        logger.info("Seeded %s sample games and %s sample price rows.", len(SAMPLE_GAMES), len(SAMPLE_PRICES))
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
