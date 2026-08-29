"""Quick DB check script — lists all tables and counts."""
import asyncio
import asyncpg

async def main():
    # Session pooler supports prepared statements
    conn = await asyncpg.connect(
        host="aws-0-ap-northeast-1.pooler.supabase.com",
        port=5432,
        user="postgres.bdkinditdmppgucsuqpg",
        password="Bytelytic@2026!",
        database="postgres",
        ssl="require",
        statement_cache_size=0,
    )
    print("Connected OK!")
    rows = await conn.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    )
    print(f"\nTABLES ({len(rows)} total):")
    for r in rows:
        name = r["tablename"]
        try:
            count = await conn.fetchval(f'SELECT COUNT(*) FROM "{name}"')
            print(f"  {name:<40} rows={count}")
        except Exception:
            print(f"  {name}")
    await conn.close()

asyncio.run(main())
