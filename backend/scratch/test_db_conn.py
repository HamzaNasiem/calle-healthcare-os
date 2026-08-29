import os
import psycopg2

def test_connection():
    db_url = "postgresql://postgres:Bytelytic%402025@localhost:5432/postgres"
    print("Testing connection with URL:")
    print(db_url.split("@")[1]) # print host/port/db part only for safety
    try:
        conn = psycopg2.connect(db_url)
        print("Connection Success!")
        cur = conn.cursor()
        cur.execute("SELECT version();")
        print("Database version:", cur.fetchone())
        cur.close()
        conn.close()
    except Exception as e:
        print("Connection Failed:", e)

if __name__ == "__main__":
    test_connection()
