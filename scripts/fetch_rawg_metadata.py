"""
fetch_rawg_metadata.py
-----------------------
Step 1.2: Extract Game Metadata (the RAWG API).

Pulls the top N games from the RAWG API (ordered by rating count,
i.e. popularity), keeps exactly the fields required by the Master
Plan, and upserts them into the Games table using the RAWG game ID
as the primary key.

Usage:
    python scripts/fetch_rawg_metadata.py --count 3000
    python scripts/fetch_rawg_metadata.py --count 1000 --page-size 40
"""

import argparse
import sqlite3
import time

import requests
from tqdm import tqdm

from config import DB_PATH, RAWG_API_KEY, RAWG_BASE_URL, get_logger

logger = get_logger("fetch_rawg_metadata")

MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 2
REQUEST_TIMEOUT_SECONDS = 30


def _get_page(page: int, page_size: int) -> dict:
    """Fetch a single page of results from RAWG, with retry/backoff.

    Retries on both HTTP-level failures (429/5xx) and network-level
    failures (timeouts, dropped connections, DNS hiccups) - a
    ReadTimeout/ConnectionError happens before any response object
    exists, so it needs its own except clause or it crashes the run.
    """
    params = {
        "key": RAWG_API_KEY,
        "page": page,
        "page_size": page_size,
        "ordering": "-added",  # most-popular-first, gives useful games early
    }

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(RAWG_BASE_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_error = exc
            wait = RETRY_BACKOFF_SECONDS * attempt
            logger.warning(
                "Network error fetching page %s (%s). Retrying in %ss (attempt %s/%s)...",
                page, type(exc).__name__, wait, attempt, MAX_RETRIES,
            )
            time.sleep(wait)
            continue

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429 or response.status_code >= 500:
            wait = RETRY_BACKOFF_SECONDS * attempt
            logger.warning(
                "RAWG returned %s on page %s. Retrying in %ss (attempt %s/%s)...",
                response.status_code, page, wait, attempt, MAX_RETRIES,
            )
            time.sleep(wait)
            continue

        logger.error("RAWG request failed (status %s): %s", response.status_code, response.text[:200])
        response.raise_for_status()

    raise RuntimeError(f"Failed to fetch page {page} after {MAX_RETRIES} retries.") from last_error


def _extract_fields(game: dict) -> tuple:
    """Map a raw RAWG JSON record to the columns required by the Master Plan."""
    genres = ",".join(g["name"] for g in game.get("genres", []))
    # RAWG's list endpoint doesn't return a single "developer" field directly;
    # it's approximated here from 'developers' when present.
    developers = ",".join(d["name"] for d in game.get("developers", [])) or None

    return (
        game["id"],                      # game_id (RAWG primary key)
        game.get("name"),                # title
        game.get("released"),             # release_date
        genres or None,                   # genres
        developers,                        # developer
        game.get("metacritic"),           # metacritic
        game.get("background_image"),     # image_url
    )


def fetch_rawg_games(total_count: int, page_size: int = 40, db_path: str = DB_PATH) -> int:
    if not RAWG_API_KEY:
        raise EnvironmentError(
            "RAWG_API_KEY is not set. Copy .env.example to .env and add your key "
            "from https://rawg.io/apidocs"
        )

    total_pages = (total_count + page_size - 1) // page_size
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    inserted_or_updated = 0

    try:
        for page in tqdm(range(1, total_pages + 1), desc="Fetching RAWG pages"):
            data = _get_page(page, page_size)
            results = data.get("results", [])
            if not results:
                logger.info("No more results returned by RAWG at page %s. Stopping early.", page)
                break

            rows = [_extract_fields(g) for g in results]
            cur.executemany(
                """
                INSERT INTO Games (game_id, title, release_date, genres, developer, metacritic, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game_id) DO UPDATE SET
                    title=excluded.title,
                    release_date=excluded.release_date,
                    genres=excluded.genres,
                    developer=excluded.developer,
                    metacritic=excluded.metacritic,
                    image_url=excluded.image_url;
                """,
                rows,
            )
            conn.commit()
            inserted_or_updated += len(rows)

            # RAWG free tier allows generous but not unlimited request rates.
            # A small delay keeps us well under any burst limit.
            time.sleep(0.4)

    finally:
        conn.close()

    logger.info("Finished. Inserted/updated %s game records.", inserted_or_updated)
    return inserted_or_updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch game metadata from the RAWG API.")
    parser.add_argument("--count", type=int, default=3000, help="Total number of games to fetch (1000-5000 per Master Plan).")
    parser.add_argument("--page-size", type=int, default=40, help="RAWG page size (max 40).")
    args = parser.parse_args()

    fetch_rawg_games(total_count=args.count, page_size=args.page_size)
