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
active_spawns = {}  # {channel_id: {pokemon_data, spawn_time}}


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
        title="A wild Pokemon appeared!",
        description=f"Type `ball` to catch it!",
        color=discord.Color.green()
    )

    if pokemon['sprite']:
        embed.set_image(url=pokemon['sprite'])

    embed.set_footer(text="First person to type 'ball' catches it!")

    return embed


def create_catch_embed(pokemon, user):
    """Create an embed for a successful catch"""
    types_str = ', '.join(pokemon['types']).title()

    embed = discord.Embed(
        title=f"{user.display_name} caught {pokemon['name']}!",
        description=f"**Type:** {types_str}\n**Pokedex #:** {pokemon['id']}",
        color=discord.Color.gold()
    )

    if pokemon['sprite']:
        embed.set_thumbnail(url=pokemon['sprite'])

    return embed


@bot.event
async def on_ready():
    """Called when bot is ready"""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')

    # Setup database
    await db.setup_database()

    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} slash command(s)')
    except Exception as e:
        print(f'Failed to sync commands: {e}')

    # Start spawn loop
    if not spawn_pokemon.is_running():
        spawn_pokemon.start()
        print('Pokemon spawn loop started')


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
            pokemon = active_spawns[channel_id]
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

            # Send catch confirmation
            embed = create_catch_embed(pokemon, message.author)
            await message.channel.send(embed=embed)

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
                # Store active spawn
                active_spawns[str(channel.id)] = pokemon

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


@bot.tree.command(name='help', description='Show bot commands and how to use them')
async def help_command(interaction: discord.Interaction):
    """Show bot commands"""
    embed = discord.Embed(
        title="Mon Bot Commands",
        description="Catch Pokemon that randomly appear in chat!",
        color=discord.Color.orange()
    )

    embed.add_field(
        name="Catching",
        value="Type `ball` when a Pokemon spawns to catch it!",
        inline=False
    )

    embed.add_field(
        name="/setup #channel",
        value="(Admin only) Configure which channel Pokemon spawn in",
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

    await interaction.response.send_message(embed=embed)


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
