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
        print("Creating database connection pool...", flush=True)
        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        print("Database connection pool created", flush=True)

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

            # Battlepass table - tracks user progression
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_battlepass (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    season INTEGER DEFAULT 1,
                    xp INTEGER DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    last_updated TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (user_id, guild_id, season)
                )
            ''')

            # Packs table - tracks user's pack inventory
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_packs (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    pack_count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')

            # Battlepass rewards table - defines rewards for each level
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS battlepass_rewards (
                    season INTEGER NOT NULL,
                    level INTEGER NOT NULL,
                    reward_type TEXT NOT NULL,
                    reward_value INTEGER NOT NULL,
                    PRIMARY KEY (season, level)
                )
            ''')

            # Initialize Season 1 rewards if not already present
            print("Initializing Season 1 rewards...", flush=True)
            await _initialize_season1_rewards(conn)
            print("Season 1 rewards initialized", flush=True)

            print("Database tables created successfully", flush=True)

    except Exception as e:
        print(f"Error setting up database: {e}", flush=True)
        import traceback
        traceback.print_exc()
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


# Battlepass functions

async def _initialize_season1_rewards(conn):
    """Initialize Season 1 battlepass rewards"""
    # Define Season 1 rewards - packs at levels 5, 10, 15, 20, 25, 30, 35, 40, 45, 50
    season1_rewards = [
        (1, 5, 'pack', 1),
        (1, 10, 'pack', 2),
        (1, 15, 'pack', 1),
        (1, 20, 'pack', 3),
        (1, 25, 'pack', 2),
        (1, 30, 'pack', 3),
        (1, 35, 'pack', 2),
        (1, 40, 'pack', 4),
        (1, 45, 'pack', 3),
        (1, 50, 'pack', 5),
    ]

    for season, level, reward_type, reward_value in season1_rewards:
        await conn.execute('''
            INSERT INTO battlepass_rewards (season, level, reward_type, reward_value)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (season, level) DO NOTHING
        ''', season, level, reward_type, reward_value)


async def add_xp(user_id: int, guild_id: int, xp_amount: int = 10, season: int = 1):
    """Add XP to a user's battlepass and handle level ups"""
    if not pool:
        return None

    async with pool.acquire() as conn:
        # Get or create user battlepass entry
        bp = await conn.fetchrow('''
            INSERT INTO user_battlepass (user_id, guild_id, season, xp, level)
            VALUES ($1, $2, $3, $4, 1)
            ON CONFLICT (user_id, guild_id, season)
            DO UPDATE SET xp = user_battlepass.xp + $4, last_updated = NOW()
            RETURNING *
        ''', user_id, guild_id, season, xp_amount)

        # Calculate new level (100 XP per level)
        new_level = (bp['xp'] // 100) + 1
        if new_level > 50:
            new_level = 50  # Cap at level 50

        old_level = bp['level']

        # Update level if it changed
        if new_level != old_level:
            await conn.execute('''
                UPDATE user_battlepass
                SET level = $1, last_updated = NOW()
                WHERE user_id = $2 AND guild_id = $3 AND season = $4
            ''', new_level, user_id, guild_id, season)

            # Award rewards for each level gained
            rewards_earned = []
            for level in range(old_level + 1, new_level + 1):
                reward = await conn.fetchrow('''
                    SELECT * FROM battlepass_rewards
                    WHERE season = $1 AND level = $2
                ''', season, level)

                if reward:
                    if reward['reward_type'] == 'pack':
                        await add_packs(user_id, guild_id, reward['reward_value'])
                        rewards_earned.append({
                            'level': level,
                            'type': 'pack',
                            'amount': reward['reward_value']
                        })

            return {
                'leveled_up': True,
                'old_level': old_level,
                'new_level': new_level,
                'current_xp': bp['xp'] + xp_amount,
                'rewards': rewards_earned
            }

        return {
            'leveled_up': False,
            'level': new_level,
            'current_xp': bp['xp'] + xp_amount
        }


async def get_battlepass_progress(user_id: int, guild_id: int, season: int = 1) -> Dict:
    """Get user's battlepass progress"""
    if not pool:
        return {'level': 1, 'xp': 0, 'season': season}

    async with pool.acquire() as conn:
        bp = await conn.fetchrow('''
            SELECT * FROM user_battlepass
            WHERE user_id = $1 AND guild_id = $2 AND season = $3
        ''', user_id, guild_id, season)

        if bp:
            return dict(bp)
        else:
            # Return default values for new users
            return {'level': 1, 'xp': 0, 'season': season}


async def get_battlepass_rewards(season: int = 1) -> List[Dict]:
    """Get all rewards for a season"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT * FROM battlepass_rewards
            WHERE season = $1
            ORDER BY level ASC
        ''', season)

        return [dict(row) for row in rows]


# Pack functions

async def add_packs(user_id: int, guild_id: int, amount: int = 1):
    """Add packs to a user's inventory"""
    if not pool:
        return

    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO user_packs (user_id, guild_id, pack_count)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, guild_id)
            DO UPDATE SET pack_count = user_packs.pack_count + $3
        ''', user_id, guild_id, amount)


async def get_pack_count(user_id: int, guild_id: int) -> int:
    """Get number of packs a user has"""
    if not pool:
        return 0

    async with pool.acquire() as conn:
        count = await conn.fetchval('''
            SELECT pack_count FROM user_packs
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

        return count if count else 0


async def use_pack(user_id: int, guild_id: int) -> bool:
    """Use one pack from user's inventory. Returns True if successful."""
    if not pool:
        return False

    async with pool.acquire() as conn:
        # Check if user has packs
        count = await conn.fetchval('''
            SELECT pack_count FROM user_packs
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

        if not count or count < 1:
            return False

        # Decrement pack count
        await conn.execute('''
            UPDATE user_packs
            SET pack_count = pack_count - 1
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

        return True
