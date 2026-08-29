import psycopg2

host = "aws-1-ap-northeast-1.pooler.supabase.com"
db_user = "postgres.aabbhuzlzjkosqmvhysm"
db_name = "postgres"

passwords = [
    "Bytelytic@2025",
    "Bytelytic@2026",
    "Bytelytic2025",
    "Bytelytic",
    "postgres",
    "password",
    "Bytelytic_2025",
    "Bytelytic2025!",
    "Bytelytic@2025!",
    "SecurePass123!",
    "Bytelytic-2025",
    "Bytelytic@2025#",
    "BytelyticClinicOS@2025",
]

def test_password(password):
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=password,
            host=host,
            port="6543",
            sslmode="require",
            connect_timeout=2
        )
        conn.close()
        print(f"  SUCCESS! Password is: {password}")
        return True
    except Exception as e:
        err_str = str(e)
        if "password authentication failed" in err_str:
            print(f"  Failed for {password}: Incorrect password")
        else:
            print(f"  Failed for {password}: {err_str}")
        return False

if __name__ == "__main__":
    print("Testing candidate database passwords...")
    found = False
    for p in passwords:
        if test_password(p):
            found = True
            break
    if not found:
        print("None of the passwords matched.")
