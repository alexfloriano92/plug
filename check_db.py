import sqlite3
conn = sqlite3.connect(r'C:\Users\User\Documents\Clientes-plug\clientes\prospector.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Tables:", tables)
for t in tables:
    print(f"\n--- {t[0]} ---")
    cursor.execute(f"SELECT * FROM {t[0]}")
    rows = cursor.fetchall()
    # Get column names
    cols = [desc[0] for desc in cursor.description]
    print("Columns:", cols)
    for row in rows:
        print(row)
conn.close()
