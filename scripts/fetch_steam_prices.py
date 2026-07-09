"""
fetch_steam_prices.py
-----------------------
Step 1.3 (Steam half): Gather current prices from Steam.

Steam does not require scraping for this project - it publishes two
public, keyless JSON endpoints that are sufficient and far more
reliable than HTML scraping:

  1. ISteamApps/GetAppList/v2  -> full catalogue of {appid, name}
     for every app on Steam (~150k+ entries).
  2. store.steampowered.com/api/appdetails?appids=<id>
     -> price_overview (current price, discount, currency) for one
        specific app at a time.

Because appdetails is rate-limited (Steam throttles roughly ~200
requests per 5 minutes per IP for this endpoint), this script only
calls it for apps whose *names* already look like a strong candidate
match against titles already sitting in our Games table - i.e. we
narrow ~150k Steam apps down to a few thousand candidates with a fast
in-memory fuzzy pass BEFORE spending any network calls on appdetails.
Final, authoritative fuzzy matching against the Games table (with a
stored confidence score) still happens later in fuzzy_match_games.py.

Usage:
    python scripts/fetch_steam_prices.py
    python scripts/fetch_steam_prices.py --limit 500   # smaller test run
"""

import argparse
import sqlite3
import time

import requests
from thefuzz import fuzz
from tqdm import tqdm

from config import DB_PATH, STEAM_API_KEY, STEAM_APP_DETAILS_URL, STEAM_APP_LIST_URL, STEAM_COUNTRY_CODE, get_logger

logger = get_logger("fetch_steam_prices")

CANDIDATE_MATCH_THRESHOLD = 70   # coarse pre-filter, final scoring happens later
REQUEST_DELAY_SECONDS = 1.6      # keeps us safely under Steam's rate limit


def get_full_steam_app_list() -> list[dict]:
    """Download the full Steam catalogue via IStoreService/GetAppList.

    Valve deprecated the old keyless ISteamApps/GetAppList/v2 endpoint (it
    now 404s - "can no longer scale to the number of items on Steam").
    IStoreService/GetAppList is the replacement. It needs a free Web API
    key (get one at https://steamcommunity.com/dev/apikey and put it in
    .env as STEAM_API_KEY=...), and it's paginated 50,000 apps at a time
    via last_appid, so we loop until have_more_results is false.
    """
    if not STEAM_API_KEY:
        raise RuntimeError(
            "STEAM_API_KEY is not set. Get a free key at "
            "https://steamcommunity.com/dev/apikey and add "
            "STEAM_API_KEY=yourkeyhere to your .env file."
        )

    logger.info("Downloading full Steam app list (paginated)...")
    apps: list[dict] = []
    last_appid = 0
    while True:
        params = {
            "key": STEAM_API_KEY,
            "include_games": True,
            "include_dlc": False,
            "include_software": False,
            "include_videos": False,
            "include_hardware": False,
            "max_results": 50000,
            "last_appid": last_appid,
        }
        response = requests.get(STEAM_APP_LIST_URL, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()["response"]
        batch = payload.get("apps", [])
        apps.extend(batch)

        if not payload.get("have_more_results"):
            break
        last_appid = payload["last_appid"]
        time.sleep(REQUEST_DELAY_SECONDS)

    logger.info("Steam app list contains %s entries.", len(apps))
    return apps


def get_local_game_titles(db_path: str) -> list[str]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT title FROM Games WHERE title IS NOT NULL;")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def find_candidate_apps(steam_apps: list[dict], our_titles: list[str]) -> list[dict]:
    """Cheap, local fuzzy pre-filter: keep only Steam apps whose name is
    plausibly one of our RAWG titles, so we don't waste rate-limited
    appdetails calls on the other ~140k irrelevant Steam apps."""
    our_titles_lower = {t.lower() for t in our_titles}
    candidates = []
    for app in steam_apps:
        name = app.get("name", "").strip()
        if not name:
            continue
        # Fast exact/substring check first (cheap), fuzzy only as fallback
        if name.lower() in our_titles_lower:
            candidates.append(app)
            continue
        best = max((fuzz.token_sort_ratio(name.lower(), t) for t in our_titles_lower), default=0)
        if best >= CANDIDATE_MATCH_THRESHOLD:
            candidates.append(app)
    logger.info("Narrowed %s Steam apps down to %s match candidates.", len(steam_apps), len(candidates))
    return candidates


def fetch_price_for_app(appid: int) -> dict | None:
    params = {"appids": appid, "cc": STEAM_COUNTRY_CODE, "filters": "price_overview"}
    response = requests.get(STEAM_APP_DETAILS_URL, params=params, timeout=15)
    if response.status_code != 200:
        return None

    data = response.json().get(str(appid))
    
    if isinstance(data, list):
        return None
        
    if not data or not isinstance(data, dict) or not data.get("success"):
        return None

    # SAFELY get the 'data' payload. If Steam returns a list (like []) instead of a dict, skip it.
    app_data = data.get("data")
    if not app_data or not isinstance(app_data, dict):
        return None

    price_overview = app_data.get("price_overview")
    if not price_overview or not isinstance(price_overview, dict):
        return None  # free-to-play or region-restricted or delisted

    return {
        "price": price_overview.get("final", 0) / 100,
        "discount_percent": price_overview.get("discount_percent", 0),
        "currency": price_overview.get("currency", "USD"),
    }


def fetch_steam_prices(limit: int | None = None, db_path: str = DB_PATH) -> int:
    our_titles = get_local_game_titles(db_path)
    if not our_titles:
        raise RuntimeError("Games table is empty. Run fetch_rawg_metadata.py first.")

    if limit is not None:
        our_titles = list(our_titles)[:limit]

    steam_apps = get_full_steam_app_list()
    candidates = find_candidate_apps(steam_apps, our_titles)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    rows_inserted = 0

    try:
        for app in tqdm(candidates, desc="Fetching Steam prices"):
            price_info = fetch_price_for_app(app["appid"])
            time.sleep(REQUEST_DELAY_SECONDS)  # respect Steam's rate limit
            if not price_info:
                continue

            cur.execute(
                """
                INSERT INTO Prices
                    (game_id, store, store_game_title, store_app_id, price, discount_percent, currency, url)
                VALUES (NULL, 'Steam', ?, ?, ?, ?, ?, ?);
                """,
                (
                    app["name"],
                    str(app["appid"]),
                    price_info["price"],
                    price_info["discount_percent"],
                    price_info["currency"],
                    f"https://store.steampowered.com/app/{app['appid']}/",
                ),
            )
            rows_inserted += 1
            if rows_inserted % 25 == 0:
                conn.commit()

        conn.commit()
    finally:
        conn.close()

    logger.info("Finished. Inserted %s Steam price records.", rows_inserted)
    return rows_inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch current Steam prices for candidate matches.")
    parser.add_argument("--limit", type=int, default=100, help="Cap candidate apps.")
    args = parser.parse_args()

    fetch_steam_prices(limit=args.limit)