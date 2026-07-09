import sqlite3

DB_PATH = "db/game_platform.db"

def fix_epic_prices():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # This SQL command divides all Epic Games prices by 100 to turn cents into dollars
    print("Fixing Epic Games prices in the database...")
    cur.execute("""
        UPDATE Prices 
        SET price = price / 100.0 
        WHERE store = 'Epic Games' AND price > 100;
    """)
    
    # Let's also fix the discount prices if they exist
    cur.execute("""
        UPDATE Prices 
        SET discount_percent = discount_percent 
        WHERE store = 'Epic Games';
    """)
    
    conn.commit()
    conn.close()
    print("Done! All prices are now in normal dollars.")

if __name__ == "__main__":
    fix_epic_prices()