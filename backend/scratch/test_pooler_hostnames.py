import socket
import psycopg2

variants = [
    "aws-0-ap-northeast-1.pooler.supabase.com",
    "aws-1-ap-northeast-1.pooler.supabase.com",
    "aws-ap-northeast-1.pooler.supabase.com",
    "aws-0-ap-northeast-1.pooler.supabase.co",
    "aws-1-ap-northeast-1.pooler.supabase.co",
    "aws-ap-northeast-1.pooler.supabase.co",
    "aws-0-ap-northeast-1.pooler.supabase.io",
    "aws-1-ap-northeast-1.pooler.supabase.io",
]

db_user = "postgres.aabbhuzlzjkosqmvhysm"
db_password = "Bytelytic@2025"
db_name = "postgres"

def test_host(host):
    print(f"\nTesting {host}:")
    try:
        ip = socket.gethostbyname(host)
        print(f"  DNS resolves to {ip}")
    except socket.gaierror:
        print("  DNS lookup failed.")
        return

    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=host,
            port="6543",
            sslmode="require",
            connect_timeout=3
        )
        conn.close()
        print("  SUCCESS!")
    except Exception as e:
        print(f"  Connection failed: {e}")

if __name__ == "__main__":
    for host in variants:
        test_host(host)
