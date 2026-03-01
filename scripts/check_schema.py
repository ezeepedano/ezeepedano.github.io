import sqlite3

def check_db():
    try:
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        print("--- Table Info: inventory_ingredient ---")
        cursor.execute("PRAGMA table_info(inventory_ingredient)")
        columns = cursor.fetchall()
        
        found = False
        for col in columns:
            cid, name, type, notnull, dflt_value, pk = col
            print(f"Column: {name} ({type})")
            if name == 'code':
                found = True
                
        if found:
            print("\nSUCCESS: 'code' column EXISTS.")
        else:
            print("\nFAILURE: 'code' column DOES NOT EXIST.")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db()
