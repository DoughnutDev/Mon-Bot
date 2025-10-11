# 🚨 Quick Fix for Database Error

## Error You're Seeing
```
Database setup failed: column "pack_config" of relation "shop_items" does not exist
```

## Quick Fix (2 Steps)

### Step 1: Set your database connection
```bash
# Replace with your actual database URL
export DATABASE_URL='postgresql://username:password@host:port/database'
```

### Step 2: Run the migration
```bash
python migrate_shop_items_comprehensive.py
```

That's it! Then restart your bot.

---

**For detailed instructions and troubleshooting, see [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)**
