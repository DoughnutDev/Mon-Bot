import discord
from discord import app_commands
from discord.ext import commands, tasks
import aiohttp
import asyncio
import random
import os
from dotenv import load_dotenv
from datetime import datetime

# Import database functions
import database as db

# Load environment variables
load_dotenv()

# Bot configuration
TOKEN = os.getenv('DISCORD_TOKEN')
DEFAULT_SPAWN_MIN = 180  # 3 minutes
DEFAULT_SPAWN_MAX = 600  # 10 minutes

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Global variables
active_spawns = {}  # {channel_id: {'pokemon': pokemon_data, 'spawn_time': datetime}}


async def fetch_pokemon(session, pokemon_id=None):
    """Fetch a random or specific Pokemon from PokeAPI"""
    if pokemon_id is None:
        pokemon_id = random.randint(1, 898)  # Gen 1-8 Pokemon

    url = f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}'

    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return {
                    'id': data['id'],
                    'name': data['name'].capitalize(),
                    'sprite': data['sprites']['front_default'],
                    'types': [t['type']['name'] for t in data['types']],
                    'height': data['height'],
                    'weight': data['weight']
                }
    except Exception as e:
        print(f"Error fetching Pokemon: {e}")

    return None


def create_spawn_embed(pokemon):
    """Create an embed for a spawned Pokemon"""
    embed = discord.Embed(
        title=f"A wild {pokemon['name']} appeared!",
        description=f"Type `ball` to catch it!",
        color=discord.Color.green()
    )

    if pokemon['sprite']:
        embed.set_image(url=pokemon['sprite'])

    embed.set_footer(text="First person to type 'ball' catches it!")

    return embed


def create_catch_embed(pokemon, user, time_taken):
    """Create an embed for a successful catch"""
    types_str = ', '.join(pokemon['types']).title()

    # Format time - show minutes if over 60 seconds, otherwise just seconds
    if time_taken >= 60:
        minutes = int(time_taken // 60)
        seconds = int(time_taken % 60)
        time_str = f"{minutes}m {seconds}s" if seconds > 0 else f"{minutes}m"
    else:
        time_str = f"{int(time_taken)}s"

    embed = discord.Embed(
        title=f"{user.display_name} caught {pokemon['name']}!",
        description=f"**Type:** {types_str}\n**Pokedex #:** {pokemon['id']}\n**Caught in:** {time_str}",
        color=discord.Color.gold()
    )

    if pokemon['sprite']:
        embed.set_thumbnail(url=pokemon['sprite'])

    return embed


def create_level_up_embed(user, new_level, rewards):
    """Create an embed for battlepass level up"""
    embed = discord.Embed(
        title=f"🎉 Level Up!",
        description=f"{user.display_name} reached **Level {new_level}**!",
        color=discord.Color.purple()
    )

    if rewards:
        rewards_text = []
        for reward in rewards:
            if reward['type'] == 'pack':
                pack_word = 'pack' if reward['amount'] == 1 else 'packs'
                rewards_text.append(f"Level {reward['level']}: {reward['amount']} {pack_word}")

        if rewards_text:
            embed.add_field(
                name="🎁 Rewards Earned",
                value='\n'.join(rewards_text),
                inline=False
            )

    embed.set_footer(text="Use /pack to open your packs!")

    return embed


@bot.event
async def on_ready():
    """Called when bot is ready"""
    print(f'{bot.user} has connected to Discord!', flush=True)
    print(f'Bot is in {len(bot.guilds)} guilds', flush=True)

    # Setup database
    print('Setting up database...', flush=True)
    try:
        await db.setup_database()
        print('Database setup complete!', flush=True)
    except Exception as e:
        print(f'ERROR: Database setup failed: {e}', flush=True)
        import traceback
        traceback.print_exc()

    # Sync slash commands
    print('Syncing slash commands...', flush=True)
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} slash command(s)', flush=True)
        print(f'Commands: {[cmd.name for cmd in synced]}', flush=True)
    except Exception as e:
        print(f'Failed to sync commands: {e}', flush=True)
        import traceback
        traceback.print_exc()

    # Start spawn loop
    if not spawn_pokemon.is_running():
        spawn_pokemon.start()
        print('Pokemon spawn loop started', flush=True)


@bot.event
async def on_message(message):
    """Handle messages"""
    # Ignore bot messages
    if message.author.bot:
        return

    # Check if someone is trying to catch
    if message.content.lower() == 'ball':
        channel_id = str(message.channel.id)

        if channel_id in active_spawns:
            spawn_data = active_spawns[channel_id]
            pokemon = spawn_data['pokemon']
            spawn_time = spawn_data['spawn_time']

            # Calculate time taken to catch
            catch_time = datetime.now()
            time_taken = (catch_time - spawn_time).total_seconds()

            user_id = message.author.id
            guild_id = message.guild.id if message.guild else 0

            # Save catch to database
            await db.add_catch(
                user_id=user_id,
                guild_id=guild_id,
                pokemon_name=pokemon['name'],
                pokemon_id=pokemon['id'],
                pokemon_types=pokemon['types']
            )

            # Add XP to battlepass (10 XP per catch)
            xp_result = await db.add_xp(user_id, guild_id, xp_amount=10)

            # Send catch confirmation with time
            embed = create_catch_embed(pokemon, message.author, time_taken)
            await message.channel.send(embed=embed)

            # If user leveled up, send level up message
            if xp_result and xp_result['leveled_up']:
                level_embed = create_level_up_embed(
                    message.author,
                    xp_result['new_level'],
                    xp_result['rewards']
                )
                await message.channel.send(embed=level_embed)

            # Remove active spawn
            del active_spawns[channel_id]


@tasks.loop(seconds=60)  # Check every minute
async def spawn_pokemon():
    """Periodically spawn Pokemon in designated channels"""
    # Get all configured spawn channels from database
    guild_channels = await db.get_all_spawn_channels()

    if not guild_channels:
        return

    # For each guild, check if it's time to spawn
    for guild_id, channel_ids in guild_channels.items():
        if not channel_ids:
            continue

        # Random chance to spawn (creates randomness)
        if random.random() > 0.15:  # 15% chance per minute = avg ~6-7 min
            continue

        # Pick a random channel from this guild's configured channels
        channel_id = random.choice(channel_ids)

        # Skip if there's already an active spawn in this channel
        if str(channel_id) in active_spawns:
            continue

        try:
            channel = bot.get_channel(channel_id)

            if channel is None:
                continue

            # Fetch random Pokemon
            async with aiohttp.ClientSession() as session:
                pokemon = await fetch_pokemon(session)

            if pokemon:
                # Store active spawn with timestamp
                active_spawns[str(channel.id)] = {
                    'pokemon': pokemon,
                    'spawn_time': datetime.now()
                }

                # Send spawn message
                embed = create_spawn_embed(pokemon)
                await channel.send(embed=embed)

                print(f"Spawned {pokemon['name']} in {channel.guild.name}#{channel.name}")

        except Exception as e:
            print(f"Error spawning Pokemon in channel {channel_id}: {e}")


@bot.tree.command(name='setup', description='Configure Mon Bot for your server (Admin only)')
@app_commands.describe(channel='The channel where Pokemon should spawn')
@app_commands.default_permissions(administrator=True)
async def setup(interaction: discord.Interaction, channel: discord.TextChannel):
    """Setup command for server admins to configure spawn channels"""
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        return

    # Defer the response immediately to prevent timeout
    await interaction.response.defer()

    # Add spawn channel to database
    await db.set_spawn_channel(interaction.guild.id, channel.id)

    embed = discord.Embed(
        title="Mon Bot Setup Complete!",
        description=f"Pokemon will now spawn in {channel.mention}",
        color=discord.Color.green()
    )

    embed.add_field(
        name="What's Next?",
        value="Pokemon will randomly appear in this channel. Type `ball` to catch them!",
        inline=False
    )

    await interaction.followup.send(embed=embed)
    print(f"Setup completed for {interaction.guild.name} - Channel: #{channel.name}")


@bot.tree.command(name='spawn', description='Force spawn a Pokemon immediately (Admin only)')
@app_commands.default_permissions(administrator=True)
async def spawn_command(interaction: discord.Interaction):
    """Admin command to force spawn a Pokemon for testing"""
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        return

    channel_id = str(interaction.channel.id)

    # Check if there's already a spawn in this channel
    if channel_id in active_spawns:
        await interaction.response.send_message(
            "There's already a Pokemon active in this channel! Catch it first before spawning another.",
            ephemeral=True
        )
        return

    # Defer the response
    await interaction.response.defer(ephemeral=True)

    try:
        # Fetch random Pokemon
        async with aiohttp.ClientSession() as session:
            pokemon = await fetch_pokemon(session)

        if pokemon:
            # Store active spawn with timestamp
            active_spawns[channel_id] = {
                'pokemon': pokemon,
                'spawn_time': datetime.now()
            }

            # Send spawn message
            embed = create_spawn_embed(pokemon)
            await interaction.channel.send(embed=embed)

            # Send confirmation to admin
            await interaction.followup.send(
                f"✅ Spawned {pokemon['name']} in this channel!",
                ephemeral=True
            )

            print(f"Admin spawned {pokemon['name']} in {interaction.guild.name}#{interaction.channel.name}")
        else:
            await interaction.followup.send(
                "❌ Failed to fetch Pokemon from API. Try again!",
                ephemeral=True
            )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error spawning Pokemon: {str(e)}",
            ephemeral=True
        )
        print(f"Error in spawn command: {e}")


@bot.tree.command(name='pokedex', description='View your Pokedex or another user\'s')
@app_commands.describe(member='The user whose Pokedex you want to view (optional)')
async def pokedex(interaction: discord.Interaction, member: discord.Member = None):
    """View your or another user's caught Pokemon"""
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        return

    # Defer the response immediately to prevent timeout
    await interaction.response.defer()

    target = member or interaction.user
    user_id = target.id
    guild_id = interaction.guild.id

    # Get user stats from database
    stats = await db.get_user_stats(user_id, guild_id)

    if stats['total'] == 0:
        await interaction.followup.send(f"{target.display_name} hasn't caught any Pokemon yet!")
        return

    # Get recent catches
    catches = await db.get_user_catches(user_id, guild_id)

    embed = discord.Embed(
        title=f"{target.display_name}'s Pokedex",
        description=f"**Total Caught:** {stats['total']}\n**Unique Pokemon:** {stats['unique']}",
        color=discord.Color.blue()
    )

    # Show last 10 catches
    recent = catches[:10]
    recent_str = '\n'.join([f"#{c['pokemon_id']} {c['pokemon_name']}" for c in recent])

    embed.add_field(name="Recent Catches", value=recent_str or "None", inline=False)

    await interaction.followup.send(embed=embed)


@bot.tree.command(name='count', description='See how many of each Pokemon you\'ve caught')
async def count(interaction: discord.Interaction):
    """Show how many of each Pokemon you've caught"""
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        return

    # Defer the response immediately to prevent timeout
    await interaction.response.defer()

    user_id = interaction.user.id
    guild_id = interaction.guild.id

    # Get catch counts from database
    counts = await db.get_user_catch_counts(user_id, guild_id)

    if not counts:
        await interaction.followup.send("You haven't caught any Pokemon yet!")
        return

    # Create embed
    embed = discord.Embed(
        title=f"{interaction.user.display_name}'s Pokemon Collection",
        color=discord.Color.purple()
    )

    # Show top 15
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    count_str = '\n'.join([f"{name}: {count}" for name, count in sorted_counts[:15]])
    embed.add_field(name="Top Pokemon", value=count_str, inline=False)

    if len(sorted_counts) > 15:
        embed.set_footer(text=f"... and {len(sorted_counts) - 15} more")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name='battlepass', description='View your Season 1 battlepass progress')
async def battlepass(interaction: discord.Interaction):
    """View battlepass progress"""
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        return

    # Defer the response immediately to prevent timeout
    await interaction.response.defer()

    user_id = interaction.user.id
    guild_id = interaction.guild.id

    # Get battlepass progress
    progress = await db.get_battlepass_progress(user_id, guild_id, season=1)
    pack_count = await db.get_pack_count(user_id, guild_id)

    # Get all rewards for Season 1
    all_rewards = await db.get_battlepass_rewards(season=1)

    level = progress.get('level', 1)
    xp = progress.get('xp', 0)

    # Calculate XP progress for current level
    current_level_xp = xp % 100
    xp_needed = 100

    # Create embed
    embed = discord.Embed(
        title="Season 1 Battlepass",
        description=f"{interaction.user.display_name}'s Progress",
        color=discord.Color.purple()
    )

    embed.add_field(
        name="📊 Level",
        value=f"**{level}** / 50",
        inline=True
    )

    embed.add_field(
        name="⭐ XP",
        value=f"{current_level_xp} / {xp_needed}",
        inline=True
    )

    embed.add_field(
        name="📦 Packs",
        value=f"{pack_count}",
        inline=True
    )

    # Show next rewards
    next_rewards = [r for r in all_rewards if r['level'] > level][:3]
    if next_rewards:
        rewards_text = []
        for reward in next_rewards:
            pack_word = 'pack' if reward['reward_value'] == 1 else 'packs'
            rewards_text.append(f"Level {reward['level']}: {reward['reward_value']} {pack_word}")

        embed.add_field(
            name="🎁 Upcoming Rewards",
            value='\n'.join(rewards_text),
            inline=False
        )

    embed.set_footer(text="Catch Pokemon to gain 10 XP each!")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name='pack', description='Open a Pokemon pack (10 random Pokemon)')
async def pack(interaction: discord.Interaction):
    """Open a Pokemon pack"""
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        return

    # Defer the response immediately to prevent timeout
    await interaction.response.defer()

    user_id = interaction.user.id
    guild_id = interaction.guild.id

    # Check pack count
    pack_count = await db.get_pack_count(user_id, guild_id)

    if pack_count < 1:
        embed = discord.Embed(
            title="No Packs Available",
            description="You don't have any packs to open!\n\nEarn packs by leveling up your battlepass.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="How to get packs",
            value="Use `/battlepass` to see your progress and upcoming rewards!",
            inline=False
        )
        await interaction.followup.send(embed=embed)
        return

    # Use one pack
    success = await db.use_pack(user_id, guild_id)

    if not success:
        await interaction.followup.send("Failed to open pack. Please try again!")
        return

    # Generate 10 random Pokemon
    pokemon_list = []
    async with aiohttp.ClientSession() as session:
        for _ in range(10):
            pokemon = await fetch_pokemon(session)
            if pokemon:
                pokemon_list.append(pokemon)
                # Add to user's collection
                await db.add_catch(
                    user_id=user_id,
                    guild_id=guild_id,
                    pokemon_name=pokemon['name'],
                    pokemon_id=pokemon['id'],
                    pokemon_types=pokemon['types']
                )

    if not pokemon_list:
        await interaction.followup.send("Error opening pack. Please try again!")
        return

    # Create pack opening embed
    embed = discord.Embed(
        title="📦 Pack Opened!",
        description=f"{interaction.user.display_name} opened a pack!",
        color=discord.Color.gold()
    )

    # List all Pokemon from the pack
    pokemon_names = [f"#{p['id']} {p['name']}" for p in pokemon_list]
    # Split into 2 columns for better display
    col1 = '\n'.join(pokemon_names[:5])
    col2 = '\n'.join(pokemon_names[5:])

    embed.add_field(name="Pokemon (1-5)", value=col1, inline=True)
    embed.add_field(name="Pokemon (6-10)", value=col2, inline=True)

    remaining_packs = pack_count - 1
    pack_word = 'pack' if remaining_packs == 1 else 'packs'
    embed.set_footer(text=f"Remaining packs: {remaining_packs} {pack_word}")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name='help', description='Show bot commands and how to use them')
async def help_command(interaction: discord.Interaction):
    """Show bot commands"""
    # Defer immediately to prevent timeout
    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="Mon Bot Commands",
        description="Catch Pokemon that randomly appear in chat!",
        color=discord.Color.orange()
    )

    embed.add_field(
        name="Catching",
        value="Type `ball` when a Pokemon spawns to catch it! (+10 XP)",
        inline=False
    )

    embed.add_field(
        name="/battlepass",
        value="View your Season 1 battlepass progress and rewards",
        inline=False
    )

    embed.add_field(
        name="/pack",
        value="Open a Pokemon pack (10 random Pokemon)",
        inline=False
    )

    embed.add_field(
        name="/pokedex [@user]",
        value="View your Pokedex (or another user's)",
        inline=False
    )

    embed.add_field(
        name="/count",
        value="See how many of each Pokemon you've caught",
        inline=False
    )

    embed.add_field(
        name="/setup #channel",
        value="(Admin only) Configure which channel Pokemon spawn in",
        inline=False
    )

    embed.add_field(
        name="/spawn",
        value="(Admin only) Force spawn a Pokemon immediately for testing",
        inline=False
    )

    embed.set_footer(text="Season 1 Battlepass: Catch Pokemon to earn XP and unlock packs!")

    await interaction.followup.send(embed=embed, ephemeral=True)


# Cleanup on shutdown
@bot.event
async def on_shutdown():
    """Cleanup when bot shuts down"""
    await db.close_database()


# Run the bot
if __name__ == '__main__':
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN not found in .env file!")
        print("Please create a .env file with your bot token.")
    else:
        try:
            bot.run(TOKEN)
        finally:
            # Ensure database connection is closed
            import asyncio
            asyncio.run(db.close_database())
