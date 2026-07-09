import sqlite3
import pandas as pd
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'db', 'game_platform.db'))

def export_unmatched_prices():
    conn = sqlite3.connect(DB_PATH)
    
    # Select all prices that failed the fuzzy matcher (game_id IS NULL)
    query = """
        SELECT store, store_game_title, price, url 
        FROM Prices 
        WHERE game_id IS NULL
        ORDER BY store, store_game_title;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print("✅ Awesome! There are no unmatched prices in the database.")
    else:
        export_path = "unmatched_audit_queue.csv"
        df.to_csv(export_path, index=False)
        print(f"⚠️ Found {len(df)} unmatched prices. Exported to '{export_path}' for manual human review.")

if __name__ == "__main__":
    export_unmatched_prices()