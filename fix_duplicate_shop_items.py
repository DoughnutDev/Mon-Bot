"""
Script to remove duplicate shop items from the database
Keeps only the newest entry for each pack type
"""
import asyncpg
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def fix_duplicates():
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    conn = await asyncpg.connect(database_url)
    print("Connected to database\n")

    # Get all shop items grouped by name
    items = await conn.fetch('''
        SELECT id, item_name, price, pack_config
        FROM shop_items
        ORDER BY item_name, id
    ''')

    print(f"Total items before cleanup: {len(items)}\n")

    # Group by item name
    items_by_name = {}
    for item in items:
        name = item['item_name']
        if name not in items_by_name:
            items_by_name[name] = []
        items_by_name[name].append(item)

    # Find duplicates and keep only the one with pack_config
    ids_to_delete = []

    for name, item_list in items_by_name.items():
        if len(item_list) > 1:
            print(f"Found {len(item_list)} duplicates of '{name}'")

            # Keep the one with pack_config (highest ID usually = newest)
            items_with_config = [i for i in item_list if i['pack_config'] is not None]

            if items_with_config:
                # Keep the last one (highest ID)
                keep_item = items_with_config[-1]
                print(f"  Keeping ID {keep_item['id']} (has pack_config)")

                # Mark others for deletion
                for item in item_list:
                    if item['id'] != keep_item['id']:
                        ids_to_delete.append(item['id'])
                        print(f"  Deleting ID {item['id']}")
            else:
                # No pack_config, just keep the highest ID
                keep_item = item_list[-1]
                print(f"  Keeping ID {keep_item['id']}")
                for item in item_list[:-1]:
                    ids_to_delete.append(item['id'])
                    print(f"  Deleting ID {item['id']}")
            print()

    if ids_to_delete:
        print(f"\nDeleting {len(ids_to_delete)} duplicate items...")
        for item_id in ids_to_delete:
            await conn.execute('DELETE FROM shop_items WHERE id = $1', item_id)
            print(f"  Deleted item ID {item_id}")

        print(f"\nDeleted {len(ids_to_delete)} duplicate items")
    else:
        print("\nNo duplicates found!")

    # Verify final count
    final_count = await conn.fetchval('SELECT COUNT(*) FROM shop_items')
    print(f"\nTotal items after cleanup: {final_count}")

    # Show remaining items
    remaining = await conn.fetch('''
        SELECT id, item_name, price
        FROM shop_items
        ORDER BY price ASC
    ''')

    print("\nRemaining shop items:")
    print("="*60)
    for i, item in enumerate(remaining):
        print(f"Page {i}: {item['item_name']} - ${item['price']} (ID: {item['id']})")

    await conn.close()
    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(fix_duplicates())
