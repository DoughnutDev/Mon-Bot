"""
Add UNIQUE constraint to shop_items.item_name column
This allows ON CONFLICT (item_name) DO NOTHING to work properly
"""
import asyncpg
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def add_constraint():
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)
    print("Connected to database\n")

    try:
        # Check if constraint already exists
        constraint_exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'shop_items_item_name_key'
            )
        ''')

        if constraint_exists:
            print("UNIQUE constraint already exists on item_name")
        else:
            print("Adding UNIQUE constraint to item_name...")

            # Add UNIQUE constraint
            await conn.execute('''
                ALTER TABLE shop_items
                ADD CONSTRAINT shop_items_item_name_key UNIQUE (item_name)
            ''')

            print("UNIQUE constraint added successfully!")

        # Verify the constraint
        print("\nVerifying constraint...")
        constraints = await conn.fetch('''
            SELECT conname, contype
            FROM pg_constraint
            WHERE conrelid = 'shop_items'::regclass
        ''')

        print("\nConstraints on shop_items:")
        print("="*50)
        for c in constraints:
            constraint_type = {
                'p': 'PRIMARY KEY',
                'u': 'UNIQUE',
                'f': 'FOREIGN KEY',
                'c': 'CHECK'
            }.get(c['contype'], c['contype'])
            print(f"  {c['conname']}: {constraint_type}")

        await conn.close()
        print("\nMigration complete!")
        print("Restart your bot to populate shop items.")

    except Exception as e:
        print(f"\nMigration failed: {e}")
        import traceback
        traceback.print_exc()
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_constraint())
