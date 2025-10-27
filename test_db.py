from db_connect_test import get_connection

try:
    conn = get_connection()
    print("✅ Database connected successfully!")
    cur = conn.cursor()
    cur.execute("SHOW TABLES;")
    for x in cur.fetchall():
        print(x)
    conn.close()
except Exception as e:
    print("❌ Database connection failed:", e)
