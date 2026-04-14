import asyncio
import os
import sys
from pathlib import Path

# Add parent dir to sys.path to allow importing app modules if needed
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def test_conn():
    # Use the actual DATABASE_URL from settings
    db_url = settings.DATABASE_URL
    print(f"Testing connection to: {db_url}")
    
    engine = create_async_engine(db_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version();"))
            row = result.fetchone()
            print(f"Connection Successful! Postgres version: {row[0]}")
            
            # Check for tables
            result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public';"))
            tables = [r[0] for r in result.fetchall()]
            print(f"Tables found in current DB: {tables}")
            
            # Check for other databases
            result = await conn.execute(text("SELECT datname FROM pg_database WHERE datistemplate = false;"))
            dbs = [r[0] for r in result.fetchall()]
            print(f"All databases on this server: {dbs}")
            
    except Exception as e:
        print(f"ERROR: Could not connect to database: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_conn())
