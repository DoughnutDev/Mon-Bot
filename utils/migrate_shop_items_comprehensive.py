"""
Comprehensive database migration script for shop_items table.

This script will:
1. Check if pack_config column exists in shop_items table
2. Add the column if it doesn't exist
3. Update all existing shop items with their proper pack configurations
4. Verify the migration was successful

Usage:
    python migrate_shop_items_comprehensive.py

Requirements:
    - DATABASE_URL environment variable must be set
    - Database must be accessible
"""

import asyncpg
import os
import asyncio
import json
from typing import Dict, List, Tuple
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Define all pack configurations (matches database.py)
PACK_CONFIGS = {
    'Basic Pack': {
        'min_pokemon': 3,
        'max_pokemon': 5,
        'shiny_chance': 0.0001,  # 0.01%
        'legendary_chance': 0.05,  # 5%
        'mega_pack_chance': 0,
        'mega_pack_size': 0
    },
    'Booster Pack': {
        'min_pokemon': 5,
        'max_pokemon': 8,
        'shiny_chance': 0.0005,  # 0.05%
        'legendary_chance': 0.10,  # 10%
        'mega_pack_chance': 0.15,  # 15%
        'mega_pack_size': 12
    },
    'Premium Pack': {
        'min_pokemon': 8,
        'max_pokemon': 12,
        'shiny_chance': 0.001,  # 0.1%
        'legendary_chance': 0.20,  # 20%
        'mega_pack_chance': 0.25,  # 25%
        'mega_pack_size': 15,
        'guaranteed_rare': True
    },
    'Elite Trainer Pack': {
        'min_pokemon': 12,
        'max_pokemon': 18,
        'shiny_chance': 0.005,  # 0.5%
        'legendary_chance': 0.40,  # 40%
        'mega_pack_chance': 0.35,  # 35%
        'mega_pack_size': 20,
        'guaranteed_rare': True,
        'guaranteed_rare_count': 3
    },
    'Master Collection': {
        'min_pokemon': 20,
        'max_pokemon': 25,
        'shiny_chance': 0.01,  # 1%
        'legendary_chance': 0.60,  # 60%
        'mega_pack_chance': 0.50,  # 50%
        'mega_pack_size': 30,
        'guaranteed_shiny_or_legendaries': True,
        'guaranteed_legendary_count': 3
    }
}


async def check_column_exists(conn: asyncpg.Connection) -> bool:
    """Check if pack_config column exists in shop_items table"""
    exists = await conn.fetchval('''
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'shop_items'
            AND column_name = 'pack_config'
        )
    ''')
    return exists


async def check_table_exists(conn: asyncpg.Connection) -> bool:
    """Check if shop_items table exists"""
    exists = await conn.fetchval('''
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'shop_items'
        )
    ''')
    return exists


async def add_pack_config_column(conn: asyncpg.Connection):
    """Add pack_config column to shop_items table"""
    print("Adding pack_config column to shop_items table...")
    await conn.execute('''
        ALTER TABLE shop_items
        ADD COLUMN pack_config JSONB
    ''')
    print("Column added successfully")


async def get_existing_shop_items(conn: asyncpg.Connection) -> List[Dict]:
    """Get all existing shop items"""
    rows = await conn.fetch('''
        SELECT id, item_name, item_type, description, price
        FROM shop_items
        ORDER BY price ASC
    ''')
    return [dict(row) for row in rows]


async def update_shop_item_config(conn: asyncpg.Connection, item_id: int, item_name: str, pack_config: Dict):
    """Update a single shop item with its pack configuration"""
    await conn.execute('''
        UPDATE shop_items
        SET pack_config = $1
        WHERE id = $2
    ''', json.dumps(pack_config), item_id)
    print(f"  Updated '{item_name}' with pack config")


async def insert_missing_shop_items(conn: asyncpg.Connection, existing_items: List[Dict]):
    """Insert any shop items that are missing from the database"""
    existing_names = {item['item_name'] for item in existing_items}

    shop_items_data = [
        ('pack', 'Basic Pack', 'Standard pack with a few random Pokemon', 100),
        ('pack', 'Booster Pack', 'Enhanced pack with better odds and more Pokemon!', 250),
        ('pack', 'Premium Pack', 'Premium pack with guaranteed rare Pokemon and excellent shiny odds!', 500),
        ('pack', 'Elite Trainer Pack', 'Elite pack for serious trainers! Multiple guaranteed rares with amazing shiny rates!', 1000),
        ('pack', 'Master Collection', 'Ultimate pack! Guaranteed shiny or multiple legendaries with the best odds!', 2500),
    ]

    inserted_count = 0
    for item_type, item_name, description, price in shop_items_data:
        if item_name not in existing_names:
            pack_config = PACK_CONFIGS.get(item_name)
            if pack_config:
                await conn.execute('''
                    INSERT INTO shop_items (item_type, item_name, description, price, pack_config)
                    VALUES ($1, $2, $3, $4, $5)
                ''', item_type, item_name, description, price, json.dumps(pack_config))
                print(f"  Inserted missing item: '{item_name}'")
                inserted_count += 1

    return inserted_count


async def verify_migration(conn: asyncpg.Connection) -> bool:
    """Verify that all shop items have pack_config set"""
    print("\nVerifying migration...")

    # Check for any NULL pack_configs
    null_count = await conn.fetchval('''
        SELECT COUNT(*)
        FROM shop_items
        WHERE pack_config IS NULL
    ''')

    if null_count > 0:
        print(f"  Warning: {null_count} shop items still have NULL pack_config")
        return False

    # Get all shop items and verify
    items = await conn.fetch('''
        SELECT item_name, pack_config
        FROM shop_items
        ORDER BY price ASC
    ''')

    print(f"\nAll {len(items)} shop items have pack_config set:")
    for item in items:
        config = json.loads(item['pack_config']) if isinstance(item['pack_config'], str) else item['pack_config']
        print(f"  - {item['item_name']}: {config['min_pokemon']}-{config['max_pokemon']} Pokemon, "
              f"{config['shiny_chance']*100:.2f}% shiny, {config['legendary_chance']*100:.0f}% legendary")

    return True


async def migrate_database():
    """Main migration function"""
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("\nPlease set it using:")
        print("  export DATABASE_URL='postgresql://user:password@host:port/database'")
        print("  # or on Windows:")
        print("  set DATABASE_URL=postgresql://user:password@host:port/database")
        return False

    try:
        print("=" * 60)
        print("Shop Items Pack Config Migration")
        print("=" * 60)

        # Connect to database
        print("\n[1/6] Connecting to database...")
        conn = await asyncpg.connect(database_url)
        print("Connected successfully")

        # Check if table exists
        print("\n[2/6] Checking if shop_items table exists...")
        table_exists = await check_table_exists(conn)
        if not table_exists:
            print("ERROR: shop_items table does not exist!")
            print("Please run the bot first to create all tables.")
            await conn.close()
            return False
        print("Table exists")

        # Check if column exists
        print("\n[3/6] Checking if pack_config column exists...")
        column_exists = await check_column_exists(conn)

        if column_exists:
            print("Column already exists")
        else:
            print("Column does not exist")
            await add_pack_config_column(conn)

        # Get existing shop items
        print("\n[4/6] Retrieving existing shop items...")
        existing_items = await get_existing_shop_items(conn)
        print(f"Found {len(existing_items)} existing shop items")

        # Update pack configs for existing items
        print("\n[5/6] Updating pack configurations...")
        updated_count = 0
        for item in existing_items:
            pack_config = PACK_CONFIGS.get(item['item_name'])
            if pack_config:
                await update_shop_item_config(conn, item['id'], item['item_name'], pack_config)
                updated_count += 1
            else:
                print(f"  Warning: No pack config found for '{item['item_name']}'")

        print(f"Updated {updated_count} items")

        # Insert any missing shop items
        print("\n[5.5/6] Checking for missing shop items...")
        inserted = await insert_missing_shop_items(conn, existing_items)
        if inserted > 0:
            print(f"Inserted {inserted} missing items")
        else:
            print("All shop items already exist")

        # Verify migration
        print("\n[6/6] Verifying migration...")
        success = await verify_migration(conn)

        # Close connection
        await conn.close()

        print("\n" + "=" * 60)
        if success:
            print("MIGRATION COMPLETED SUCCESSFULLY!")
            print("=" * 60)
            print("\nYou can now restart your bot.")
            return True
        else:
            print("MIGRATION COMPLETED WITH WARNINGS")
            print("=" * 60)
            print("\nPlease review the warnings above.")
            return False

    except Exception as e:
        print(f"\nMIGRATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(migrate_database())
    exit(0 if success else 1)
