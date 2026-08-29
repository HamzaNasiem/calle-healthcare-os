import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.core.database import supabase

print("Testing if exec_sql RPC exists...")
try:
    res = supabase.rpc("exec_sql", {"sql_query": "SELECT 1 as val;"}).execute()
    print("  SUCCESS (sql_query):", res.data)
except Exception as e:
    print(f"  Failed with sql_query: {e}")
    try:
        res = supabase.rpc("exec_sql", {"query": "SELECT 1 as val;"}).execute()
        print("  SUCCESS (query):", res.data)
    except Exception as e2:
        print(f"  Failed with query: {e2}")
        try:
            res = supabase.rpc("exec_sql", {"sql": "SELECT 1 as val;"}).execute()
            print("  SUCCESS (sql):", res.data)
        except Exception as e3:
            print(f"  Failed with sql: {e3}")
