import psycopg2

conn = psycopg2.connect('postgresql://calle_user:L9zYPT9GzEEcPOV2grP3TtDrX9fXmKwV@dpg-da9dirm7bikc7390tqrg-a.oregon-postgres.render.com:5432/bytelytic_clinic_db?sslmode=require')
cur = conn.cursor()

print("--- Appointments within 36 hours ---")
cur.execute("SELECT id, patient_id, patient_phone, datetime, status FROM appointments WHERE status='scheduled' AND datetime BETWEEN NOW() AND NOW() + interval '36 hours';")
rows = cur.fetchall()
for r in rows:
    print(r)
    
print("Total:", len(rows))

print("--- Outbound Calls ---")
cur.execute("SELECT id, campaign_type, status, appointment_id FROM outbound_calls LIMIT 10;")
print(cur.fetchall())

try:
    print("--- Calls ---")
    cur.execute("SELECT id, direction, call_type FROM calls LIMIT 10;")
    print(cur.fetchall())
except Exception as e:
    print("Error querying calls:", e)

conn.close()
