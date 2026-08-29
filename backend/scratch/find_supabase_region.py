import psycopg2
import socket

REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2",
    "ap-south-1", "eu-west-1", "eu-west-2", "eu-west-3",
    "eu-central-1", "ca-central-1", "sa-east-1"
]

def test_region(region):
    db_host = f"aws-0-{region}.pooler.supabase.com"
    db_user = "postgres.aabbhuzlzjkosqmvhysm"
    db_password = "Bytelytic@2025"
    db_name = "postgres"
    
    print(f"Testing {region} ({db_host})...")
    # First check DNS resolution
    try:
        ip = socket.gethostbyname(db_host)
        print(f"  DNS resolves to {ip}")
    except socket.gaierror:
        print("  DNS lookup failed.")
        return False

    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port="6543",
            sslmode="require",
            connect_timeout=3
        )
        conn.close()
        print(f"  SUCCESS connected to {region}!")
        return True
    except Exception as e:
        print(f"  Connection failed: {e}")
        return False

def main():
    print("Testing pooler regions...")
    successful_regions = []
    for region in REGIONS:
        if test_region(region):
            successful_regions.append(region)
            break
            
    if successful_regions:
        print(f"\nFound successful region(s): {successful_regions}")
    else:
        print("\nNo region poolers succeeded.")

if __name__ == "__main__":
    main()
