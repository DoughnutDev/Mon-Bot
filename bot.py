import discord
from discord.ext import commands, tasks
import aiohttp
import asyncio
import random
import os
from dotenv import load_dotenv
import json
from datetime import datetime

# Load environment variables
load_dotenv()

# Bot configuration
TOKEN = os.getenv('DISCORD_TOKEN')
SPAWN_CHANNELS = os.getenv('SPAWN_CHANNELS', '').split(',')
SPAWN_INTERVAL = int(os.getenv('SPAWN_INTERVAL', 300))  # Default 5 minutes

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Global variables
active_spawns = {}  # {channel_id: {pokemon_data, spawn_time}}
user_catches = {}  # Store caught pokemon per user

# File to store user data
DATA_FILE = 'user_data.json'


def load_user_data():
    """Load user catch data from file"""
    global user_catches
    try:
        with open(DATA_FILE, 'r') as f:
            user_catches = json.load(f)
    except FileNotFoundError:
        user_catches = {}


def save_user_data():
    """Save user catch data to file"""
    with open(DATA_FILE, 'w') as f:
        json.dump(user_catches, f, indent=4)


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

    # Load user data
    load_user_data()

    # Start spawn loop
    if SPAWN_CHANNELS and SPAWN_CHANNELS[0]:
        spawn_pokemon.start()
        print(f'Pokemon spawning enabled in {len(SPAWN_CHANNELS)} channels')
    else:
        print('No spawn channels configured. Set SPAWN_CHANNELS in .env')


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
            user_id = str(message.author.id)

            # Initialize user data if needed
            if user_id not in user_catches:
                user_catches[user_id] = {
                    'username': str(message.author),
                    'pokemon': []
                }

            # Add pokemon to user's collection
            user_catches[user_id]['pokemon'].append({
                'name': pokemon['name'],
                'id': pokemon['id'],
                'caught_at': datetime.now().isoformat(),
                'types': pokemon['types']
            })

            # Save data
            save_user_data()

            # Send catch confirmation
            embed = create_catch_embed(pokemon, message.author)
            await message.channel.send(embed=embed)

            # Remove active spawn
            del active_spawns[channel_id]

    # Process commands
    await bot.process_commands(message)


@tasks.loop(seconds=SPAWN_INTERVAL)
async def spawn_pokemon():
    """Periodically spawn Pokemon in designated channels"""
    if not SPAWN_CHANNELS or not SPAWN_CHANNELS[0]:
        return

    # Pick a random channel from configured channels
    channel_id = random.choice([c.strip() for c in SPAWN_CHANNELS if c.strip()])

    try:
        channel = bot.get_channel(int(channel_id))

        if channel is None:
            print(f"Could not find channel {channel_id}")
            return

        # Don't spawn if there's already an active spawn in this channel
        if str(channel.id) in active_spawns:
            return

        # Fetch random Pokemon
        async with aiohttp.ClientSession() as session:
            pokemon = await fetch_pokemon(session)

        if pokemon:
            # Store active spawn
            active_spawns[str(channel.id)] = pokemon

            # Send spawn message
            embed = create_spawn_embed(pokemon)
            await channel.send(embed=embed)

            print(f"Spawned {pokemon['name']} in {channel.name}")

    except Exception as e:
        print(f"Error spawning Pokemon: {e}")


@bot.command(name='pokedex')
async def pokedex(ctx, member: discord.Member = None):
    """View your or another user's caught Pokemon"""
    target = member or ctx.author
    user_id = str(target.id)

    if user_id not in user_catches or not user_catches[user_id]['pokemon']:
        await ctx.send(f"{target.display_name} hasn't caught any Pokemon yet!")
        return

    pokemon_list = user_catches[user_id]['pokemon']
    total = len(pokemon_list)

    # Count unique Pokemon
    unique = len(set(p['name'] for p in pokemon_list))

    embed = discord.Embed(
        title=f"{target.display_name}'s Pokedex",
        description=f"**Total Caught:** {total}\n**Unique Pokemon:** {unique}",
        color=discord.Color.blue()
    )

    # Show last 10 catches
    recent = pokemon_list[-10:]
    recent_str = '\n'.join([f"#{p['id']} {p['name']}" for p in reversed(recent)])

    embed.add_field(name="Recent Catches", value=recent_str or "None", inline=False)

    await ctx.send(embed=embed)


@bot.command(name='count')
async def count(ctx):
    """Show how many of each Pokemon you've caught"""
    user_id = str(ctx.author.id)

    if user_id not in user_catches or not user_catches[user_id]['pokemon']:
        await ctx.send("You haven't caught any Pokemon yet!")
        return

    pokemon_list = user_catches[user_id]['pokemon']

    # Count each Pokemon
    counts = {}
    for p in pokemon_list:
        name = p['name']
        counts[name] = counts.get(name, 0) + 1

    # Sort by count
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    # Create embed
    embed = discord.Embed(
        title=f"{ctx.author.display_name}'s Pokemon Collection",
        color=discord.Color.purple()
    )

    # Show top 15
    count_str = '\n'.join([f"{name}: {count}" for name, count in sorted_counts[:15]])
    embed.add_field(name="Top Pokemon", value=count_str, inline=False)

    if len(sorted_counts) > 15:
        embed.set_footer(text=f"... and {len(sorted_counts) - 15} more")

    await ctx.send(embed=embed)


@bot.command(name='help')
async def help_command(ctx):
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
        name="!pokedex [@user]",
        value="View your Pokedex (or another user's)",
        inline=False
    )

    embed.add_field(
        name="!count",
        value="See how many of each Pokemon you've caught",
        inline=False
    )

    await ctx.send(embed=embed)


# Run the bot
if __name__ == '__main__':
    if not TOKEN:
        print("ERROR: DISCORD_TOKEN not found in .env file!")
        print("Please create a .env file with your bot token.")
    else:
        bot.run(TOKEN)
