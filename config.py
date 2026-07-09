"""
config.py
---------
Central place for environment variables, paths, and logging setup.
Every other script in Phase 1 imports from here so settings only
need to change in one place.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = one level above /scripts
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

RAWG_API_KEY = os.getenv("RAWG_API_KEY", "")
DB_PATH = str(PROJECT_ROOT / os.getenv("DB_PATH", "db/game_platform.db"))
SCHEMA_PATH = str(PROJECT_ROOT / "db" / "schema.sql")
STEAM_COUNTRY_CODE = os.getenv("STEAM_COUNTRY_CODE", "us")

# Free key from https://steamcommunity.com/dev/apikey - needed for
# IStoreService/GetAppList (the old ISteamApps/GetAppList/v2 endpoint was
# deprecated by Valve and now 404s).
STEAM_API_KEY = os.getenv("STEAM_API_KEY", "")

RAWG_BASE_URL = "https://api.rawg.io/api/games"
STEAM_APP_LIST_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
STEAM_APP_DETAILS_URL = "https://store.steampowered.com/api/appdetails"

LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """Return a logger that writes to both console and a shared log file."""
    logger = logging.getLogger(name)
    if logger.handlers:  # avoid duplicate handlers on re-import
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    file_handler = logging.FileHandler(LOG_DIR / "phase1_pipeline.log")
    file_handler.setFormatter(fmt)

    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger
