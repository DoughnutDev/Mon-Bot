# Database Migration Guide

## Problem

Your bot is failing to start with this error:
```
Database setup failed: column "pack_config" of relation "shop_items" does not exist
```

## Why This Happens

The bot code was updated to include a tiered pack system with different pack configurations (Basic Pack, Booster Pack, Premium Pack, etc.). These configurations are stored in a `pack_config` column in the `shop_items` table.

However, your **existing database** was created before this feature was added, so it doesn't have this column. The bot expects it to exist, which causes the startup to fail.

## Solution: Run the Migration Script

I've created `migrate_shop_items_comprehensive.py` which will:

1. ✅ Check if your `shop_items` table exists
2. ✅ Add the `pack_config` column if it's missing
3. ✅ Update all existing shop items with their proper pack configurations
4. ✅ Insert any missing shop items (in case some weren't created)
5. ✅ Verify everything worked correctly

## How to Run the Migration

### Step 1: Set Your Database URL

The script needs to connect to your PostgreSQL database. Set the `DATABASE_URL` environment variable:

**On Linux/Mac:**
```bash
export DATABASE_URL='postgresql://username:password@hostname:port/database_name'
```

**On Windows (Command Prompt):**
```cmd
set DATABASE_URL=postgresql://username:password@hostname:port/database_name
```

**On Windows (PowerShell):**
```powershell
$env:DATABASE_URL="postgresql://username:password@hostname:port/database_name"
```

**Example:**
```bash
export DATABASE_URL='postgresql://monbot_user:mypassword@localhost:5432/monbot_db'
```

### Step 2: Run the Migration

```bash
cd C:\Users\gunna\IdeaProjects\Mon-Bot
python migrate_shop_items_comprehensive.py
```

### Step 3: Review the Output

The script will show detailed output like this:

```
============================================================
Shop Items Pack Config Migration
============================================================

[1/6] Connecting to database...
✓ Connected successfully

[2/6] Checking if shop_items table exists...
✓ Table exists

[3/6] Checking if pack_config column exists...
✗ Column does not exist
Adding pack_config column to shop_items table...
✓ Column added successfully

[4/6] Retrieving existing shop items...
✓ Found 5 existing shop items

[5/6] Updating pack configurations...
  ✓ Updated 'Basic Pack' with pack config
  ✓ Updated 'Booster Pack' with pack config
  ✓ Updated 'Premium Pack' with pack config
  ✓ Updated 'Elite Trainer Pack' with pack config
  ✓ Updated 'Master Collection' with pack config
✓ Updated 5 items

[5.5/6] Checking for missing shop items...
✓ All shop items already exist

[6/6] Verifying migration...

✓ All 5 shop items have pack_config set:
  • Basic Pack: 3-5 Pokemon, 0.01% shiny, 5% legendary
  • Booster Pack: 5-8 Pokemon, 0.05% shiny, 10% legendary
  • Premium Pack: 8-12 Pokemon, 0.10% shiny, 20% legendary
  • Elite Trainer Pack: 12-18 Pokemon, 0.50% shiny, 40% legendary
  • Master Collection: 20-25 Pokemon, 1.00% shiny, 60% legendary

============================================================
✓ MIGRATION COMPLETED SUCCESSFULLY!
============================================================

You can now restart your bot.
```

### Step 4: Restart Your Bot

After the migration completes successfully, restart your bot:

```bash
python bot.py
```

## Alternative: Manual SQL Migration

If you prefer to do it manually via SQL, connect to your PostgreSQL database and run:

```sql
-- Add the column
ALTER TABLE shop_items ADD COLUMN pack_config JSONB;

-- Update Basic Pack
UPDATE shop_items
SET pack_config = '{"min_pokemon": 3, "max_pokemon": 5, "shiny_chance": 0.0001, "legendary_chance": 0.05, "mega_pack_chance": 0, "mega_pack_size": 0}'::jsonb
WHERE item_name = 'Basic Pack';

-- Update Booster Pack
UPDATE shop_items
SET pack_config = '{"min_pokemon": 5, "max_pokemon": 8, "shiny_chance": 0.0005, "legendary_chance": 0.10, "mega_pack_chance": 0.15, "mega_pack_size": 12}'::jsonb
WHERE item_name = 'Booster Pack';

-- Update Premium Pack
UPDATE shop_items
SET pack_config = '{"min_pokemon": 8, "max_pokemon": 12, "shiny_chance": 0.001, "legendary_chance": 0.20, "mega_pack_chance": 0.25, "mega_pack_size": 15, "guaranteed_rare": true}'::jsonb
WHERE item_name = 'Premium Pack';

-- Update Elite Trainer Pack
UPDATE shop_items
SET pack_config = '{"min_pokemon": 12, "max_pokemon": 18, "shiny_chance": 0.005, "legendary_chance": 0.40, "mega_pack_chance": 0.35, "mega_pack_size": 20, "guaranteed_rare": true, "guaranteed_rare_count": 3}'::jsonb
WHERE item_name = 'Elite Trainer Pack';

-- Update Master Collection
UPDATE shop_items
SET pack_config = '{"min_pokemon": 20, "max_pokemon": 25, "shiny_chance": 0.01, "legendary_chance": 0.60, "mega_pack_chance": 0.50, "mega_pack_size": 30, "guaranteed_shiny_or_legendaries": true, "guaranteed_legendary_count": 3}'::jsonb
WHERE item_name = 'Master Collection';
```

## What Each Pack Configuration Means

Each pack has these properties:

- **min_pokemon / max_pokemon**: How many Pokemon you get per pack
- **shiny_chance**: Probability of getting a shiny Pokemon (0.01 = 1%)
- **legendary_chance**: Probability of each Pokemon being legendary
- **mega_pack_chance**: Chance the pack becomes a "mega pack" with extra Pokemon
- **mega_pack_size**: How many Pokemon in a mega pack
- **guaranteed_rare**: Whether the pack guarantees at least 1 rare Pokemon
- **guaranteed_rare_count**: Minimum number of rare Pokemon guaranteed
- **guaranteed_shiny_or_legendaries**: Guarantees either a shiny OR multiple legendaries
- **guaranteed_legendary_count**: Minimum legendaries if no shiny is caught

## Troubleshooting

### Error: "DATABASE_URL environment variable not set"
Make sure you've set the environment variable in the same terminal session where you run the script.

### Error: "shop_items table does not exist"
Run your bot once to create all the tables, then run the migration.

### Error: "Connection refused"
Check that:
- Your PostgreSQL server is running
- The hostname, port, username, and password are correct
- Your firewall allows connections to PostgreSQL

### Error: "Authentication failed"
Double-check your username and password in the DATABASE_URL.

## After Migration

Once the migration completes:
1. ✅ The `pack_config` column will exist
2. ✅ All shop items will have their configurations
3. ✅ Your bot will start without errors
4. ✅ Users can purchase different pack types from the shop
5. ✅ The `/pack` command will use the correct pack configurations

## Need Help?

If you encounter issues:
1. Check the error message carefully
2. Make sure your DATABASE_URL is correct
3. Ensure PostgreSQL is running
4. Review the migration script output for clues
