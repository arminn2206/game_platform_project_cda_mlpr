
# Game Platform Recommendation & Price Comparison Engine

**Game Platforms Summarization and Recommendation** 

Computational Data Analytics, Machine Learning Supervised Techniques, ETF Sarajevo (Prof. Dr. Aida Branković)

A data-driven platform that aggregates game pricing across multiple storefronts, generates personalized recommendations using a K-Nearest Neighbors model, and presents both through an interactive Streamlit dashboard.

## Overview

The project is built around three layers that work together end to end:

- **Data engineering pipeline** - ingests, normalizes, and stores game and pricing data from multiple sources into a shared SQLite database.
- **Machine learning engine** - a content-based recommendation model that learns from user preferences and is validated with a formal train/validation/test split.
- **Web application** - a Streamlit dashboard for searching games, comparing prices, receiving recommendations, and monitoring data quality.

## Data Sources

The pipeline integrates and compares prices from two sources:

| Source | Method | Notes |
|---|---|---|
| **Steam** | Live data via Steam's public JSON endpoints | Real-time pricing |
| **Epic Games/Common Retail Price** | Loaded from a Kaggle CSV dataset (Epic Games Store listings) | A historical snapshot rather than a live feed, so it's labeled as a general retail reference price rather than a current Epic Games Store price |

Raw rows from each source are inserted with `game_id = NULL` and only a raw title. A dedicated fuzzy-matching step then resolves each title to its canonical `game_id` and records a `match_confidence` score for every row - matched or not - so weak matches remain auditable instead of silently incorrect. Ingestion and normalization are kept as separate, independently testable steps.

## Architecture

```text
Games table  <───┐
                  │  game_id (matched)
Prices table ─────┘
  ├─ Steam rows                (Steam's public JSON endpoints)
  └─ Epic Games rows  (Kaggle CSV dataset)

User_Likes table  (populated by the app's "Like" feature)
```

## Machine Learning Pipeline

The recommendation engine uses **content-based filtering** with a **K-Nearest Neighbors (k-NN)** algorithm.

- **Vectorization** — builds a user centroid vector from the features (genres, Metacritic scores) of a user's liked games.
- **Holdout evaluation** — validated with a strict **60/20/20 train/validation/test split** on the Kaggle dataset to guard against overfitting.
- **Metrics** — computes Precision, Recall, and F1-Score, and generates `precision_recall_curve.png` to visualize model performance across thresholds.

## Web Application

An interactive dashboard (`app.py`) built with Streamlit, unifying the data pipeline and the ML engine into a single user-facing tool.

### Game Search & Price Comparison
- Autocomplete search bar backed by a cached database query, reducing user typos.
- Guarantees fair comparisons by only surfacing games with confirmed prices from **both** Steam and the Common Retail Price source.

### Personalized Recommendations
- Generates a tailored list of the top 5 recommended games based on a user's liked titles.
- Supports exporting personalized recommendations and current prices to CSV.

### Admin & ML Validation Dashboard
- Live monitoring of database health (total games, active prices).
- One-click re-run of the holdout evaluation (`recommendation_model.py`) directly from the browser, with live metrics and the precision-recall plot rendered in place.
- **Audit trail** — `scripts/export_audit_queue.py` flags borderline/unmatched prices and exports them to a CSV review queue, keeping the database reliable.

## Project Layout

```text
game_platform_project/
├── data/
│   └── steam-200k.csv           # Kaggle dataset
├── db/
│   ├── schema.sql               # Games, Prices, User_Likes DDL
│   └── setup_database.py        # Initializes the database
├── scripts/
│   ├── config.py                # Shared env vars, paths, logging
│   ├── fetch_rawg_metadata.py   # Pulls game metadata from RAWG
│   ├── fetch_steam_prices.py    # Fetches live Steam pricing
│   ├── load_epic_dataset.py     # Loads Epic pricing from dataset
│   ├── fuzzy_match_games.py     # Normalizes raw titles to game_id
│   ├── price_summary_engine.py  # get_price_summary(game_id)
│   ├── seed_sample_data.py      # Demo/offline sample data
│   ├── recommendation_model.py  # ML pipeline & holdout evaluation
│   └── export_audit_queue.py    # QA script for unmatched prices
├── tests/
│   └── test_phase1_pipeline.py  # End-to-end pipeline tests
├── app.py                       # Streamlit application
├── precision_recall_curve.png   # Generated ML plot
├── requirements.txt
└── .env.example
```

## Getting Started

### Installation

```bash
git clone <your-repo-url>
cd game_platform_project
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and add your free RAWG API key from https://rawg.io/apidocs
```

### Running the Full Pipeline

```bash
# 1. Create the database and tables
python db/setup_database.py

# 2. Pull 1,000–5,000 games from RAWG
python scripts/fetch_rawg_metadata.py --count 3000

# 3. Gather Steam prices (auto-narrows Steam's catalogue to
#    plausible matches before spending rate-limited requests)
python scripts/fetch_steam_prices.py

# 4. Load Common Retail Price data from a downloaded Kaggle CSV
#    (sourced from Epic Games Store listings; see load_epic_dataset.py's
#    docstring for dataset links and how to adjust DATASET_COLUMN_MAP
#    to your file's columns)
python scripts/load_epic_dataset.py --csv data/epic_games_store.csv

# 5. Resolve every raw store title to the correct game_id
python scripts/fuzzy_match_games.py

# 6. Export any unmatched prices for manual review
python scripts/export_audit_queue.py

# 7. Test the summarization engine on any RAWG game_id
python scripts/price_summary_engine.py 3328

# 8. Launch the web application
streamlit run app.py
```

### Running Without API Keys (Offline Demo)

```bash
python db/setup_database.py
python scripts/seed_sample_data.py
python scripts/fuzzy_match_games.py
python scripts/price_summary_engine.py 3328
# -> "Cheapest price is $14.99 on Steam (30% off). Common Retail Price is $19.99."
```

## Testing

```bash
python -m pytest tests/test_phase1_pipeline.py -v
```

Tests run against an isolated temporary database seeded with realistic sample data, and verify that:
- Fuzzy matching resolves every sample row.
- The summarization engine correctly identifies the true minimum price.
- Single-store games are handled correctly.
- Unmatched or unknown games fail gracefully rather than crashing the app's "View Details" feature.

## Key Interfaces for Extension

- `Games` and `Prices` tables — populated and normalized, ready for downstream use.
- `get_price_summary(game_id)` — returns an explanatory `summary_text`; used directly by the app's "View Details" feature.
- `User_Likes` table — supports the app's "Like" feature (`session_id`, `game_id`).
- Feature engineering can read `Games.genres`, `Games.metacritic`, and the matched minimum price per game directly from `Prices` via a simple `MIN(price) GROUP BY game_id` query.
