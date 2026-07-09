import sqlite3
import pandas as pd
import os
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.neighbors import NearestNeighbors

# Dynamically compute path relative to this script's folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'db', 'game_platform.db'))

def get_ml_recommendations(liked_game_ids, top_n=5):
    """Armin's Phase 2 ML Content-Based Classifier.
    Transforms raw metadata into numerical matrices, creates an on-the-fly 
    user preference vector, and uses scikit-learn's k-NN with Cosine Distance 
    to fetch real-time recommendations.
    """
    if not liked_game_ids:
        return pd.DataFrame()
        
    conn = sqlite3.connect(DB_PATH)
    try:
        # Pull all core parameters required to match features engineered in training
        query = """
            SELECT g.game_id, g.title, g.genres, g.metacritic, MIN(p.price) as price, g.image_url 
            FROM Games g
            INNER JOIN Prices p ON g.game_id = p.game_id
            WHERE g.genres IS NOT NULL AND p.price > 0
            GROUP BY g.game_id
            HAVING COUNT(DISTINCT p.store) = 2;
        """
        df = pd.read_sql_query(query, conn)
    except Exception:
        # Fallback query if image_url or metacritic features are missing from tables
        query = """
            SELECT g.game_id, g.title, g.genres, MIN(p.price) as price
            FROM Games g
            INNER JOIN Prices p ON g.game_id = p.game_id
            WHERE g.genres IS NOT NULL AND p.price > 0
            GROUP BY g.game_id
            HAVING COUNT(DISTINCT p.store) = 2;
        """
        df = pd.read_sql_query(query, conn)
    finally:
        conn.close()

    if df.empty:
        return pd.DataFrame()

    # --- STEP 1: FEATURE ENGINEERING (MATCHING THE TRAINING PIPELINE) ---
    df_ml = df.copy()
    
    # Handle missing or null structural values safely
    if 'metacritic' in df_ml.columns:
        df_ml['metacritic'] = df_ml['metacritic'].fillna(df_ml['metacritic'].mean())
    else:
        df_ml['metacritic'] = 50.0  # Safe fallback if column doesn't exist
        
    df_ml['price'] = df_ml['price'].fillna(0.0)
    
    # Scale numerical values via MinMaxScaler exactly like step 2.2
    scaler = MinMaxScaler()
    df_ml[['metacritic_scaled', 'price_scaled']] = scaler.fit_transform(df_ml[['metacritic', 'price']])
    
    # Multi-label dummy string expansion for Genres matrix mapping
    genres_encoded = df_ml['genres'].str.get_dummies(sep=',')
    
    # Consolidate pure numerical feature vectors
    feature_matrix = pd.concat([
        df_ml[['game_id', 'title', 'metacritic_scaled', 'price_scaled']], 
        genres_encoded
    ], axis=1)
    
    # --- STEP 2: ISOLATING USER HISTORY AND CANDIDATE POOLS ---
    # Convert IDs to strings or common types to prevent mapping mismatch
    feature_matrix['game_id_str'] = feature_matrix['game_id'].astype(str)
    liked_ids_str = [str(uid) for uid in liked_game_ids]
    
    liked_rows = feature_matrix[feature_matrix['game_id_str'].isin(liked_ids_str)]
    
    if liked_rows.empty:
        return pd.DataFrame()
        
    # --- STEP 3: BUILDING USER VECTOR & RUNNING MACHINE LEARNING ---
    # Isolate vector features only (drop identifier metadata columns)
    drop_cols = ['game_id', 'title', 'game_id_str']
    features_only = feature_matrix.drop(columns=drop_cols)
    liked_features_only = liked_rows.drop(columns=drop_cols)
    
    # Create the user profile vector by finding the centroid average of all chosen games
    user_profile_vector = liked_features_only.mean(axis=0).values.reshape(1, -1)
    
    # Instantiate and fit the real Cosine Nearest Neighbors model on the fly
    knn = NearestNeighbors(n_neighbors=min(top_n + len(liked_ids_str), len(df_ml)), metric='cosine')
    knn.fit(features_only)
    
    # Query matrix for vectors displaying closest angular spatial similarity
    distances, indices = knn.kneighbors(user_profile_vector)
    
    # --- STEP 4: FILTERING AND RESULT FORMATTING ---
    recommended_indices = indices[0]
    
    # Map index locations back to the primary structural DataFrame
    recommended_df = df_ml.iloc[recommended_indices].copy()
    
    # Strip out items the user has already liked so recommendations stay unique
    recommended_df['game_id_str'] = recommended_df['game_id'].astype(str)
    final_recommendations = recommended_df[~recommended_df['game_id_str'].isin(liked_ids_str)]
    
    # Return exactly top N candidates formatted for our Streamlit UI
    return final_recommendations.head(top_n)