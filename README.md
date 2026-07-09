
# Game Platform Recommendation & Price Comparison Engine

**Game Platforms Summarization and Recommendation** 

Computational Data Analytics, Machine Learning Supervised Techniques, ETF Sarajevo (Prof. Dr. Aida Branković)

A data-driven platform that aggregates game pricing across multiple storefronts, generates personalized recommendations using a K-Nearest Neighbors model, and presents both through an interactive Streamlit dashboard.

## Link to Web Application:
### https://gameplatformprojectcdamlpr.streamlit.app


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
| **Epic Games** | Loaded from a Kaggle CSV dataset (Epic Games Store listings) | A historical snapshot rather than a live feed, so it's labeled as a general retail reference price rather than a current Epic Games Store price |

Raw rows from each source are inserted with `game_id = NULL` and only a raw title. A dedicated fuzzy-matching step then resolves each title to its canonical `game_id` and records a `match_confidence` score for every row - matched or not - so weak matches remain auditable instead of silently incorrect. Ingestion and normalization are kept as separate, independently testable steps.

## Architecture

```text
Games table  <───┐
                  │  game_id (matched)
Prices table ─────┘
  ├─ Steam rows       (Steam's public JSON endpoints)
  └─ Epic Games rows  (Kaggle CSV dataset)

User_Likes table  (populated by the app's "Like" feature)
```

## Machine Learning Pipeline

The recommendation engine uses **content-based filtering** with a **K-Nearest Neighbors (k-NN)** algorithm.

- **Vectorization** - builds a user centroid vector from the features (genres, Metacritic scores) of a user's liked games.
- **Holdout evaluation** - validated with a strict **60/20/20 train/validation/test split** on the Kaggle dataset to guard against overfitting.
- **Metrics** - computes Precision, Recall, and F1-Score, and generates `precision_recall_curve.png` to visualize model performance across thresholds.
<img width="1600" height="1552" alt="image" src="https://github.com/user-attachments/assets/d1820595-832e-4e0e-a7e3-5b1a2ebc5a5f" />

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
│   ├── games.csv                  #  Epic Games Store listings
│   └── steam-200k.csv             # Kaggle Steam-200k interactions dataset
├── db/
│   ├── schema.sql                 # Games, Prices, User_Likes DDL
│   ├── setup_database.py          # Initializes the database
│   ├── game_platform.db           # SQLite database
│   └── model_metrics.json         # Latest holdout evaluation metrics
├── scripts/
│   ├── fetch_rawg_metadata.py     # Pulls game metadata from RAWG
│   ├── fetch_steam_prices.py      # Fetches live Steam pricing
│   ├── load_epic_dataset.py       # Loads Epic Games Store data from data/games.csv
│   ├── fuzzy_match_games.py       # Normalizes raw titles to game_id
│   ├── fix_prices.py              # One-off cents-to-dollars price correction
│   ├── price_summary_engine.py    # get_price_summary(game_id)
│   ├── seed_sample_data.py        # Demo/offline sample data
│   ├── recommendation_engine.py   # Live in-app k-NN recommender
│   ├── recommendation_model.py    # Offline ML pipeline & holdout evaluation
│   └── export_audit_queue.py      # QA script for unmatched prices
├── app.py                         # Streamlit application (3 pages)
├── config.py                      # Shared env vars, paths, logging
├── requirements.txt
└── precision_recall_curve.png     # Generated by recommendation_model.py
```
