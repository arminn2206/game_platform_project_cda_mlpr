import streamlit as st
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scripts.price_summary_engine import get_price_summary
from scripts.recommendation_engine import get_ml_recommendations

DB_PATH = "db/game_platform.db"

# --- STEP 3.1: INITIALIZE THE WEB APP ---
st.set_page_config(page_title="GameRecommender Pro", page_icon="🎮", layout="wide")

# Initialize Session State to remember User Likes
if 'liked_games' not in st.session_state:
    st.session_state.liked_games = []

@st.cache_data
def load_games(search_term=""):
    """Queries database for games with valid prices from BOTH stores."""
    conn = sqlite3.connect(DB_PATH)
    try:
        if search_term:
            query = """
                SELECT g.game_id, g.title, g.genres, g.image_url 
                FROM Games g
                INNER JOIN Prices p ON g.game_id = p.game_id
                WHERE p.price > 0 AND g.title LIKE ?
                GROUP BY g.game_id
                HAVING COUNT(DISTINCT p.store) = 2
                LIMIT 48;
            """
            df = pd.read_sql_query(query, conn, params=('%' + search_term + '%',))
        else:
            query = """
                SELECT g.game_id, g.title, g.genres, g.image_url 
                FROM Games g
                INNER JOIN Prices p ON g.game_id = p.game_id
                WHERE p.price > 0
                GROUP BY g.game_id
                HAVING COUNT(DISTINCT p.store) = 2
                ORDER BY RANDOM()
                LIMIT 24;
            """
            df = pd.read_sql_query(query, conn)
    except Exception:
        # Fallback query if image_url is missing
        if search_term:
            query = """
                SELECT g.game_id, g.title, g.genres 
                FROM Games g
                INNER JOIN Prices p ON g.game_id = p.game_id
                WHERE p.price > 0 AND g.title LIKE ?
                GROUP BY g.game_id
                HAVING COUNT(DISTINCT p.store) = 2
                LIMIT 48;
            """
            df = pd.read_sql_query(query, conn, params=('%' + search_term + '%',))
        else:
            query = """
                SELECT g.game_id, g.title, g.genres 
                FROM Games g
                INNER JOIN Prices p ON g.game_id = p.game_id
                WHERE p.price > 0
                GROUP BY g.game_id
                HAVING COUNT(DISTINCT p.store) = 2
                ORDER BY RANDOM()
                LIMIT 24;
            """
            df = pd.read_sql_query(query, conn)
    conn.close()
    return df

@st.cache_data
def get_search_suggestions():
    """Fetches a list of all game titles that have both prices for the autocomplete search."""
    conn = sqlite3.connect(DB_PATH)
    try:
        query = """
            SELECT g.title 
            FROM Games g
            INNER JOIN Prices p ON g.game_id = p.game_id
            WHERE p.price > 0
            GROUP BY g.game_id
            HAVING COUNT(DISTINCT p.store) = 2
            ORDER BY g.title;
        """
        titles = pd.read_sql_query(query, conn)['title'].tolist()
    except Exception:
        titles = []
    finally:
        conn.close()
    return titles

# --- SIDEBAR PROFILE & NAVIGATION ---
st.sidebar.title("👤 Your Profile")
st.sidebar.write(f"**Liked Games:** {len(st.session_state.liked_games)}")

if st.sidebar.button("Clear Likes"):
    st.session_state.liked_games = []
    st.rerun()

st.sidebar.divider()
st.sidebar.title("🧭 Navigation")
app_page = st.sidebar.radio("Go to:", [
    "🎮 Game Explorer", 
    "✨ For You (Recommendations)",
    "📊 Admin & ML Metrics"
])


# --- PAGE 1: GAME EXPLORER ---
if app_page == "🎮 Game Explorer":
    st.title("🎮 Game Explorer")
    st.markdown("Browse the database. Click **View Details** to check prices, and **Like** games to build your taste profile!")

    all_titles = get_search_suggestions()
    search_query = st.selectbox("🔍 Search for a game (start typing)...", options=[""] + all_titles, index=0)
    games_df = load_games(search_query)

    if games_df.empty:
        st.warning("No games found with valid pricing for that search. Try another title!")
    else:
        cols = st.columns(4)
        for index, row in games_df.iterrows():
            col = cols[index % 4]
            with col:
                with st.container(height=580, border=True):
                    display_title = row['title']
                    if len(display_title) > 22:
                        display_title = display_title[:19] + "..."
                        
                    st.subheader(display_title, help=row['title'])
                    
                    if 'image_url' in row and pd.notna(row['image_url']):
                        st.image(row['image_url'], use_column_width=True)
                    else:
                        st.image("https://via.placeholder.com/300x400?text=No+Poster", use_container_width=True)
                        
                    st.caption(f"**Genres:** {row['genres'][:30]}...")
                    
                    if row['game_id'] in st.session_state.liked_games:
                        st.button("❤️ Liked", key=f"like_{row['game_id']}", disabled=True, use_container_width=True)
                    else:
                        if st.button("🤍 Like", key=f"like_{row['game_id']}", use_container_width=True):
                            st.session_state.liked_games.append(row['game_id'])
                            st.rerun() 
                            
                    if st.button("View Details", key=f"details_{row['game_id']}", use_container_width=True):
                        with st.spinner("Fetching..."):
                            summary_text = get_price_summary(row['game_id'])
                            st.success(summary_text)


# --- PAGE 2: MACHINE LEARNING RECOMMENDATIONS ---
elif app_page == "✨ For You (Recommendations)":
    st.title("✨ Personalized Recommendations")
    st.markdown("Our Phase 2 Content-Based ML Classifier evaluates your favorite features to generate these real-time selections.")

    if not st.session_state.liked_games:
        st.info("💡 Your recommendation engine is empty! Go back to the **Game Explorer** page and click '🤍 Like' on a few titles first.")
    else:
        with st.spinner("Running ML classifier matrix matching..."):
            rec_df = get_ml_recommendations(st.session_state.liked_games, top_n=5)
            
        if rec_df.empty:
            st.error("We couldn't generate recommendations based on those criteria. Try liking different genres!")
        else:
            st.success(f"🎯 Found {len(rec_df)} perfect recommendations matching your profile vector!")

            csv_data = rec_df[['title', 'genres', 'price']].to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Recommendations (CSV)",
                data=csv_data,
                file_name="my_game_recommendations.csv",
                mime="text/csv",
            )

            rec_cols = st.columns(len(rec_df))
            for idx, (_, row) in enumerate(rec_df.iterrows()):
                with rec_cols[idx]:
                    with st.container(height=580, border=True):
                        display_title = row['title']
                        if len(display_title) > 20:
                            display_title = display_title[:17] + "..."
                            
                        st.subheader(display_title, help=row['title'])
                        
                        if 'image_url' in row and pd.notna(row['image_url']):
                            st.image(row['image_url'], use_container_width=True)
                        else:
                            st.image("https://via.placeholder.com/300x400?text=No+Poster", use_container_width=True)
                            
                        st.caption(f"**Genres:** {row['genres'][:30]}...")
                        
                        if st.button("Check Price", key=f"rec_price_{row['game_id']}", use_container_width=True):
                            price_text = get_price_summary(row['game_id'])
                            st.info(price_text)
# --- PAGE 3: ADMIN & ML METRICS ---
elif app_page == "📊 Admin & ML Metrics":
    st.title("📊 System Analytics & ML Metrics")
    st.markdown("Live view of the database health and Phase 2 Recommendation Model performance.")
    
    # 1. Database Health
    st.subheader("Database Overview")
    conn = sqlite3.connect(DB_PATH)
    total_games = pd.read_sql_query("SELECT COUNT(*) as cnt FROM Games", conn).iloc[0]['cnt']
    total_prices = pd.read_sql_query("SELECT COUNT(*) as cnt FROM Prices", conn).iloc[0]['cnt']
    conn.close()
    
    col1, col2 = st.columns(2)
    col1.metric(label="Total Games in Catalog", value=f"{total_games:,}")
    col2.metric(label="Total Price Records Fetched", value=f"{total_prices:,}")
    
    # 2. ML Metrics
    st.subheader("Machine Learning Performance")
    
    import os
    import subprocess
    import re
    
    # Use Session State to "remember" the numbers so they don't disappear
    if 'ml_metrics' not in st.session_state:
        st.session_state.ml_metrics = None
        
    # The interactive button
    if st.button("🚀 Run ML Evaluation Pipeline"):
        with st.spinner("Executing model evaluation (this may take a minute)..."):
            try:
                result = subprocess.run(
                    ["python", "scripts/recommendation_model.py"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                
                # --- AUTOMATIC TEXT EXTRACTION ---
                # Search the terminal text for your exact metric numbers
                stdout = result.stdout
                p_match = re.search(r"Precision @ 5:\s+([0-9.]+)", stdout)
                r_match = re.search(r"Recall @ 5:\s+([0-9.]+)", stdout)
                f_match = re.search(r"F1-Score @ 5:\s+([0-9.]+)", stdout)
                
                if p_match and r_match and f_match:
                    st.session_state.ml_metrics = {
                        "precision": p_match.group(1),
                        "recall": r_match.group(1),
                        "f1": f_match.group(1)
                    }
                    st.success("✅ Model evaluation complete! Metrics extracted.")
                else:
                    st.warning("Script ran, but couldn't parse the exact numbers from the output.")
                    st.code(stdout, language="text")

            except subprocess.CalledProcessError as e:
                st.error("Failed to run the script.")
                st.code(e.stderr, language="text")

# --- RENDER THE UI ---
    # Display the numbers AND the image ONLY if we have them in memory (after button click)
    if st.session_state.ml_metrics:
        
        # 1. Show the metrics
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.metric(label="Precision @ 5", value=st.session_state.ml_metrics["precision"])
        m_col2.metric(label="Recall @ 5", value=st.session_state.ml_metrics["recall"])
        m_col3.metric(label="F1-Score @ 5", value=st.session_state.ml_metrics["f1"])
        st.info("💡 *These metrics were generated by executing our k-NN model against the strict 60/20/20 holdout split from the Kaggle dataset.*")

        # 2. Show the image
        plot_path = "precision_recall_curve.png"
        if os.path.exists(plot_path):
            st.write("---") # Adds a nice subtle divider line
            
            # We create 3 columns to perfectly center the image
            spacer_left, img_col, spacer_right = st.columns([1, 2, 1])
            
            with img_col:
                st.image(plot_path, caption="Phase 2: Technical Precision-Recall Curve", use_container_width=True)
                
    # If the button hasn't been clicked yet, show this warning instead
    else:
        st.warning("No metrics found. Click the button above to generate them!")
