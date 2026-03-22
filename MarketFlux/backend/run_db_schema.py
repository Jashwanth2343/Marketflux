import sys
import asyncio
import asyncpg
from pathlib import Path

async def main():
    # URL provided by user
    db_url = "postgresql://postgres.hsmcuvimxwbkrzojgjkr:Mainnet%2343%23@aws-1-us-east-2.pooler.supabase.com:6543/postgres"
    print("Connecting to the database...")
    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
        # Retrying password encoding just in case
        print("Retrying alternative password URL encoding...")
        try:
            db_url_2 = "postgresql://postgres.hsmcuvimxwbkrzojgjkr:Mainnet%252343%23@aws-1-us-east-2.pooler.supabase.com:6543/postgres"
            conn = await asyncpg.connect(db_url_2)
        except Exception as e2:
            print(f"Failed again: {e2}")
            sys.exit(1)
        
    print("Connected successfully. Enabling pgvector...")
    await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    row = await conn.fetchrow("SELECT * FROM pg_extension WHERE extname = 'vector';")
    if row:
        print("pgvector extension status: INSTALLED")
    
    print("Reading schema file...")
    schema_sql = Path("sql/vnext_pgvector_schema.sql").read_text()
    
    print("Executing schema...")
    await conn.execute(schema_sql)
    
    print("\nSchema applied successfully!")
    
    # Query tables to verify
    tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
    print("Tables created:")
    for t in tables:
        print(f"- {t['tablename']}")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
