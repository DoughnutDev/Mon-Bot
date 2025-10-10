"""
Quick script to check shop items in the database
"""
import asyncpg
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def check_shop():
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)

    # Get all shop items
    items = await conn.fetch('SELECT * FROM shop_items ORDER BY price ASC')

    print(f"\nTotal shop items in database: {len(items)}\n")
    print("="*60)

    for i, item in enumerate(items):
        print(f"Page {i}: {item['item_name']} - ${item['price']}")
        print(f"  ID: {item['id']}")
        print(f"  Type: {item['item_type']}")
        print(f"  Active: {item['is_active']}")
        print(f"  Has pack_config: {item['pack_config'] is not None}")
        print()

    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_shop())
