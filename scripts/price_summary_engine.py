import sqlite3
import os

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'db', 'game_platform.db'))

def get_price_summary(game_id):
    """Fetches and compares prices across all stores (Steam, Epic) from the local database."""
    try:
        safe_int_id = int(game_id) if str(game_id).isdigit() else game_id
        safe_str_id = str(game_id)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT title FROM Games WHERE game_id = ? OR game_id = ?", (safe_int_id, safe_str_id))
        title_row = cursor.fetchone()
        if not title_row:
            conn.close()
            return "Game not found."
        title = title_row[0]
        
        # --- THE FIX: We use MIN(price) and GROUP BY store to hide duplicate deluxe editions ---
        cursor.execute("""
            SELECT store, MIN(price) 
            FROM Prices 
            WHERE (game_id = ? OR game_id = ?) AND price IS NOT NULL
            GROUP BY store
        """, (safe_int_id, safe_str_id))
        prices = cursor.fetchall()
        conn.close()
        
        if not prices:
            return f"No pricing data available for **{title}** in the database."
        
        summary_lines = [f"📊 **Price Comparison for {title}:**"]
        
        for store, price in prices:
            if price == 0:
                summary_lines.append(f" - **{store}:** Free to Play 🆓")
            else:
                summary_lines.append(f" - **{store}:** ${price:.2f} 💰")
                
        return "\n".join(summary_lines)
            
    except Exception as e:
        return f"Database error: {str(e)}"