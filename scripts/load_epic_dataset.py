"""
load_epic_dataset.py
-----------------------
Step 1.3 (Epic Games half): Load Epic Games Store prices from a
Kaggle dataset instead of a live scraper.

Why a dataset instead of a scraper/API:
  * Epic Games has no official public pricing API.
  * Epic's storefront is a JavaScript single-page app, so it requires
    Selenium + browser automation to scrape reliably, and Epic
    actively changes its front-end GraphQL contracts, which makes a
    scraper fragile and a poor foundation for a graded, reproducible
    pipeline.
  * A static, versioned dataset gives every team member and the
    grader identical, reproducible input data - the same argument
    the Master Plan already used for the Kaggle "Steam User
    Interactions" dataset in Phase 2, Step 2.1.

Recommended dataset (download manually or via the Kaggle CLI):
    "Epic Games Store Dataset" - search Kaggle for
    "epic games store dataset" and pick a listing that includes at
    minimum: title, price, discounted price, release date, and URL.
    Two commonly used listings as of 2026:
        - mexwell/epic-games-store-dataset
        - jrobischon/epic-games-store-full-dataset
    (Verify column names against DATASET_COLUMN_MAP below - Kaggle
    contributors do not use a standardized schema, so this mapping is
    the part you must double check/adjust after downloading.)

Setup:
    pip install kaggle
    # place kaggle.json (API token) in ~/.kaggle/
    kaggle datasets download -d <owner>/<dataset-slug> -p data/ --unzip

Usage:
    python scripts/load_epic_dataset.py --csv data/epic_games_store.csv
"""

import argparse
import sqlite3

import pandas as pd

from config import DB_PATH, get_logger

logger = get_logger("load_epic_dataset")

# Adjust the right-hand values to match whichever Kaggle CSV you download.
# Left-hand keys are the concepts this project needs.
DATASET_COLUMN_MAP = {
    "id": "id",
    "title": "name",              # Maps 'name' to 'title'
    "game_slug": "game_slug",
    "price": "price",
    "release_date": "release_date",
    "platform": "platform",
    "description": "description",
    "developer": "developer",
    "publisher": "publisher",
    "genres": "genres"
}


def load_epic_csv(csv_path: str, db_path: str = DB_PATH) -> int:
    logger.info("Reading Epic Games Store dataset: %s", csv_path)
    df = pd.read_csv(csv_path)

    missing_cols = [c for c in DATASET_COLUMN_MAP.values() if c not in df.columns]
    if missing_cols:
        raise KeyError(
            f"Expected columns {missing_cols} not found in {csv_path}. "
            f"Available columns: {list(df.columns)}. "
            "Update DATASET_COLUMN_MAP at the top of this script to match your download."
        )

    df = df.rename(columns={v: k for k, v in DATASET_COLUMN_MAP.items()})
    df = df.dropna(subset=["title"])

    # If the dataset has no separate discounted-price column, fall back to full price.
    if "discount_price" not in df.columns:
        df["discount_price"] = df["price"]

    def _discount_pct(row) -> float:
        try:
            if row["price"] and row["price"] > 0:
                return round((1 - (row["discount_price"] / row["price"])) * 100, 2)
        except (TypeError, ZeroDivisionError):
            pass
        return 0.0

    df["discount_percent"] = df.apply(_discount_pct, axis=1)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    rows_inserted = 0

    try:
        for _, row in df.iterrows():
            cur.execute(
                """
                INSERT INTO Prices
                    (game_id, store, store_game_title, store_app_id, price, discount_percent, currency, url)
                VALUES (NULL, 'Epic Games', ?, NULL, ?, ?, 'USD', ?);
                """,
                (
                    str(row["title"]).strip(),
                    float(row["discount_price"]) if pd.notna(row["discount_price"]) else None,
                    float(row["discount_percent"]),
                    row.get("url"),
                ),
            )
            rows_inserted += 1

        conn.commit()
    finally:
        conn.close()

    logger.info("Finished. Inserted %s Epic Games price records.", rows_inserted)
    return rows_inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Epic Games Store prices from a Kaggle CSV dataset.")
    parser.add_argument("--csv", required=True, help="Path to the downloaded Epic Games Store CSV file.")
    args = parser.parse_args()

    load_epic_csv(csv_path=args.csv)
