import sys
import asyncio
import asyncpg
import os
from pathlib import Path

async def main():
    db_url = os.getenv("MARKETFLUX_VNEXT_DATABASE_URL") or os.getenv("FUNDOS_DATABASE_URL")
    if not db_url:
        print("Set MARKETFLUX_VNEXT_DATABASE_URL or FUNDOS_DATABASE_URL before running this script.")
        sys.exit(1)

    print("Connecting to the database...")
    try:
        conn = await asyncpg.connect(db_url)
    except Exception as e:
        print(f"Connection failed: {e}")
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
