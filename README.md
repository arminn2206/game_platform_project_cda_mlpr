```markdown
# Phase 1: Data Engineering & Summarization (CDA)

Game Platforms Summarization and Recommendation — Computational Data Analytics, ETF Sarajevo (Prof. Dr. Aida Branković)

This is the completed **Phase 1** deliverable from the Project Master Plan. It builds the database, the data pipeline, and the price summarization engine that Phase 2 (ML recommendations) and Phase 3 (Streamlit UI) depend on.

## Data Scope

The pipeline successfully integrates and compares prices across two major storefronts: **Steam** and **Epic Games**, providing a robust multi-store comparison.

1. **Steam Data:** Live pricing data is fetched directly using Steam's public JSON endpoints.
2. **Epic Games Data:** Price data is loaded from a Kaggle CSV dataset, ensuring a highly reproducible, structured, and stable data source for the machine learning models.

## Architecture

```text
Games table  <───┐
                  │  game_id (matched)
Prices table ─────┘
  ├─ Steam rows   (from Steam's public JSON endpoints)
  └─ Epic rows    (from a Kaggle CSV dataset)

User_Likes table  (written by Phase 3's Streamlit "Like" button)

```

Raw Steam/Epic rows are inserted with `game_id = NULL` and only a raw store title. A separate fuzzy-matching pass then resolves each raw title to the correct `game_id`, and stores a `match_confidence` score for every row — matched or not — so weak matches are auditable rather than silently wrong. This keeps scraping/loading and normalization as clean, independently-testable steps, exactly as separated in Step 1.3.

---

## Phase 2: Machine Learning & Recommendations (MLPR)

Phase 2 introduces a Content-Based Filtering recommendation engine utilizing a K-Nearest Neighbors (k-NN) algorithm.

* **Vectorization:** The engine calculates a user centroid vector based on the features (genres, metacritic scores) of the games a user has liked.
* **Holdout Evaluation:** To scientifically validate our classifier without overfitting, we implemented a strict **60/20/20 holdout split** using the Kaggle dataset.
* **Metrics:** The backend pipeline computes standard Machine Learning evaluation metrics (Precision, Recall, and F1-Score) and generates a `precision_recall_curve.png` plot to visualize the model's performance threshold.

---

## Phase 3: Streamlit Web Application

The final deliverable is an interactive web dashboard (`app.py`) deployed on Streamlit Community Cloud, tying Phase 1 and Phase 2 together.

### 1. Game Search & Price Comparison

* **Google-Style Autocomplete:** Features a dynamic `selectbox` search bar that queries the database and caches results, preventing user typos.
* **Strict Dual-Store Filtering:** The platform *strictly* guarantees perfect price comparisons. The app only processes games that successfully matched prices on both Steam and Epic Games (`HAVING COUNT(DISTINCT p.store) = 2`), ensuring zero blank spots.

### 2. Personalized Recommendations

* Based on the user's liked games, the ML algorithm generates a tailored grid of the top **5 recommended games**.
* **Offline Export:** Users can download their personalized recommendations and current prices to a CSV via a built-in export button.

### 3. Admin & ML Validation Dashboard

* We built a live Admin panel that monitors database health (total games and active prices).
* Admins can natively re-run the Phase 2 holdout evaluation script (`recommendation_model.py`) directly from the browser (using `sys.executable`). It extracts the live metrics from the terminal output and renders the ML curve plot on the screen.
* **Active QA Audit Trail:** Includes `scripts/export_audit_queue.py`, which flags borderline unmatched prices from Phase 1 and exports them into a CSV queue for human review, keeping the database pristine.

---

## Project layout

```text
game_platform_project/
├── data/
│   └── steam-200k.csv           # Kaggle dataset
├── db/
│   ├── schema.sql               # Games, Prices, User_Likes DDL
│   └── setup_database.py        # Step 1.1
├── scripts/
│   ├── config.py                # shared env vars, paths, logging
│   ├── fetch_rawg_metadata.py   # Step 1.2
│   ├── fetch_steam_prices.py    # Step 1.3 (Steam)
│   ├── load_epic_dataset.py     # Step 1.3 (Epic, dataset-based)
│   ├── fuzzy_match_games.py     # Step 1.3 (normalization)
│   ├── price_summary_engine.py  # Step 1.4 — get_price_summary(game_id)
│   ├── seed_sample_data.py      # demo/offline data, not graded
│   ├── recommendation_model.py  # Phase 2 ML Pipeline & holdout evaluation
│   └── export_audit_queue.py    # Phase 3 QA script for unmatched prices
├── tests/
│   └── test_phase1_pipeline.py  # end-to-end proof, no API keys needed
├── app.py                       # Phase 3 Streamlit App
├── precision_recall_curve.png   # Generated ML plot
├── requirements.txt
└── .env.example

```

## Setup

```bash
git clone <your-repo-url>
cd game_platform_project
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and paste your free RAWG key from [https://rawg.io/apidocs](https://rawg.io/apidocs)

```

## Running the Complete Pipeline end to end

```bash
# 1. Create the database and tables
python db/setup_database.py

# 2. Pull 1,000–5,000 games from RAWG
python scripts/fetch_rawg_metadata.py --count 3000

# 3. Gather Steam prices (auto-narrows Steam's full catalogue to
#    plausible matches before spending rate-limited requests)
python scripts/fetch_steam_prices.py

# 4. Load Epic Games prices from your downloaded Kaggle CSV
#    (see the docstring in load_epic_dataset.py for dataset links
#    and how to adjust DATASET_COLUMN_MAP to your file's columns)
python scripts/load_epic_dataset.py --csv data/epic_games_store.csv

# 5. Resolve every raw store title to the correct game_id
python scripts/fuzzy_match_games.py

# 6. Run the QA script to export any unmatched prices for review
python scripts/export_audit_queue.py

# 7. Try the summarization engine on any RAWG game_id
python scripts/price_summary_engine.py 3328

# 8. Start the Streamlit Web Application!
streamlit run app.py

```

## Running without API keys (offline demo / grading)

```bash
python db/setup_database.py
python scripts/seed_sample_data.py
python scripts/fuzzy_match_games.py
python scripts/price_summary_engine.py 3328
# -> "Cheapest price is $14.99 on Steam (30% off). Epic Games is $19.99."

```

## Tests

```bash
python -m pytest tests/test_phase1_pipeline.py -v

```

All four tests run against an isolated temporary database seeded with realistic sample data, and verify: fuzzy matching resolves every sample row, the summarization engine picks the true minimum price, single-store games are handled correctly, and unmatched/unknown games fail gracefully instead of crashing the future Streamlit "View Details" button.

## What Phase 2 and Phase 3 can now rely on

* `Games` and `Prices` tables, populated and normalized.
* `get_price_summary(game_id)` — call it directly from the Streamlit "View Details" button; it returns an explanatory `summary_text`.
* `User_Likes` table ready for Phase 3's "Like" button (`session_id`, `game_id`).
* Feature Engineering (Step 2.2) can read `Games.genres`, `Games.metacritic`, and the matched minimum price per game directly from `Prices` via a simple `MIN(price) GROUP BY game_id` query.

```

```
