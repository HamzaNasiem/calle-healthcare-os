import psycopg2

conn = psycopg2.connect("postgresql://calle_user:L9zYPT9GzEEcPOV2grP3TtDrX9fXmKwV@dpg-da9dirm7bikc7390tqrg-a.oregon-postgres.render.com:5432/bytelytic_clinic_db?sslmode=require")
cur = conn.cursor()

for tbl in ["calls", "call_logs"]:
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{tbl}' 
        ORDER BY ordinal_position;
    """)
    print(f"\n=== {tbl} COLUMNS ===")
    for c in cur.fetchall():
        print(f"  {c[0]} ({c[1]})")

cur.close()
conn.close()
