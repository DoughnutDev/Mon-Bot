import asyncpg
import os
import asyncio


async def migrate_database():
    """Add pack_config column to shop_items table"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        print("Connected to database")

        # Check if column exists
        column_exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'shop_items'
                AND column_name = 'pack_config'
            )
        ''')

        if column_exists:
            print("Column 'pack_config' already exists in shop_items table")
        else:
            print("Adding 'pack_config' column to shop_items table...")

            # Add the column
            await conn.execute('''
                ALTER TABLE shop_items
                ADD COLUMN pack_config JSONB
            ''')

            print("Column added successfully!")

        # Close connection
        await conn.close()
        print("Migration complete!")

    except Exception as e:
        print(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(migrate_database())
