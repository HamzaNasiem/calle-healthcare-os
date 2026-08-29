import psycopg2
import socket

ipv6_addr = "2406:da14:311:1500:39d5:563c:41b0:6f"
hostname = "db.aabbhuzlzjkosqmvhysm.supabase.co"
db_user = "postgres"
db_password = "Bytelytic@2025"
db_name = "postgres"

def test_conn(host, port):
    print(f"\nTesting connection to {host} on port {port}...")
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=host,
            port=port,
            sslmode="require",
            connect_timeout=5
        )
        conn.close()
        print("  SUCCESS!")
    except Exception as e:
        print(f"  Failed: {e}")

if __name__ == "__main__":
    # Test IPv6 address directly
    test_conn(ipv6_addr, "5432")
    test_conn(ipv6_addr, "6543")
    
    # Test resolved hostname
    test_conn(hostname, "5432")
    test_conn(hostname, "6543")
