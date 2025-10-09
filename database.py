import asyncpg
import os
from datetime import datetime
from typing import List, Dict, Optional

# Database connection pool
pool: Optional[asyncpg.Pool] = None


async def setup_database():
    """Initialize database connection and create tables"""
    global pool

    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("WARNING: DATABASE_URL not set. Database features will not work.")
        return

    try:
        # Create connection pool
        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        print("Database connection pool created")

        # Create tables
        async with pool.acquire() as conn:
            # Guilds table - stores server configurations
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS guilds (
                    guild_id BIGINT PRIMARY KEY,
                    spawn_channels BIGINT[],
                    spawn_interval_min INTEGER DEFAULT 180,
                    spawn_interval_max INTEGER DEFAULT 600,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            ''')

            # Catches table - stores all Pokemon catches
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS catches (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    pokemon_name TEXT NOT NULL,
                    pokemon_id INTEGER NOT NULL,
                    pokemon_types TEXT[],
                    caught_at TIMESTAMP DEFAULT NOW()
                )
            ''')

            # Create indexes for faster queries
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_catches_user
                ON catches(user_id, guild_id)
            ''')

            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_catches_guild
                ON catches(guild_id)
            ''')

            print("Database tables created successfully")

    except Exception as e:
        print(f"Error setting up database: {e}")
        raise


async def close_database():
    """Close database connection pool"""
    global pool
    if pool:
        await pool.close()
        print("Database connection pool closed")


# Guild management functions

async def get_guild_config(guild_id: int) -> Optional[Dict]:
    """Get configuration for a guild"""
    if not pool:
        return None

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM guilds WHERE guild_id = $1',
            guild_id
        )

        if row:
            return dict(row)
        return None


async def set_spawn_channel(guild_id: int, channel_id: int):
    """Set or add a spawn channel for a guild"""
    if not pool:
        return

    async with pool.acquire() as conn:
        # Check if guild exists
        exists = await conn.fetchval(
            'SELECT EXISTS(SELECT 1 FROM guilds WHERE guild_id = $1)',
            guild_id
        )

        if exists:
            # Add channel to existing array (if not already present)
            await conn.execute('''
                UPDATE guilds
                SET spawn_channels = array_append(
                    COALESCE(spawn_channels, ARRAY[]::BIGINT[]), $2::BIGINT
                ),
                updated_at = NOW()
                WHERE guild_id = $1
                AND NOT ($2::BIGINT = ANY(COALESCE(spawn_channels, ARRAY[]::BIGINT[])))
            ''', guild_id, channel_id)
        else:
            # Create new guild entry
            await conn.execute('''
                INSERT INTO guilds (guild_id, spawn_channels)
                VALUES ($1, ARRAY[$2]::BIGINT[])
            ''', guild_id, channel_id)


async def remove_spawn_channel(guild_id: int, channel_id: int):
    """Remove a spawn channel from a guild"""
    if not pool:
        return

    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE guilds
            SET spawn_channels = array_remove(spawn_channels, $2::BIGINT),
            updated_at = NOW()
            WHERE guild_id = $1
        ''', guild_id, channel_id)


async def get_all_spawn_channels() -> Dict[int, List[int]]:
    """Get all spawn channels for all guilds"""
    if not pool:
        return {}

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT guild_id, spawn_channels
            FROM guilds
            WHERE spawn_channels IS NOT NULL
            AND array_length(spawn_channels, 1) > 0
        ''')

        result = {}
        for row in rows:
            result[row['guild_id']] = list(row['spawn_channels'])

        return result


# Pokemon catch functions

async def add_catch(user_id: int, guild_id: int, pokemon_name: str,
                   pokemon_id: int, pokemon_types: List[str]):
    """Record a Pokemon catch"""
    if not pool:
        return

    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO catches (user_id, guild_id, pokemon_name, pokemon_id, pokemon_types)
            VALUES ($1, $2, $3, $4, $5)
        ''', user_id, guild_id, pokemon_name, pokemon_id, pokemon_types)


async def get_user_catches(user_id: int, guild_id: int) -> List[Dict]:
    """Get all catches for a user in a specific guild"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT pokemon_name, pokemon_id, pokemon_types, caught_at
            FROM catches
            WHERE user_id = $1 AND guild_id = $2
            ORDER BY caught_at DESC
        ''', user_id, guild_id)

        return [dict(row) for row in rows]


async def get_user_catch_counts(user_id: int, guild_id: int) -> Dict[str, int]:
    """Get count of each Pokemon caught by a user"""
    if not pool:
        return {}

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT pokemon_name, COUNT(*) as count
            FROM catches
            WHERE user_id = $1 AND guild_id = $2
            GROUP BY pokemon_name
            ORDER BY count DESC
        ''', user_id, guild_id)

        return {row['pokemon_name']: row['count'] for row in rows}


async def get_user_stats(user_id: int, guild_id: int) -> Dict:
    """Get catch statistics for a user"""
    if not pool:
        return {'total': 0, 'unique': 0}

    async with pool.acquire() as conn:
        stats = await conn.fetchrow('''
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT pokemon_name) as unique
            FROM catches
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

        return dict(stats) if stats else {'total': 0, 'unique': 0}
