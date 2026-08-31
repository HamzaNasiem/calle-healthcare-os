import psycopg2

url = 'postgresql://calle_user:L9zYPT9GzEEcPOV2grP3TtDrX9fXmKwV@dpg-da9dirm7bikc7390tqrg-a.oregon-postgres.render.com:5432/bytelytic_clinic_db?sslmode=require'
conn = psycopg2.connect(url)
cur = conn.cursor()

cur.execute("""
SELECT column_name 
FROM information_schema.columns 
WHERE table_name='calls'
""")
cols = cur.fetchall()
print("Columns in calls table:", [c[0] for c in cols])

cur.execute("""
SELECT id, patient_id, direction, status, campaign_type, created_at 
FROM calls 
WHERE campaign_type='no_show'
ORDER BY created_at DESC LIMIT 5
""")
calls = cur.fetchall()
print('\n4. Calls table for no-show recovery:')
for c in calls:
    print(c)
