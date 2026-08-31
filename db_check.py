import psycopg2
from datetime import datetime, timezone

url = 'postgresql://calle_user:L9zYPT9GzEEcPOV2grP3TtDrX9fXmKwV@dpg-da9dirm7bikc7390tqrg-a.oregon-postgres.render.com:5432/bytelytic_clinic_db?sslmode=require'
conn = psycopg2.connect(url)
cur = conn.cursor()

print('--- Ground Truth Check ---')

cur.execute("""
SELECT id, patient_name, datetime, status 
FROM appointments 
WHERE status='no_show' 
AND DATE(datetime) = CURRENT_DATE
""")
no_shows = cur.fetchall()
print(f'1. Today no_shows count: {len(no_shows)}')
for row in no_shows:
    print(f'   - {row[1]} at {row[2]} (id: {row[0]})')

cur.execute("""
SELECT id, patient_name, datetime, status 
FROM appointments 
WHERE status='no_show' 
AND DATE(datetime) = CURRENT_DATE
AND datetime <= NOW() - INTERVAL '2 hours'
""")
eligible = cur.fetchall()
print(f'\n2. Eligible for recovery (2+ hours ago): {len(eligible)}')
for row in eligible:
    print(f'   - {row[1]} at {row[2]} (id: {row[0]})')

print('\n3. Emily and Robert check:')
for row in no_shows:
    if 'Emily' in row[1] or 'Robert' in row[1]:
        print(f'   - {row[1]} found at {row[2]}')

cur.execute("""
SELECT id, patient_id, direction, status, ai_summary, duration_seconds, created_at 
FROM calls 
WHERE campaign_type='no_show'
ORDER BY created_at DESC LIMIT 5
""")
calls = cur.fetchall()
print(f'\n4. Calls table for no-show recovery:')
for c in calls:
    print(c)
