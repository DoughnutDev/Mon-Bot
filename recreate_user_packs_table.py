"""
Recreate user_packs table with correct structure
WARNING: This will delete all existing pack data!
"""
import asyncpg
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def recreate_table():
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)
    print("Connected to database\n")

    try:
        # Check current data
        rows = await conn.fetch('SELECT * FROM user_packs')
        print(f"Current user_packs has {len(rows)} rows")

        if rows:
            print("\nCurrent data (will be lost):")
            print("="*50)
            for row in rows:
                print(f"  User {row['user_id']} in guild {row['guild_id']}: {row['pack_count']} packs")

        print("\n" + "="*50)
        print("WARNING: About to drop and recreate user_packs table!")
        print("All pack data will be lost!")
        print("="*50)

        # Drop the old table
        print("\nDropping old user_packs table...")
        await conn.execute('DROP TABLE IF EXISTS user_packs CASCADE')
        print("Table dropped")

        # Create new table with correct structure
        print("\nCreating new user_packs table...")
        await conn.execute('''
            CREATE TABLE user_packs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                pack_name TEXT NOT NULL,
                pack_config JSONB NOT NULL,
                acquired_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        print("Table created")

        # Create index
        print("\nCreating index...")
        await conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_packs
            ON user_packs(user_id, guild_id)
        ''')
        print("Index created")

        # Verify new structure
        columns = await conn.fetch('''
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'user_packs'
            ORDER BY ordinal_position
        ''')

        print("\nNew user_packs table structure:")
        print("="*50)
        for col in columns:
            print(f"  {col['column_name']}: {col['data_type']}")

        await conn.close()
        print("\nMigration complete!")
        print("\nNote: Users will need to buy new packs from the shop.")

    except Exception as e:
        print(f"\nMigration failed: {e}")
        import traceback
        traceback.print_exc()
        await conn.close()

if __name__ == "__main__":
    asyncio.run(recreate_table())
