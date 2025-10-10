"""
Migration script to add id column to user_packs table
"""
import asyncpg
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def fix_user_packs_table():
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)
    print("Connected to database\n")

    try:
        # Check if id column exists
        column_exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'user_packs'
                AND column_name = 'id'
            )
        ''')

        if column_exists:
            print("Column 'id' already exists in user_packs table")
        else:
            print("Adding 'id' column to user_packs table...")

            # Add id column as SERIAL
            await conn.execute('''
                ALTER TABLE user_packs
                ADD COLUMN id SERIAL PRIMARY KEY
            ''')

            print("Column added successfully!")

        # Verify the table structure
        columns = await conn.fetch('''
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'user_packs'
            ORDER BY ordinal_position
        ''')

        print("\nuser_packs table structure:")
        print("="*50)
        for col in columns:
            print(f"  {col['column_name']}: {col['data_type']}")

        await conn.close()
        print("\nMigration complete!")

    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_user_packs_table())
