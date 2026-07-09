"""
fuzzy_match_games.py
-----------------------
Step 1.3: Fuzzy Matching (Data Normalization).

Every row inserted by fetch_steam_prices.py and load_epic_dataset.py
starts with game_id = NULL and only a raw store_game_title (e.g.
"The Witcher 3: Wild Hunt - Complete Edition"). This script resolves
each of those raw titles to the correct RAWG game_id already sitting
in the Games table (e.g. "The Witcher 3" -> game_id 3328), using
TheFuzz (Levenshtein-based) string matching.

Matching strategy:
  1. Normalize both sides (lowercase, strip edition/subtitle noise
     like "- Definitive Edition", "GOTY", "(2015)", etc.).
  2. Use fuzz.token_sort_ratio, which is robust to word re-ordering
     ("Witcher 3, The" vs "The Witcher 3") and partial subtitle noise.
  3. Only accept a match if its score clears MATCH_THRESHOLD, and
     always store the score in Prices.match_confidence, so weak or
     wrong matches can be audited and manually reviewed later rather
     than silently trusted.

Usage:
    python scripts/fuzzy_match_games.py
    python scripts/fuzzy_match_games.py --threshold 85
"""

import argparse
import re
import sqlite3

from thefuzz import fuzz, process
from tqdm import tqdm

from config import DB_PATH, get_logger

logger = get_logger("fuzzy_match_games")

DEFAULT_MATCH_THRESHOLD = 80

_EDITION_NOISE = re.compile(
    r"\b(goty|game of the year|definitive|complete|deluxe|ultimate|"
    r"standard|remastered|remaster|enhanced|special|gold|"
    r"director'?s cut|edition|bundle|collection)\b",
    re.IGNORECASE,
)
_PAREN_NOISE = re.compile(r"[\(\[].*?[\)\]]")
_PUNCT = re.compile(r"[^a-z0-9 ]")


def normalize_title(title: str) -> str:
    if not title:
        return ""
    t = title.lower()
    t = _PAREN_NOISE.sub(" ", t)     # drop "(2015)", "[PC]" etc.
    t = _EDITION_NOISE.sub(" ", t)   # drop edition/marketing noise words
    t = t.replace("-", " ").replace(":", " ")
    t = _PUNCT.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def load_games(db_path: str) -> dict[str, int]:
    """Return {normalized_title: game_id} for every game in the Games table."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT game_id, title FROM Games;")
        mapping = {}
        for game_id, title in cur.fetchall():
            norm = normalize_title(title)
            if norm:
                mapping[norm] = game_id
        return mapping
    finally:
        conn.close()


def load_unmatched_prices(db_path: str) -> list[tuple[int, str]]:
    """Return [(price_id, store_game_title), ...] for rows still needing a match."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT price_id, store_game_title FROM Prices WHERE game_id IS NULL;")
        return cur.fetchall()
    finally:
        conn.close()


def run_fuzzy_matching(threshold: int = DEFAULT_MATCH_THRESHOLD, db_path: str = DB_PATH) -> dict:
    games_by_norm_title = load_games(db_path)
    if not games_by_norm_title:
        raise RuntimeError("Games table is empty. Run fetch_rawg_metadata.py first.")

    choices = list(games_by_norm_title.keys())
    unmatched = load_unmatched_prices(db_path)
    logger.info("Attempting to match %s price rows against %s known game titles.", len(unmatched), len(choices))

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    stats = {"matched": 0, "rejected_below_threshold": 0}

    try:
        for price_id, raw_title in tqdm(unmatched, desc="Fuzzy matching"):
            norm_title = normalize_title(raw_title)
            if not norm_title:
                continue

            best_match, score = process.extractOne(
                norm_title, choices, scorer=fuzz.token_sort_ratio
            )

            if score >= threshold:
                matched_game_id = games_by_norm_title[best_match]
                cur.execute(
                    "UPDATE Prices SET game_id = ?, match_confidence = ? WHERE price_id = ?;",
                    (matched_game_id, score, price_id),
                )
                stats["matched"] += 1
            else:
                # Still record the best score we found, for manual review,
                # without committing to a (likely wrong) game_id.
                cur.execute(
                    "UPDATE Prices SET match_confidence = ? WHERE price_id = ?;",
                    (score, price_id),
                )
                stats["rejected_below_threshold"] += 1

        conn.commit()
    finally:
        conn.close()

    logger.info(
        "Matching complete. Matched: %s | Below threshold (%s): %s",
        stats["matched"], threshold, stats["rejected_below_threshold"],
    )
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fuzzy-match raw store titles to RAWG game_id values.")
    parser.add_argument("--threshold", type=int, default=DEFAULT_MATCH_THRESHOLD, help="Minimum fuzz score (0-100) to accept a match.")
    args = parser.parse_args()

    run_fuzzy_matching(threshold=args.threshold)
