"""
setup_database.py
------------------
Step 1.1: Set up the environment & database.

Creates the SQLite database file and all three required tables
(Games, Prices, User_Likes) from schema.sql. Safe to re-run at any
time - all statements use CREATE TABLE IF NOT EXISTS.

Usage:
    python db/setup_database.py
"""

import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
from config import DB_PATH, SCHEMA_PATH, get_logger  # noqa: E402

logger = get_logger("setup_database")


def create_database(db_path: str = DB_PATH, schema_path: str = SCHEMA_PATH) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema_sql)
        conn.commit()
        logger.info("Database created/verified at: %s", db_path)

        # Sanity check: confirm the three required tables exist
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cur.fetchall()}
        required = {"Games", "Prices", "User_Likes"}
        missing = required - tables
        if missing:
            raise RuntimeError(f"Schema did not create expected tables: {missing}")
        logger.info("Tables present: %s", sorted(required))
    finally:
        conn.close()


if __name__ == "__main__":
    create_database()
