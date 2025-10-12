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
                    is_shiny BOOLEAN DEFAULT FALSE,
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

            # Packs table - tracks user's pack inventory by type
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_packs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    pack_name TEXT NOT NULL,
                    pack_config JSONB NOT NULL,
                    acquired_at TIMESTAMP DEFAULT NOW()
                )
            ''')

            # Create index for faster pack queries
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_packs
                ON user_packs(user_id, guild_id)
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

            # Pokemon stats table - for battle system (per individual catch)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS pokemon_stats (
                    catch_id INTEGER PRIMARY KEY,
                    level INTEGER DEFAULT 1,
                    experience INTEGER DEFAULT 0,
                    battles_won INTEGER DEFAULT 0,
                    battles_lost INTEGER DEFAULT 0
                )
            ''')

            # Pokemon species stats table - shared XP/level for all Pokemon of same species
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS pokemon_species_stats (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    pokemon_id INTEGER NOT NULL,
                    pokemon_name TEXT NOT NULL,
                    level INTEGER DEFAULT 1,
                    experience INTEGER DEFAULT 0,
                    battles_won INTEGER DEFAULT 0,
                    battles_lost INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id, pokemon_id)
                )
            ''')

            # Battle history table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS battle_history (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    winner_id BIGINT NOT NULL,
                    loser_id BIGINT NOT NULL,
                    winner_pokemon_id INTEGER NOT NULL,
                    loser_pokemon_id INTEGER NOT NULL,
                    winner_pokemon_name TEXT NOT NULL,
                    loser_pokemon_name TEXT NOT NULL,
                    turns_taken INTEGER NOT NULL,
                    battle_date TIMESTAMP DEFAULT NOW()
                )
            ''')

            # Create index for battle history
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_battle_history_users
                ON battle_history(winner_id, loser_id, guild_id)
            ''')

            # Daily quests table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_quests (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    quest_date DATE NOT NULL,
                    quest_1_type TEXT,
                    quest_1_target INTEGER,
                    quest_1_progress INTEGER DEFAULT 0,
                    quest_1_completed BOOLEAN DEFAULT FALSE,
                    quest_1_reward INTEGER,
                    quest_2_type TEXT,
                    quest_2_target INTEGER,
                    quest_2_progress INTEGER DEFAULT 0,
                    quest_2_completed BOOLEAN DEFAULT FALSE,
                    quest_2_reward INTEGER,
                    quest_3_type TEXT,
                    quest_3_target INTEGER,
                    quest_3_progress INTEGER DEFAULT 0,
                    quest_3_completed BOOLEAN DEFAULT FALSE,
                    quest_3_reward INTEGER,
                    PRIMARY KEY (user_id, guild_id, quest_date)
                )
            ''')

            # Rain usage tracking table (one-time use per user)
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS rain_usage (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    has_used BOOLEAN DEFAULT FALSE,
                    used_at TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')

            # User currency table - Pokedollars
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_currency (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    balance INTEGER DEFAULT 0,
                    total_earned INTEGER DEFAULT 0,
                    total_spent INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')

            # Shop items table - defines items available in shop
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS shop_items (
                    id SERIAL PRIMARY KEY,
                    item_type TEXT NOT NULL,
                    item_name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    price INTEGER NOT NULL,
                    stock_unlimited BOOLEAN DEFAULT TRUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    pack_config JSONB
                )
            ''')

            # Gym badges table - tracks which gyms users have beaten
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS gym_badges (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    gym_name TEXT NOT NULL,
                    earned_at TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (user_id, guild_id, gym_name)
                )
            ''')

            # Trainer battle cooldowns - tracks /trainer command usage
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS trainer_cooldowns (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    battles_used INTEGER DEFAULT 0,
                    cooldown_reset TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (user_id, guild_id)
                )
            ''')

            # Initialize Season 1 rewards if not already present
            print("Initializing Season 1 rewards...", flush=True)
            await _initialize_season1_rewards(conn)
            print("Season 1 rewards initialized", flush=True)

            # Initialize shop items
            print("Initializing shop items...", flush=True)
            await _initialize_shop_items(conn)
            print("Shop items initialized", flush=True)

            # Migration: Add is_shiny column if it doesn't exist
            print("Checking for database migrations...", flush=True)
            try:
                await conn.execute('''
                    ALTER TABLE catches
                    ADD COLUMN IF NOT EXISTS is_shiny BOOLEAN DEFAULT FALSE
                ''')
                print("Migration complete: is_shiny column added", flush=True)
            except Exception as e:
                print(f"Migration note: {e}", flush=True)

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
                   pokemon_id: int, pokemon_types: List[str], is_shiny: bool = False):
    """Record a Pokemon catch"""
    if not pool:
        return

    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO catches (user_id, guild_id, pokemon_name, pokemon_id, pokemon_types, is_shiny)
            VALUES ($1, $2, $3, $4, $5, $6)
        ''', user_id, guild_id, pokemon_name, pokemon_id, pokemon_types, is_shiny)


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


async def get_pokemon_with_counts(user_id: int, guild_id: int, sort_by: str = 'most_caught') -> List[Dict]:
    """Get Pokemon with counts, sorted by various criteria"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        # Base query
        base_query = '''
            SELECT
                pokemon_name,
                pokemon_id,
                COUNT(*) as count,
                MAX(caught_at) as last_caught
            FROM catches
            WHERE user_id = $1 AND guild_id = $2
            GROUP BY pokemon_name, pokemon_id
        '''

        # Add sorting
        if sort_by == 'most_caught':
            order_by = 'ORDER BY count DESC, pokemon_name ASC'
        elif sort_by == 'alphabetical':
            order_by = 'ORDER BY pokemon_name ASC'
        elif sort_by == 'pokedex_number':
            order_by = 'ORDER BY pokemon_id ASC'
        elif sort_by == 'rarest':
            order_by = 'ORDER BY count ASC, pokemon_name ASC'
        elif sort_by == 'recently_caught':
            order_by = 'ORDER BY last_caught DESC'
        else:
            order_by = 'ORDER BY count DESC, pokemon_name ASC'

        query = f'{base_query} {order_by}'

        rows = await conn.fetch(query, user_id, guild_id)
        return [dict(row) for row in rows]


async def get_legendary_pokemon(user_id: int, guild_id: int) -> List[Dict]:
    """Get only legendary Pokemon from Gen 1"""
    if not pool:
        return []

    # Gen 1 legendaries: Articuno (144), Zapdos (145), Moltres (146), Mewtwo (150), Mew (151)
    legendary_ids = [144, 145, 146, 150, 151]

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT
                pokemon_name,
                pokemon_id,
                COUNT(*) as count,
                MAX(caught_at) as last_caught
            FROM catches
            WHERE user_id = $1 AND guild_id = $2 AND pokemon_id = ANY($3)
            GROUP BY pokemon_name, pokemon_id
            ORDER BY pokemon_id ASC
        ''', user_id, guild_id, legendary_ids)

        return [dict(row) for row in rows]


async def get_shiny_pokemon(user_id: int, guild_id: int) -> List[Dict]:
    """Get only shiny Pokemon"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT
                pokemon_name,
                pokemon_id,
                COUNT(*) as count,
                MAX(caught_at) as last_caught
            FROM catches
            WHERE user_id = $1 AND guild_id = $2 AND is_shiny = TRUE
            GROUP BY pokemon_name, pokemon_id
            ORDER BY pokemon_id ASC
        ''', user_id, guild_id)

        return [dict(row) for row in rows]


# Leaderboard functions

async def get_leaderboard_most_caught(guild_id: int, limit: int = 10) -> List[Dict]:
    """Get leaderboard by total Pokemon caught"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT
                user_id,
                COUNT(*) as total_caught
            FROM catches
            WHERE guild_id = $1
            GROUP BY user_id
            ORDER BY total_caught DESC
            LIMIT $2
        ''', guild_id, limit)

        return [dict(row) for row in rows]


async def get_leaderboard_unique(guild_id: int, limit: int = 10) -> List[Dict]:
    """Get leaderboard by unique Pokemon caught"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT
                user_id,
                COUNT(DISTINCT pokemon_name) as unique_pokemon
            FROM catches
            WHERE guild_id = $1
            GROUP BY user_id
            ORDER BY unique_pokemon DESC
            LIMIT $2
        ''', guild_id, limit)

        return [dict(row) for row in rows]


async def get_leaderboard_legendaries(guild_id: int, limit: int = 10) -> List[Dict]:
    """Get leaderboard by legendary Pokemon caught"""
    if not pool:
        return []

    legendary_ids = [144, 145, 146, 150, 151]

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT
                user_id,
                COUNT(*) as legendary_count
            FROM catches
            WHERE guild_id = $1 AND pokemon_id = ANY($2)
            GROUP BY user_id
            ORDER BY legendary_count DESC
            LIMIT $3
        ''', guild_id, legendary_ids, limit)

        return [dict(row) for row in rows]


async def get_leaderboard_shinies(guild_id: int, limit: int = 10) -> List[Dict]:
    """Get leaderboard by shiny Pokemon caught"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT
                user_id,
                COUNT(*) as shiny_count
            FROM catches
            WHERE guild_id = $1 AND is_shiny = TRUE
            GROUP BY user_id
            ORDER BY shiny_count DESC
            LIMIT $2
        ''', guild_id, limit)

        return [dict(row) for row in rows]


async def get_leaderboard_collection_value(guild_id: int, limit: int = 10) -> List[Dict]:
    """Get leaderboard by total collection value (based on sell prices)"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT
                user_id,
                SUM(
                    CASE
                        WHEN pokemon_id IN (144, 145, 146, 150, 151) THEN 100
                        WHEN pokemon_id IN (3, 6, 9, 59, 65, 68, 76, 94, 103, 112, 115, 130, 131, 142, 143) THEN 50
                        WHEN pokemon_id IN (1, 2, 3, 4, 5, 6, 7, 8, 9) THEN 30
                        ELSE 10
                    END
                ) as collection_value
            FROM catches
            WHERE guild_id = $1
            GROUP BY user_id
            ORDER BY collection_value DESC
            LIMIT $2
        ''', guild_id, limit)

        return [dict(row) for row in rows]


async def get_rarest_pokemon_in_server(guild_id: int) -> Optional[Dict]:
    """Get the rarest Pokemon in the server (least caught overall)"""
    if not pool:
        return None

    async with pool.acquire() as conn:
        # Find Pokemon with the lowest catch count across all users
        row = await conn.fetchrow('''
            WITH pokemon_counts AS (
                SELECT
                    pokemon_name,
                    pokemon_id,
                    COUNT(*) as total_caught,
                    COUNT(DISTINCT user_id) as unique_owners
                FROM catches
                WHERE guild_id = $1
                GROUP BY pokemon_name, pokemon_id
            )
            SELECT * FROM pokemon_counts
            ORDER BY total_caught ASC, unique_owners ASC
            LIMIT 1
        ''', guild_id)

        return dict(row) if row else None


async def get_user_with_rarest(guild_id: int) -> Optional[Dict]:
    """Get user who owns the rarest Pokemon in the server"""
    if not pool:
        return None

    rarest = await get_rarest_pokemon_in_server(guild_id)
    if not rarest:
        return None

    async with pool.acquire() as conn:
        # Find first user who caught this rarest Pokemon
        row = await conn.fetchrow('''
            SELECT user_id, caught_at
            FROM catches
            WHERE guild_id = $1 AND pokemon_name = $2
            ORDER BY caught_at ASC
            LIMIT 1
        ''', guild_id, rarest['pokemon_name'])

        if row:
            return {
                'user_id': row['user_id'],
                'pokemon_name': rarest['pokemon_name'],
                'pokemon_id': rarest['pokemon_id'],
                'total_caught': rarest['total_caught'],
                'unique_owners': rarest['unique_owners'],
                'caught_at': row['caught_at']
            }

        return None


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


# Trading functions

async def get_user_pokemon_for_trade(user_id: int, guild_id: int) -> List[Dict]:
    """Get user's Pokemon with individual catch IDs for trading"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT id, pokemon_name, pokemon_id, caught_at
            FROM catches
            WHERE user_id = $1 AND guild_id = $2
            ORDER BY pokemon_name ASC, caught_at DESC
        ''', user_id, guild_id)

        return [dict(row) for row in rows]


async def execute_trade(catch_id1: int, catch_id2: int, user_id1: int, user_id2: int, guild_id: int) -> bool:
    """Execute a trade by swapping ownership of two Pokemon"""
    if not pool:
        return False

    async with pool.acquire() as conn:
        # Start a transaction
        async with conn.transaction():
            # Verify both catches exist and belong to the right users
            catch1 = await conn.fetchrow('''
                SELECT user_id, guild_id FROM catches WHERE id = $1
            ''', catch_id1)

            catch2 = await conn.fetchrow('''
                SELECT user_id, guild_id FROM catches WHERE id = $1
            ''', catch_id2)

            # Validate the trade
            if not catch1 or not catch2:
                return False

            if catch1['user_id'] != user_id1 or catch1['guild_id'] != guild_id:
                return False

            if catch2['user_id'] != user_id2 or catch2['guild_id'] != guild_id:
                return False

            # Execute the swap
            await conn.execute('''
                UPDATE catches SET user_id = $2 WHERE id = $1
            ''', catch_id1, user_id2)

            await conn.execute('''
                UPDATE catches SET user_id = $2 WHERE id = $1
            ''', catch_id2, user_id1)

            return True


# Battle system functions

async def get_pokemon_level(catch_id: int) -> int:
    """Get the level of a specific caught Pokemon"""
    if not pool:
        return 1

    async with pool.acquire() as conn:
        level = await conn.fetchval('''
            SELECT level FROM pokemon_stats WHERE catch_id = $1
        ''', catch_id)

        return level if level else 1


async def record_battle(guild_id: int, winner_id: int, loser_id: int,
                       winner_pokemon_id: int, loser_pokemon_id: int,
                       winner_pokemon_name: str, loser_pokemon_name: str,
                       turns_taken: int):
    """Record a battle result"""
    if not pool:
        return

    async with pool.acquire() as conn:
        # Record battle history
        await conn.execute('''
            INSERT INTO battle_history
            (guild_id, winner_id, loser_id, winner_pokemon_id, loser_pokemon_id,
             winner_pokemon_name, loser_pokemon_name, turns_taken)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ''', guild_id, winner_id, loser_id, winner_pokemon_id, loser_pokemon_id,
             winner_pokemon_name, loser_pokemon_name, turns_taken)

        # Update winner's Pokemon stats
        await conn.execute('''
            INSERT INTO pokemon_stats (catch_id, battles_won)
            VALUES ($1, 1)
            ON CONFLICT (catch_id)
            DO UPDATE SET battles_won = pokemon_stats.battles_won + 1
        ''', winner_pokemon_id)

        # Update loser's Pokemon stats
        await conn.execute('''
            INSERT INTO pokemon_stats (catch_id, battles_lost)
            VALUES ($1, 1)
            ON CONFLICT (catch_id)
            DO UPDATE SET battles_lost = pokemon_stats.battles_lost + 1
        ''', loser_pokemon_id)


async def get_battle_stats(user_id: int, guild_id: int) -> Dict:
    """Get battle statistics for a user"""
    if not pool:
        return {'wins': 0, 'losses': 0}

    async with pool.acquire() as conn:
        wins = await conn.fetchval('''
            SELECT COUNT(*) FROM battle_history
            WHERE winner_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

        losses = await conn.fetchval('''
            SELECT COUNT(*) FROM battle_history
            WHERE loser_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

        return {'wins': wins or 0, 'losses': losses or 0}


async def get_species_level(user_id: int, guild_id: int, pokemon_id: int, pokemon_name: str) -> int:
    """Get the level of a Pokemon species for a user"""
    if not pool:
        return 1

    async with pool.acquire() as conn:
        level = await conn.fetchval('''
            SELECT level FROM pokemon_species_stats
            WHERE user_id = $1 AND guild_id = $2 AND pokemon_id = $3
        ''', user_id, guild_id, pokemon_id)

        return level if level else 1


async def get_multiple_species_levels(user_id: int, guild_id: int, pokemon_ids: list) -> dict:
    """Get levels for multiple Pokemon species at once. Returns dict of {pokemon_id: level}"""
    if not pool or not pokemon_ids:
        return {pid: 1 for pid in pokemon_ids}

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT pokemon_id, level FROM pokemon_species_stats
            WHERE user_id = $1 AND guild_id = $2 AND pokemon_id = ANY($3)
        ''', user_id, guild_id, pokemon_ids)

        # Create dict with levels, defaulting to 1 if not found
        level_dict = {pid: 1 for pid in pokemon_ids}
        for row in rows:
            level_dict[row['pokemon_id']] = row['level']

        return level_dict


async def add_species_xp(user_id: int, guild_id: int, pokemon_id: int, pokemon_name: str, xp_amount: int, is_win: bool = True) -> Dict:
    """Add XP to a Pokemon species and handle level ups"""
    if not pool:
        return None

    async with pool.acquire() as conn:
        # Get or create species entry
        species = await conn.fetchrow('''
            INSERT INTO pokemon_species_stats (user_id, guild_id, pokemon_id, pokemon_name, experience, level)
            VALUES ($1, $2, $3, $4, $5, 1)
            ON CONFLICT (user_id, guild_id, pokemon_id)
            DO UPDATE SET experience = pokemon_species_stats.experience + $5
            RETURNING *
        ''', user_id, guild_id, pokemon_id, pokemon_name, xp_amount)

        # Update win/loss count
        if is_win:
            await conn.execute('''
                UPDATE pokemon_species_stats
                SET battles_won = battles_won + 1
                WHERE user_id = $1 AND guild_id = $2 AND pokemon_id = $3
            ''', user_id, guild_id, pokemon_id)
        else:
            await conn.execute('''
                UPDATE pokemon_species_stats
                SET battles_lost = battles_lost + 1
                WHERE user_id = $1 AND guild_id = $2 AND pokemon_id = $3
            ''', user_id, guild_id, pokemon_id)

        # Calculate new level (100 XP per level, no cap)
        new_level = (species['experience'] // 100) + 1
        old_level = species['level']

        # Update level if it changed
        if new_level != old_level:
            await conn.execute('''
                UPDATE pokemon_species_stats
                SET level = $1
                WHERE user_id = $2 AND guild_id = $3 AND pokemon_id = $4
            ''', new_level, user_id, guild_id, pokemon_id)

            return {
                'leveled_up': True,
                'old_level': old_level,
                'new_level': new_level,
                'current_xp': species['experience'],
                'pokemon_name': pokemon_name
            }

        return {
            'leveled_up': False,
            'level': new_level,
            'current_xp': species['experience'],
            'pokemon_name': pokemon_name
        }


# Battlepass functions (LEGACY - kept for historical data, no longer actively used)

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


async def _initialize_shop_items(conn):
    """Initialize shop items with pack configurations"""
    import json

    # Define shop items with pack configurations
    shop_items = [
        ('pack', 'Basic Pack', 'Standard pack with a few random Pokemon', 100, {
            'min_pokemon': 3,
            'max_pokemon': 5,
            'shiny_chance': 0.0001,  # 0.01%
            'legendary_chance': 0.05,  # 5%
            'mega_pack_chance': 0,
            'mega_pack_size': 0
        }),
        ('pack', 'Booster Pack', 'Enhanced pack with better odds and more Pokemon!', 250, {
            'min_pokemon': 5,
            'max_pokemon': 8,
            'shiny_chance': 0.0005,  # 0.05%
            'legendary_chance': 0.10,  # 10%
            'mega_pack_chance': 0.15,  # 15%
            'mega_pack_size': 12
        }),
        ('pack', 'Premium Pack', 'Premium pack with guaranteed rare Pokemon and excellent shiny odds!', 500, {
            'min_pokemon': 8,
            'max_pokemon': 12,
            'shiny_chance': 0.001,  # 0.1%
            'legendary_chance': 0.20,  # 20%
            'mega_pack_chance': 0.25,  # 25%
            'mega_pack_size': 15,
            'guaranteed_rare': True
        }),
        ('pack', 'Elite Trainer Pack', 'Elite pack for serious trainers! Multiple guaranteed rares with amazing shiny rates!', 1000, {
            'min_pokemon': 12,
            'max_pokemon': 18,
            'shiny_chance': 0.005,  # 0.5%
            'legendary_chance': 0.40,  # 40%
            'mega_pack_chance': 0.35,  # 35%
            'mega_pack_size': 20,
            'guaranteed_rare': True,
            'guaranteed_rare_count': 3
        }),
        ('pack', 'Master Collection', 'Ultimate pack! Guaranteed shiny or multiple legendaries with the best odds!', 2500, {
            'min_pokemon': 20,
            'max_pokemon': 25,
            'shiny_chance': 0.01,  # 1%
            'legendary_chance': 0.60,  # 60%
            'mega_pack_chance': 0.50,  # 50%
            'mega_pack_size': 30,
            'guaranteed_shiny_or_legendaries': True,
            'guaranteed_legendary_count': 3
        }),
    ]

    for item_type, item_name, description, price, pack_config in shop_items:
        await conn.execute('''
            INSERT INTO shop_items (item_type, item_name, description, price, pack_config)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (item_name) DO NOTHING
        ''', item_type, item_name, description, price, json.dumps(pack_config))


async def add_xp(user_id: int, guild_id: int, xp_amount: int = 10, season: int = 1):
    """DEPRECATED: Battlepass XP system removed - quests now reward currency directly"""
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
    """DEPRECATED: Battlepass system removed - kept for legacy data access only"""
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
    """DEPRECATED: Battlepass system removed - kept for legacy data access only"""
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

async def add_pack(user_id: int, guild_id: int, pack_name: str, pack_config: dict):
    """Add a specific pack to user's inventory"""
    if not pool:
        return

    import json

    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO user_packs (user_id, guild_id, pack_name, pack_config)
            VALUES ($1, $2, $3, $4)
        ''', user_id, guild_id, pack_name, json.dumps(pack_config))


async def add_packs(user_id: int, guild_id: int, pack_tier: int):
    """DEPRECATED: Was used by battlepass rewards - kept for legacy compatibility"""
    if not pool:
        return

    # Map tier numbers to pack names
    pack_tiers = {
        1: 'Basic Pack',
        2: 'Booster Pack',
        3: 'Premium Pack',
        4: 'Elite Trainer Pack',
        5: 'Master Collection'
    }

    pack_name = pack_tiers.get(pack_tier, 'Basic Pack')

    # Get pack config from shop
    async with pool.acquire() as conn:
        pack_data = await conn.fetchrow('''
            SELECT pack_config FROM shop_items
            WHERE item_name = $1
        ''', pack_name)

        if pack_data:
            await add_pack(user_id, guild_id, pack_name, pack_data['pack_config'])


async def get_user_packs(user_id: int, guild_id: int) -> List[Dict]:
    """Get all packs in user's inventory"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT id, pack_name, pack_config, acquired_at
            FROM user_packs
            WHERE user_id = $1 AND guild_id = $2
            ORDER BY acquired_at DESC
        ''', user_id, guild_id)

        return [dict(row) for row in rows]


async def get_pack_count(user_id: int, guild_id: int) -> int:
    """Get total number of packs a user has"""
    if not pool:
        return 0

    async with pool.acquire() as conn:
        count = await conn.fetchval('''
            SELECT COUNT(*) FROM user_packs
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

        return count if count else 0


async def use_pack(user_id: int, guild_id: int, pack_id: int) -> Optional[Dict]:
    """Use a specific pack from user's inventory. Returns pack data if successful."""
    if not pool:
        return None

    async with pool.acquire() as conn:
        # Get pack data
        pack = await conn.fetchrow('''
            SELECT pack_name, pack_config FROM user_packs
            WHERE id = $1 AND user_id = $2 AND guild_id = $3
        ''', pack_id, user_id, guild_id)

        if not pack:
            return None

        # Delete the pack
        await conn.execute('''
            DELETE FROM user_packs WHERE id = $1
        ''', pack_id)

        return dict(pack)


# Daily Quest functions

async def get_daily_quests(user_id: int, guild_id: int) -> Optional[Dict]:
    """Get user's daily quests for today"""
    if not pool:
        return None
    
    from datetime import date
    today = date.today()
    
    async with pool.acquire() as conn:
        quests = await conn.fetchrow('''
            SELECT * FROM daily_quests
            WHERE user_id = $1 AND guild_id = $2 AND quest_date = $3
        ''', user_id, guild_id, today)
        
        return dict(quests) if quests else None


async def create_daily_quests(user_id: int, guild_id: int, quests: List[Dict]) -> bool:
    """Create daily quests for a user"""
    if not pool:
        return False
    
    from datetime import date
    today = date.today()
    
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO daily_quests (
                user_id, guild_id, quest_date,
                quest_1_type, quest_1_target, quest_1_reward,
                quest_2_type, quest_2_target, quest_2_reward,
                quest_3_type, quest_3_target, quest_3_reward
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (user_id, guild_id, quest_date) DO NOTHING
        ''', user_id, guild_id, today,
             quests[0]['type'], quests[0]['target'], quests[0]['reward'],
             quests[1]['type'], quests[1]['target'], quests[1]['reward'],
             quests[2]['type'], quests[2]['target'], quests[2]['reward'])
        
        return True


async def update_quest_progress(user_id: int, guild_id: int, quest_type: str, increment: int = 1) -> Optional[Dict]:
    """Update progress for quests of a specific type and check for completion"""
    if not pool:
        return None
    
    from datetime import date
    today = date.today()
    
    async with pool.acquire() as conn:
        # Get current quests
        quests = await conn.fetchrow('''
            SELECT * FROM daily_quests
            WHERE user_id = $1 AND guild_id = $2 AND quest_date = $3
        ''', user_id, guild_id, today)
        
        if not quests:
            return None
        
        completed_quests = []
        total_xp_earned = 0
        
        # Check each quest
        for i in range(1, 4):
            q_type = quests[f'quest_{i}_type']
            q_target = quests[f'quest_{i}_target']
            q_progress = quests[f'quest_{i}_progress']
            q_completed = quests[f'quest_{i}_completed']
            q_reward = quests[f'quest_{i}_reward']
            
            # Update matching quest types that aren't completed
            if q_type == quest_type and not q_completed:
                new_progress = q_progress + increment
                
                # Check if quest is now completed
                if new_progress >= q_target:
                    await conn.execute(f'''
                        UPDATE daily_quests
                        SET quest_{i}_progress = $1, quest_{i}_completed = TRUE
                        WHERE user_id = $2 AND guild_id = $3 AND quest_date = $4
                    ''', q_target, user_id, guild_id, today)
                    
                    completed_quests.append({
                        'description': f'Quest {i}',
                        'reward': q_reward
                    })
                    total_xp_earned += q_reward  # Using the same variable for currency now
                else:
                    # Just update progress
                    await conn.execute(f'''
                        UPDATE daily_quests
                        SET quest_{i}_progress = $1
                        WHERE user_id = $2 AND guild_id = $3 AND quest_date = $4
                    ''', new_progress, user_id, guild_id, today)
        
        if completed_quests:
            return {
                'completed_quests': completed_quests,
                'total_currency': total_xp_earned,  # Return as currency now
                'total_xp': total_xp_earned  # Keep for backwards compatibility during transition
            }

        return None


# Currency/Economy functions

async def get_balance(user_id: int, guild_id: int) -> int:
    """Get user's Pokedollar balance"""
    if not pool:
        return 0

    async with pool.acquire() as conn:
        balance = await conn.fetchval('''
            SELECT balance FROM user_currency
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

        return balance if balance is not None else 0


async def add_currency(user_id: int, guild_id: int, amount: int) -> int:
    """Add currency to user's balance. Returns new balance."""
    if not pool:
        return 0

    async with pool.acquire() as conn:
        result = await conn.fetchrow('''
            INSERT INTO user_currency (user_id, guild_id, balance, total_earned)
            VALUES ($1, $2, $3, $3)
            ON CONFLICT (user_id, guild_id)
            DO UPDATE SET
                balance = user_currency.balance + $3,
                total_earned = user_currency.total_earned + $3,
                last_updated = NOW()
            RETURNING balance
        ''', user_id, guild_id, amount)

        return result['balance'] if result else 0


async def spend_currency(user_id: int, guild_id: int, amount: int) -> bool:
    """Spend currency. Returns True if successful, False if insufficient funds."""
    if not pool:
        return False

    async with pool.acquire() as conn:
        # Check if user has enough
        balance = await conn.fetchval('''
            SELECT balance FROM user_currency
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

        if not balance or balance < amount:
            return False

        # Deduct amount
        await conn.execute('''
            UPDATE user_currency
            SET balance = balance - $3,
                total_spent = total_spent + $3,
                last_updated = NOW()
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id, amount)

        return True


async def get_shop_items() -> List[Dict]:
    """Get all active shop items"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT * FROM shop_items
            WHERE is_active = TRUE
            ORDER BY price ASC
        ''')

        return [dict(row) for row in rows]


async def get_duplicate_pokemon(user_id: int, guild_id: int) -> List[Dict]:
    """Get Pokemon that user has duplicates of (count > 1)"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT
                pokemon_name,
                pokemon_id,
                COUNT(*) as count,
                MIN(id) as first_catch_id
            FROM catches
            WHERE user_id = $1 AND guild_id = $2
            GROUP BY pokemon_name, pokemon_id
            HAVING COUNT(*) > 1
            ORDER BY count DESC, pokemon_name ASC
        ''', user_id, guild_id)

        return [dict(row) for row in rows]


def calculate_sell_price(pokemon_id: int, is_shiny: bool = False) -> int:
    """Calculate sell price based on Pokemon rarity and shiny status"""
    # Gen 1 legendaries: Articuno (144), Zapdos (145), Moltres (146), Mewtwo (150), Mew (151)
    legendary_ids = [144, 145, 146, 150, 151]

    # Starter Pokemon and their evolutions
    starter_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9]

    # Pseudo-legendaries and rare Pokemon
    rare_ids = [3, 6, 9, 59, 65, 68, 76, 94, 103, 112, 115, 130, 131, 142, 143]

    if pokemon_id in legendary_ids:
        base_price = 100  # Legendaries worth 100
    elif pokemon_id in rare_ids:
        base_price = 50   # Rare Pokemon worth 50
    elif pokemon_id in starter_ids:
        base_price = 30   # Starters worth 30
    else:
        base_price = 10   # Common Pokemon worth 10

    # 5x multiplier for shinies
    if is_shiny:
        return base_price * 5

    return base_price


async def sell_pokemon(user_id: int, guild_id: int, catch_id: int) -> Optional[int]:
    """Sell a Pokemon. Returns sale price if successful, None if failed."""
    if not pool:
        return None

    async with pool.acquire() as conn:
        # Verify Pokemon exists and belongs to user
        pokemon = await conn.fetchrow('''
            SELECT user_id, guild_id, pokemon_id, pokemon_name, is_shiny FROM catches
            WHERE id = $1
        ''', catch_id)

        if not pokemon or pokemon['user_id'] != user_id or pokemon['guild_id'] != guild_id:
            return None

        # Calculate sale price based on rarity and shiny status
        sale_price = calculate_sell_price(pokemon['pokemon_id'], pokemon.get('is_shiny', False))

        # Delete the Pokemon
        await conn.execute('''
            DELETE FROM catches WHERE id = $1
        ''', catch_id)

        # Add currency
        await add_currency(user_id, guild_id, sale_price)

        return sale_price


# Gym badge functions

async def get_user_badges(user_id: int, guild_id: int) -> List[str]:
    """Get list of gym badges earned by user"""
    if not pool:
        return []

    async with pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT gym_name FROM gym_badges
            WHERE user_id = $1 AND guild_id = $2
            ORDER BY earned_at ASC
        ''', user_id, guild_id)

        return [row['gym_name'] for row in rows]


async def award_gym_badge(user_id: int, guild_id: int, gym_name: str) -> bool:
    """Award a gym badge to a user. Returns True if newly awarded, False if already owned."""
    if not pool:
        return False

    async with pool.acquire() as conn:
        try:
            await conn.execute('''
                INSERT INTO gym_badges (user_id, guild_id, gym_name)
                VALUES ($1, $2, $3)
            ''', user_id, guild_id, gym_name)
            return True
        except:
            # Badge already exists (primary key constraint)
            return False


async def has_gym_badge(user_id: int, guild_id: int, gym_name: str) -> bool:
    """Check if user has a specific gym badge"""
    if not pool:
        return False

    async with pool.acquire() as conn:
        exists = await conn.fetchval('''
            SELECT EXISTS(
                SELECT 1 FROM gym_badges
                WHERE user_id = $1 AND guild_id = $2 AND gym_name = $3
            )
        ''', user_id, guild_id, gym_name)

        return exists if exists else False


async def get_badge_count(user_id: int, guild_id: int) -> int:
    """Get total number of badges earned by user"""
    if not pool:
        return 0

    async with pool.acquire() as conn:
        count = await conn.fetchval('''
            SELECT COUNT(*) FROM gym_badges
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

        return count if count else 0


async def get_pokemon_species_stats(user_id: int, guild_id: int, pokemon_id: int) -> Optional[Dict]:
    """Get detailed stats for a Pokemon species including level, XP, and battle record"""
    if not pool:
        return None

    async with pool.acquire() as conn:
        stats = await conn.fetchrow('''
            SELECT pokemon_id, pokemon_name, level, experience, battles_won, battles_lost
            FROM pokemon_species_stats
            WHERE user_id = $1 AND guild_id = $2 AND pokemon_id = $3
        ''', user_id, guild_id, pokemon_id)

        if stats:
            return dict(stats)
        return None


# Trainer battle cooldown functions

async def check_trainer_cooldown(user_id: int, guild_id: int) -> Dict:
    """Check trainer battle cooldown status. Returns battles_remaining and seconds_until_reset."""
    if not pool:
        return {'battles_remaining': 0, 'seconds_until_reset': 0}

    from datetime import datetime, timedelta

    async with pool.acquire() as conn:
        # Get or create cooldown entry
        cooldown = await conn.fetchrow('''
            INSERT INTO trainer_cooldowns (user_id, guild_id, battles_used, cooldown_reset)
            VALUES ($1, $2, 0, NOW())
            ON CONFLICT (user_id, guild_id)
            DO UPDATE SET user_id = trainer_cooldowns.user_id
            RETURNING battles_used, cooldown_reset
        ''', user_id, guild_id)

        if not cooldown:
            return {'battles_remaining': 3, 'seconds_until_reset': 0}

        now = datetime.now()
        reset_time = cooldown['cooldown_reset']

        # Check if an hour has passed since last reset
        if now >= reset_time + timedelta(hours=1):
            # Reset cooldown
            await conn.execute('''
                UPDATE trainer_cooldowns
                SET battles_used = 0, cooldown_reset = $3
                WHERE user_id = $1 AND guild_id = $2
            ''', user_id, guild_id, now)

            return {'battles_remaining': 3, 'seconds_until_reset': 0}

        # Calculate remaining battles and time until reset
        battles_used = cooldown['battles_used']
        battles_remaining = max(0, 3 - battles_used)
        time_until_reset = (reset_time + timedelta(hours=1)) - now
        seconds_until_reset = int(time_until_reset.total_seconds())

        return {
            'battles_remaining': battles_remaining,
            'seconds_until_reset': max(0, seconds_until_reset)
        }


async def use_trainer_battle(user_id: int, guild_id: int) -> bool:
    """Use one trainer battle. Returns True if successful, False if no battles remaining."""
    if not pool:
        return False

    async with pool.acquire() as conn:
        # Check if user has battles remaining
        cooldown = await check_trainer_cooldown(user_id, guild_id)

        if cooldown['battles_remaining'] <= 0:
            return False

        # Increment battles_used
        await conn.execute('''
            UPDATE trainer_cooldowns
            SET battles_used = battles_used + 1
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id)

        return True


async def reset_trainer_cooldown(user_id: int, guild_id: int):
    """Manually reset trainer cooldown (for admin/testing purposes)."""
    if not pool:
        return

    from datetime import datetime

    async with pool.acquire() as conn:
        await conn.execute('''
            UPDATE trainer_cooldowns
            SET battles_used = 0, cooldown_reset = $3
            WHERE user_id = $1 AND guild_id = $2
        ''', user_id, guild_id, datetime.now())
