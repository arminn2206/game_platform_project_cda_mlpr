import sqlite3
import pandas as pd
import os
import numpy as np
import matplotlib.pyplot as plt
import warnings
import json

# Quiet down scikit-learn's feature name warnings
warnings.filterwarnings("ignore", category=UserWarning)

from sklearn.preprocessing import MinMaxScaler
from sklearn.neighbors import NearestNeighbors

# FIXED PATHS: Dynamically compute paths relative to this script's directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "db", "game_platform.db"))
STEAM_CSV_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "data", "steam-200k.csv"))

def load_data():
    """Loads both the Database and the Kaggle User Interaction dataset."""
    print("1. Loading Game Metadata and Prices from Database...")
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT g.game_id, g.title, g.genres, g.metacritic, MIN(p.price) as price
        FROM Games g
        LEFT JOIN Prices p ON g.game_id = p.game_id
        WHERE g.genres IS NOT NULL
        GROUP BY g.game_id;
    """
    df_games = pd.read_sql_query(query, conn)
    conn.close()
    
    print("2. Loading User Interactions (Steam 200k Dataset)...")
    col_names = ['user_id', 'game_title', 'behavior', 'value', 'zero_column']
    interactions = pd.read_csv(STEAM_CSV_PATH, names=col_names)
    interactions = interactions.drop(columns=['zero_column'])
    
    return df_games, interactions

def preprocess_features(df_games):
    """Turns text genres into 1s and 0s, and scales Prices and Metacritic scores (Step 2.2)."""
    print("3. Executing Feature Engineering...")
    df_games = df_games.dropna(subset=['price']).copy()
    df_games['metacritic'] = df_games['metacritic'].fillna(df_games['metacritic'].mean())
    
    scaler = MinMaxScaler()
    df_games[['metacritic_scaled', 'price_scaled']] = scaler.fit_transform(df_games[['metacritic', 'price']])
    
    genres_encoded = df_games['genres'].str.get_dummies(sep=',')
    feature_matrix = pd.concat([df_games[['game_id', 'title', 'metacritic_scaled', 'price_scaled']], genres_encoded], axis=1)
    
    return df_games, feature_matrix

def train_knn_model(feature_matrix):
    """Initializes and fits the k-NN model on the mathematical features (Step 2.3)."""
    print("4. Training k-NN Classifier (Cosine Distance Metric)...")
    features_only = feature_matrix.drop(columns=['game_id', 'title'])
    knn = NearestNeighbors(n_neighbors=20, metric='cosine') 
    knn.fit(features_only)
    return knn

def evaluate_model_holdout(interactions, df_games, feature_matrix, knn_model):
    """Performs a strict 60/20/20 Holdout evaluation and saves a Precision-Recall Curve (Step 2.4)."""
    print("\n5. Starting Rigorous Model Evaluation (60/20/20 Split)...")
    
    interactions['title_clean'] = interactions['game_title'].str.lower().str.replace(r'[^a-z0-9]', '', regex=True)
    df_games['title_clean'] = df_games['title'].str.lower().str.replace(r'[^a-z0-9]', '', regex=True)
    
    mapped_data = interactions.merge(df_games[['game_id', 'title_clean']], on='title_clean', how='inner')
    user_game_counts = mapped_data.groupby('user_id')['game_id'].nunique()
    valid_users = user_game_counts[user_game_counts >= 4].index.values.copy()
    
    if len(valid_users) == 0:
        print("Error: Not enough overlapping games between Kaggle dataset and database to evaluate.")
        return
        
    np.random.seed(42)
    np.random.shuffle(valid_users)
    train_split = int(0.6 * len(valid_users))
    val_split = int(0.8 * len(valid_users))
    
    test_users = valid_users[val_split:]
    print(f"   Total evaluatable users found: {len(valid_users)}")
    print(f"   60% Train Users: {train_split} | 20% Val Users: {val_split - train_split} | 20% Test Users: {len(test_users)}")
    
    sample_test_users = np.random.choice(test_users, min(250, len(test_users)), replace=False)
    
    n_cutoffs = [1, 3, 5, 10, 15, 20]
    avg_precisions = []
    avg_recalls = []
    
    for N in n_cutoffs:
        user_precisions = []
        user_recalls = []
        
        for user in sample_test_users:
            user_history = mapped_data[mapped_data['user_id'] == user]['game_id'].unique()
            split_point = len(user_history) // 2
            known_likes = user_history[:split_point]
            hidden_likes = set(user_history[split_point:])
            
            liked_rows = feature_matrix[feature_matrix['game_id'].isin(known_likes)]
            liked_features = liked_rows.drop(columns=['game_id', 'title'])
            user_profile_vector = liked_features.mean(axis=0).values.reshape(1, -1)
            
            distances, indices = knn_model.kneighbors(user_profile_vector, n_neighbors=N+len(known_likes))
            
            recommended_indices = indices[0]
            recs = feature_matrix.iloc[recommended_indices]['game_id'].values
            
            # Filter out known likes and keep top N
            recs_filtered = list(dict.fromkeys([r for r in recs if r not in known_likes]))[:N]
            
            set_recs = set(recs_filtered)
            set_hidden = set(hidden_likes)
            
            # True Positives
            hits = len(set_recs.intersection(set_hidden))
            
            actual_recs_count = len(set_recs)
            precision = hits / actual_recs_count if actual_recs_count > 0 else 0
            
            total_hidden_count = len(set_hidden)
            recall = hits / total_hidden_count if total_hidden_count > 0 else 0
            
            user_precisions.append(precision)
            user_recalls.append(recall)
            
        avg_precisions.append(np.mean(user_precisions))
        avg_recalls.append(np.mean(user_recalls))

    p_at_5 = avg_precisions[n_cutoffs.index(5)]
    r_at_5 = avg_recalls[n_cutoffs.index(5)]
    f1_at_5 = (2 * p_at_5 * r_at_5) / (p_at_5 + r_at_5) if (p_at_5 + r_at_5) > 0 else 0
    
    print("\n--- RIGOROUS MODEL METRICS (At Top 5 Recommendations) ---")
    print(f"   Precision @ 5: {p_at_5:.4f}")
    print(f"   Recall @ 5:    {r_at_5:.4f}")
    print(f"   F1-Score @ 5:  {f1_at_5:.4f}")
    
    plt.figure(figsize=(7, 5))
    plt.plot(avg_recalls, avg_precisions, marker='o', color='b', linestyle='-', linewidth=2)
    plt.title("MLPR Technical Precision-Recall Curve")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.grid(True, linestyle='--', alpha=0.6)
    
    for i, txt in enumerate(n_cutoffs):
        plt.annotate(f"N={txt}", (avg_recalls[i], avg_precisions[i]), textcoords="offset points", xytext=(0,10), ha='center')
        
    # Plot saved successfully
    plot_filename = os.path.abspath(os.path.join(BASE_DIR, "..", "precision_recall_curve.png"))
    plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\n Saved official Precision-Recall Curve plot as: '{plot_filename}'")

    # JSON saving block
    metrics_data = {
        "precision": round(float(p_at_5), 4),
        "recall": round(float(r_at_5), 4),
        "f1_score": round(float(f1_at_5), 4),
        "f1": round(float(f1_at_5), 4),  # Backup key for app compatibility
        "recall_curve_points": [round(float(x), 4) for x in avg_recalls],
        "precision_curve_points": [round(float(x), 4) for x in avg_precisions]
    }
    
    json_path = os.path.abspath(os.path.join(BASE_DIR, "..", "model_metrics.json"))
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=4)
        
    print(f" Saved official metrics JSON as: '{json_path}'")


if __name__ == "__main__":
    df_games, interactions = load_data()
    df_games_clean, features = preprocess_features(df_games)
    knn = train_knn_model(features)
    evaluate_model_holdout(interactions, df_games_clean, features, knn)
