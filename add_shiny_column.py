"""
Database migration: Add is_shiny column to catches table

Run this once to update your production database with the shiny column.
Usage: python add_shiny_column.py
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()


async def migrate():
    """Add is_shiny column to catches table"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not found in environment variables")
        return

    try:
        print("Connecting to database...")
        conn = await asyncpg.connect(database_url)

        print("Adding is_shiny column to catches table...")
        await conn.execute('''
            ALTER TABLE catches
            ADD COLUMN IF NOT EXISTS is_shiny BOOLEAN DEFAULT FALSE
        ''')

        print("Successfully added is_shiny column!")
        print("All existing Pokemon are marked as non-shiny (is_shiny = FALSE)")

        await conn.close()
        print("Database connection closed.")

    except Exception as e:
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("=== Database Migration: Add Shiny Column ===")
    asyncio.run(migrate())
    print("=== Migration Complete ===")
