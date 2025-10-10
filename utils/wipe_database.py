"""
DANGER: This script will DELETE ALL DATA from the database!
Use only during beta testing when you want a fresh start.
"""
import asyncpg
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def wipe_database():
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)
    print("Connected to database\n")

    print("="*70)
    print("WARNING: THIS WILL DELETE ALL DATA!")
    print("="*70)
    print("\nTables that will be dropped:")

    # Get all tables
    tables = await conn.fetch('''
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public'
    ''')

    for table in tables:
        print(f"  - {table['tablename']}")

    print("\n" + "="*70)
    print("Dropping all tables...")
    print("="*70 + "\n")

    # Drop all tables
    for table in tables:
        table_name = table['tablename']
        print(f"Dropping {table_name}...")
        await conn.execute(f'DROP TABLE IF EXISTS {table_name} CASCADE')

    print("\n" + "="*70)
    print("ALL TABLES DELETED!")
    print("="*70)
    print("\nNext steps:")
    print("1. Restart your bot")
    print("2. setup_database() will recreate all tables with correct structure")
    print("3. Shop will be populated with 5 packs")
    print("4. Fresh start! ✨")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(wipe_database())
