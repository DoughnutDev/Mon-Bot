"""
Check the current structure of user_packs table
"""
import asyncpg
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def check_structure():
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)
    print("Connected to database\n")

    # Get all columns
    columns = await conn.fetch('''
        SELECT column_name, data_type, column_default, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'user_packs'
        ORDER BY ordinal_position
    ''')

    print("user_packs table structure:")
    print("="*70)
    for col in columns:
        print(f"{col['column_name']:20} {col['data_type']:15} Default: {col['column_default']}")

    # Check for primary keys
    print("\nPrimary keys:")
    print("="*70)
    pks = await conn.fetch('''
        SELECT a.attname AS column_name
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = 'user_packs'::regclass
        AND i.indisprimary
    ''')

    for pk in pks:
        print(f"  - {pk['column_name']}")

    # Check if there are any rows
    count = await conn.fetchval('SELECT COUNT(*) FROM user_packs')
    print(f"\nTotal rows in user_packs: {count}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_structure())
