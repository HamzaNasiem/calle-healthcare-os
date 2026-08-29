import os
import sys
import psycopg2

def apply_sql_file(cursor, file_path):
    print(f"Applying migration: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        sql = f.read()
    try:
        # Execute the raw SQL commands
        cursor.execute(sql)
        print(f"[SUCCESS] Applied {file_path}")
    except Exception as e:
        print(f"[ERROR] Failed applying {file_path}: {e}")
        raise e

def main():
    db_password = "Bytelytic@2025"
    db_host = "db.aabbhuzlzjkosqmvhysm.supabase.co"
    db_user = "postgres"
    db_name = "postgres"
    db_port = "5432"

    print("Connecting to Supabase Database...")
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            sslmode="require"
        )
        conn.autocommit = True
        cursor = conn.cursor()
        print("Connected successfully.")
    except Exception as e:
        print(f"Database Connection Failed: {e}")
        sys.exit(1)

    # List of SQL files to apply
    migrations = [
        "src/db/migrations/create_clinic_users.sql",
        "src/db/migrations/create_security_tables.sql",
        "src/db/migrations/create_distributed_locks.sql"
    ]

    for m in migrations:
        try:
            apply_sql_file(cursor, m)
        except Exception as e:
            print(f"Aborting migration execution due to error: {e}")
            cursor.close()
            conn.close()
            sys.exit(1)

    cursor.close()
    conn.close()
    print("\nAll database migrations applied successfully!")

if __name__ == "__main__":
    main()
