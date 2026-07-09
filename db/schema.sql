-- ============================================================
-- Game Platforms Summarization and Recommendation
-- Phase 1 - Database Schema (SQLite)
-- ============================================================
-- Design notes:
--   * Games.game_id uses the RAWG game ID as the primary key,
--     as required by the Master Plan (Step 1.2).
--   * Prices.game_id is nullable on insert because raw Steam /
--     Epic records are loaded BEFORE fuzzy matching resolves
--     them to a RAWG game. fuzzy_match_games.py fills this in.
--   * store_game_title is kept permanently (even after matching)
--     so the matching step is auditable and can be re-run or
--     manually corrected without re-scraping.
--   * User_Likes uses a session_id instead of a user_id because
--     Phase 3 (Streamlit) has no login system - it relies on
--     st.session_state, which this schema anticipates.
-- ============================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Games (
    game_id         INTEGER PRIMARY KEY,      -- RAWG game ID
    title           TEXT NOT NULL,
    release_date    TEXT,
    genres          TEXT,                     -- comma-separated, e.g. "Action,RPG"
    developer       TEXT,
    metacritic      INTEGER,
    image_url       TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Prices (
    price_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id              INTEGER,                 -- FK -> Games.game_id, NULL until matched
    store                TEXT NOT NULL CHECK (store IN ('Steam', 'Epic Games')),
    store_game_title     TEXT NOT NULL,            -- raw title as it appears on the store
    store_app_id         TEXT,                     -- Steam appid or Epic product slug
    price                REAL,                     -- current price, NULL if not for sale / delisted
    discount_percent     REAL DEFAULT 0,
    currency             TEXT DEFAULT 'USD',
    url                  TEXT,
    match_confidence     INTEGER,                  -- 0-100 fuzzy match score, NULL until matched
    last_updated         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES Games(game_id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS User_Likes (
    like_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT NOT NULL,      -- Streamlit st.session_state id
    game_id      INTEGER NOT NULL,
    liked_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES Games(game_id) ON DELETE CASCADE,
    UNIQUE (session_id, game_id)     -- prevents duplicate likes of the same game
);

-- Helpful indexes for the queries Phase 2 and Phase 3 will run constantly
CREATE INDEX IF NOT EXISTS idx_prices_game_id      ON Prices(game_id);
CREATE INDEX IF NOT EXISTS idx_prices_store_title   ON Prices(store_game_title);
CREATE INDEX IF NOT EXISTS idx_games_title          ON Games(title);
CREATE INDEX IF NOT EXISTS idx_likes_session        ON User_Likes(session_id);
