import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import Select, View, Button
import aiohttp
import asyncio
import random
import os
from dotenv import load_dotenv
from datetime import datetime

# Import database functions
import database as db
# Import Pokemon stats
import pokemon_stats as pkmn
# Import quest system
import quest_system
# Import gym leaders
import gym_leaders
# Import local Pokemon data loader (with fallback to PokeAPI)
import pokemon_data_loader as poke_data
# Import trainer data for random encounters
import trainer_data
from trainer_battle_view import TrainerBattleView

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
active_trainer_battles = {}  # {user_id: {'trainer': trainer_data, 'pokemon': wild_pokemon, 'channel_id': channel_id}}
last_guild_spawn = {}  # {guild_id: datetime} - Track last spawn per guild to guarantee max spawn interval
recent_catches = {}  # {channel_id: {'message': catch_message, 'timestamp': datetime}} - Track recent catches for laugh reactions


async def fetch_pokemon(session, pokemon_id=None):
    """Fetch a random or specific Pokemon from PokeAPI"""
    if pokemon_id is None:
        pokemon_id = random.randint(1, 251)  # Gen 1 & 2 Pokemon

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


async def fetch_pokemon_moves(session, pokemon_id: int, num_moves: int = 4, max_level: int = 100):
    """Fetch Pokemon's moves - uses local data if available, otherwise PokeAPI"""

    # Try local data first
    if poke_data.has_local_data():
        return poke_data.get_pokemon_moves(pokemon_id, num_moves, max_level)

    # Fallback to PokeAPI if local data not available
    url = f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}'

    try:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()

                # Get level-up moves only for simpler battles
                level_up_moves = []
                for move_data in data['moves']:
                    for version_detail in move_data['version_group_details']:
                        if version_detail['move_learn_method']['name'] == 'level-up':
                            level_up_moves.append(move_data['move'])
                            break

                # Pick random moves or return all if less than num_moves
                if len(level_up_moves) > num_moves:
                    selected_moves = random.sample(level_up_moves, num_moves)
                else:
                    selected_moves = level_up_moves[:num_moves]

                # Fetch details for each move
                moves = []
                for move in selected_moves:
                    try:
                        async with session.get(move['url']) as move_response:
                            if move_response.status == 200:
                                move_details = await move_response.json()
                                moves.append({
                                    'name': move_details['name'].replace('-', ' ').title(),
                                    'power': move_details['power'] or 40,  # Default power for status moves
                                    'accuracy': move_details['accuracy'] or 100,
                                    'type': move_details['type']['name'],
                                    'damage_class': move_details.get('damage_class', {}).get('name', 'physical')
                                })
                    except:
                        continue

                # Fill with default "Tackle" move if we don't have enough
                while len(moves) < num_moves:
                    moves.append({
                        'name': 'Tackle',
                        'power': 40,
                        'accuracy': 100,
                        'type': 'normal',
                        'damage_class': 'physical'
                    })

                return moves[:num_moves]
    except Exception as e:
        print(f"Error fetching moves for Pokemon {pokemon_id}: {e}")

    # Fallback: return basic moves
    return [
        {'name': 'Tackle', 'power': 40, 'accuracy': 100, 'type': 'normal', 'damage_class': 'physical'},
        {'name': 'Scratch', 'power': 40, 'accuracy': 100, 'type': 'normal', 'damage_class': 'physical'},
        {'name': 'Growl', 'power': 40, 'accuracy': 100, 'type': 'normal', 'damage_class': 'status'},
        {'name': 'Leer', 'power': 40, 'accuracy': 100, 'type': 'normal', 'damage_class': 'status'}
    ]


async def fetch_pokemon_species(session, pokemon_identifier):
    """Fetch Pokemon species data including Pokedex entries"""
    # pokemon_identifier can be ID or name
    url = f'https://pokeapi.co/api/v2/pokemon-species/{pokemon_identifier}'

    try:
        async with session.get(url) as response:
            if response.status == 200:
                species_data = await response.json()

                # Get English flavor text (Pokedex entries)
                flavor_texts = [
                    entry['flavor_text'].replace('\n', ' ').replace('\f', ' ')
                    for entry in species_data['flavor_text_entries']
                    if entry['language']['name'] == 'en'
                ]

                # Get Pokemon basic data
                pokemon_url = species_data['varieties'][0]['pokemon']['url']
                async with session.get(pokemon_url) as poke_response:
                    if poke_response.status == 200:
                        pokemon_data = await poke_response.json()

                        return {
                            'id': species_data['id'],
                            'name': species_data['name'].capitalize(),
                            'sprite': pokemon_data['sprites']['front_default'],
                            'types': [t['type']['name'].capitalize() for t in pokemon_data['types']],
                            'height': pokemon_data['height'] / 10,  # Convert to meters
                            'weight': pokemon_data['weight'] / 10,  # Convert to kg
                            'flavor_texts': flavor_texts,
                            'genus': next((g['genus'] for g in species_data['genera'] if g['language']['name'] == 'en'), 'Unknown'),
                            'habitat': species_data.get('habitat', {}).get('name', 'Unknown').capitalize() if species_data.get('habitat') else 'Unknown',
                            'generation': species_data['generation']['name'].replace('generation-', 'Gen ').upper()
                        }
    except Exception as e:
        print(f"Error fetching Pokemon species: {e}")

    return None


def get_type_icon_url(type_name: str) -> str:
    """Get the icon URL for a Pokemon type"""
    # Map type names to their IDs for the sprite URLs
    type_ids = {
        'normal': 1, 'fighting': 2, 'flying': 3, 'poison': 4,
        'ground': 5, 'rock': 6, 'bug': 7, 'ghost': 8,
        'steel': 9, 'fire': 10, 'water': 11, 'grass': 12,
        'electric': 13, 'psychic': 14, 'ice': 15, 'dragon': 16,
        'dark': 17, 'fairy': 18
    }

    type_id = type_ids.get(type_name.lower(), 1)  # Default to normal if not found
    return f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/types/generation-viii/sword-shield/{type_id}.png"


def create_spawn_embed(pokemon):
    """Create an embed for a spawned Pokemon"""
    types_str = '/'.join([t.title() for t in pokemon['types']])
    generation = poke_data.get_pokemon_generation(pokemon['id'])
    gen_text = f"Gen {generation}"

    embed = discord.Embed(
        title=f"A wild {pokemon['name']} appeared!",
        description=f"**Type:** {types_str}\n**Pokedex #:** {pokemon['id']} ({gen_text})\n\nType `ball` to catch it!",
        color=discord.Color.green()
    )

    if pokemon['sprite']:
        embed.set_image(url=pokemon['sprite'])

    # Add type icon as thumbnail
    if pokemon['types']:
        embed.set_thumbnail(url=get_type_icon_url(pokemon['types'][0]))

    embed.set_footer(text="First person to type 'ball' catches it!")

    return embed


def create_catch_embed(pokemon, user, time_taken, is_shiny=False, currency_reward=0):
    """Create an embed for a successful catch"""
    # Format time - show minutes if over 60 seconds, otherwise just seconds
    if time_taken >= 60:
        minutes = int(time_taken // 60)
        seconds = int(time_taken % 60)
        time_str = f"{minutes}m {seconds}s" if seconds > 0 else f"{minutes}m"
    else:
        time_str = f"{int(time_taken)}s"

    # Custom pokeball emoji (animated)
    pokeball = "<a:pokemonball:1426316759866146896>"
    shiny_text = "✨ **SHINY!** ✨ " if is_shiny else ""

    # Build description with currency reward
    description = f"{shiny_text}**Pokedex #:** {pokemon['id']}\n**Caught in:** {time_str}"
    if currency_reward > 0:
        description += f"\n💰 **Earned:** {currency_reward} Pokedollars"

    embed = discord.Embed(
        title=f"{pokeball} {user.display_name} caught {pokemon['name']}!",
        description=description,
        color=discord.Color.gold() if not is_shiny else discord.Color.purple()
    )

    # Use larger type icon as thumbnail instead of text
    if pokemon['types']:
        embed.set_thumbnail(url=get_type_icon_url(pokemon['types'][0]))

    # Use animated sprite as the main image (larger display)
    if pokemon['sprite']:
        embed.set_image(url=pokemon['sprite'])

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
    else:
        # No rewards at this level - show next pack level
        next_pack_level = ((new_level // 5) + 1) * 5
        if next_pack_level > 50:
            next_pack_level = 50

        embed.set_footer(text=f"Keep leveling to earn packs! Next pack at Level {next_pack_level}!")

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
            # Remove spawn immediately to prevent race condition (first come first serve)
            spawn_data = active_spawns.pop(channel_id)
            pokemon = spawn_data['pokemon']
            spawn_time = spawn_data['spawn_time']

            # Calculate time taken to catch
            catch_time = datetime.now()
            time_taken = (catch_time - spawn_time).total_seconds()

            user_id = message.author.id
            guild_id = message.guild.id if message.guild else 0

            # Reset spawn timer for this guild to prevent immediate respawn
            # This prevents the issue where a Pokemon sitting for 10+ minutes triggers immediate spawn after catch
            last_guild_spawn[guild_id] = catch_time

            # Roll for shiny (1/512 = 0.195% chance)
            is_shiny = random.random() < (1/512)

            # Update sprite to shiny version if shiny
            if is_shiny:
                pokemon['sprite'] = poke_data.get_pokemon_sprite(pokemon['id'], shiny=True)

            # 15% chance for a trainer to appear and claim the Pokemon
            if random.random() < 0.15:
                # Get a random trainer
                trainer = trainer_data.get_random_trainer()

                # Get user's average Pokemon level for scaling
                user_pokemon = await db.get_user_pokemon_for_trade(user_id, guild_id)
                if user_pokemon:
                    pokemon_ids = [p['pokemon_id'] for p in user_pokemon]
                    level_dict = await db.get_multiple_species_levels(user_id, guild_id, pokemon_ids)
                    avg_level = sum(level_dict.values()) / len(level_dict) if level_dict else 15
                else:
                    avg_level = 10  # New players get easier trainers

                # Trainer uses the wild Pokemon at a random level (1-10)
                trainer_pokemon_level = random.randint(1, 10)

                trainer_team = [{
                    'pokemon_id': pokemon['id'],
                    'level': trainer_pokemon_level
                }]

                # Send trainer appearance message
                trainer_quote = trainer.get('quote', "Let's battle!")
                trainer_embed = discord.Embed(
                    title=f"{trainer['sprite']} {trainer['name']} wants to battle {message.author.display_name}!",
                    description=f'**"{pokemon["name"]}"? That\'s MY Pokemon! Fight me for it!**\n\n💬 *"{trainer_quote}"*',
                    color=discord.Color.red()
                )

                # Show trainer's Pokemon (just the wild one they're claiming)
                trainer_embed.add_field(
                    name=f"{trainer['class']}'s Pokemon",
                    value=f"• **{pokemon['name']}** (Lv.{trainer_pokemon_level})",
                    inline=False
                )

                trainer_embed.add_field(
                    name="💰 Rewards if you win",
                    value=f"• **{pokemon['name']}** (the wild Pokemon)\n• **{trainer['reward_money']}** Pokedollars\n• Battle XP",
                    inline=False
                )

                trainer_embed.set_footer(text="Click 'Fight!' below to battle for the Pokemon!")

                # Store trainer battle data
                active_trainer_battles[user_id] = {
                    'trainer': trainer,
                    'trainer_team': trainer_team,
                    'pokemon': pokemon,
                    'channel_id': message.channel.id,
                    'guild_id': guild_id,
                    'time_taken': time_taken,
                    'is_shiny': is_shiny
                }

                # Create "Fight!" button
                class TrainerChallengeView(View):
                    def __init__(self, challenger_id):
                        super().__init__(timeout=60)
                        self.challenger_id = challenger_id

                    @discord.ui.button(label="⚔️ Fight!", style=discord.ButtonStyle.danger)
                    async def fight_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        if interaction.user.id != self.challenger_id:
                            await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
                            return

                        # Check if battle still exists
                        if self.challenger_id not in active_trainer_battles:
                            await interaction.response.send_message("❌ This trainer battle has expired!", ephemeral=True)
                            return

                        # Defer immediately to prevent timeout
                        await interaction.response.defer()

                        battle_data = active_trainer_battles[self.challenger_id]

                        # Get user's Pokemon for battle (deduplicated by species)
                        user_pokemon = await db.get_user_pokemon_for_trade(self.challenger_id, interaction.guild.id)

                        if not user_pokemon:
                            await interaction.followup.send("❌ You don't have any Pokemon to battle with!", ephemeral=True)
                            return

                        # Deduplicate by species to avoid querying duplicate levels
                        seen_species = {}
                        for pokemon in user_pokemon:
                            species_id = pokemon['pokemon_id']
                            if species_id not in seen_species:
                                seen_species[species_id] = pokemon

                        unique_pokemon = list(seen_species.values())

                        # Get levels only for unique species (faster)
                        pokemon_ids = [p['pokemon_id'] for p in unique_pokemon]
                        level_dict = await db.get_multiple_species_levels(self.challenger_id, interaction.guild.id, pokemon_ids)

                        # Add levels and sort
                        pokemon_with_levels = [{**p, 'level': level_dict.get(p['pokemon_id'], 1)} for p in unique_pokemon]
                        pokemon_with_levels.sort(key=lambda p: p['level'], reverse=True)

                        # Create trainer battle view
                        trainer_battle_view = TrainerBattleView(
                            interaction.user,
                            interaction.guild.id,
                            battle_data['trainer'],
                            battle_data['trainer_team'],
                            battle_data['pokemon'],
                            pokemon_with_levels,
                            battle_data['time_taken'],
                            battle_data.get('is_shiny', False)
                        )

                        # Show Pokemon selection
                        embed = trainer_battle_view.create_selection_embed()
                        await interaction.followup.send(embed=embed, view=trainer_battle_view)

                        # Disable both buttons
                        self.fight_button.disabled = True
                        self.flee_button.disabled = True
                        await interaction.message.edit(view=self)

                    @discord.ui.button(label="🏃 Flee", style=discord.ButtonStyle.secondary)
                    async def flee_button(self, interaction: discord.Interaction, button: discord.ui.Button):
                        if interaction.user.id != self.challenger_id:
                            await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
                            return

                        # Check if battle still exists
                        if self.challenger_id not in active_trainer_battles:
                            await interaction.response.send_message("❌ This trainer battle has expired!", ephemeral=True)
                            return

                        battle_data = active_trainer_battles[self.challenger_id]
                        pokemon = battle_data['pokemon']

                        # Remove from active battles
                        del active_trainer_battles[self.challenger_id]

                        # Create flee embed
                        flee_embed = discord.Embed(
                            title="🏃 Fled from Battle!",
                            description=f"You ran away from the trainer battle!\n\n**{pokemon['name']}** escaped into the wild...",
                            color=discord.Color.blue()
                        )

                        # Disable both buttons
                        self.fight_button.disabled = True
                        self.flee_button.disabled = True

                        # Update the message with the flee embed
                        await interaction.response.edit_message(embed=flee_embed, view=self)

                view = TrainerChallengeView(user_id)
                await message.channel.send(embed=trainer_embed, view=view)

                # Don't catch the Pokemon automatically - trainer battle will handle it
                return

            # Save catch to database
            await db.add_catch(
                user_id=user_id,
                guild_id=guild_id,
                pokemon_name=pokemon['name'],
                pokemon_id=pokemon['id'],
                pokemon_types=pokemon['types'],
                is_shiny=is_shiny
            )

            # Award Pokedollars for catching (5-15 based on rarity)
            # Gen 1: Articuno, Zapdos, Moltres, Mewtwo, Mew
            # Gen 2: Raikou, Entei, Suicune, Lugia, Ho-Oh, Celebi
            legendary_ids = [144, 145, 146, 150, 151, 243, 244, 245, 249, 250, 251]
            if pokemon['id'] in legendary_ids:
                currency_reward = 50  # Legendary = 50 Pokedollars
            else:
                currency_reward = random.randint(5, 15)  # Regular = 5-15 Pokedollars

            new_balance = await db.add_currency(user_id, guild_id, currency_reward)

            # Update quest progress for catching Pokemon
            quest_result = await db.update_quest_progress(user_id, guild_id, 'catch_pokemon')

            # Update quest progress for earning Pokedollars
            earn_quest_result = await db.update_quest_progress(user_id, guild_id, 'earn_pokedollars', increment=currency_reward)
            if earn_quest_result and earn_quest_result.get('completed_quests'):
                if not quest_result:
                    quest_result = earn_quest_result
                else:
                    quest_result['total_currency'] += earn_quest_result['total_currency']
                    quest_result['completed_quests'].extend(earn_quest_result['completed_quests'])

            # Check if caught Pokemon is legendary
            # Gen 1: Articuno, Zapdos, Moltres, Mewtwo, Mew
            # Gen 2: Raikou, Entei, Suicune, Lugia, Ho-Oh, Celebi
            legendary_ids = [144, 145, 146, 150, 151, 243, 244, 245, 249, 250, 251]
            if pokemon['id'] in legendary_ids:
                legendary_quest_result = await db.update_quest_progress(user_id, guild_id, 'catch_legendary')
                if legendary_quest_result and legendary_quest_result.get('completed_quests'):
                    # Merge quest results
                    if not quest_result:
                        quest_result = legendary_quest_result
                    else:
                        quest_result['total_currency'] += legendary_quest_result['total_currency']
                        quest_result['completed_quests'].extend(legendary_quest_result['completed_quests'])

            # Check for starter Pokemon (IDs 1-9: Bulbasaur line, Charmander line, Squirtle line)
            starter_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9]
            if pokemon['id'] in starter_ids:
                starter_quest_result = await db.update_quest_progress(user_id, guild_id, 'catch_starter')
                if starter_quest_result and starter_quest_result.get('completed_quests'):
                    if not quest_result:
                        quest_result = starter_quest_result
                    else:
                        quest_result['total_currency'] += starter_quest_result['total_currency']
                        quest_result['completed_quests'].extend(starter_quest_result['completed_quests'])

            # Check for type-specific quests
            pokemon_types = pokemon['types']  # Types from the spawned Pokemon
            for poke_type in pokemon_types:
                type_lower = poke_type.lower()
                quest_type = f'catch_{type_lower}'
                type_quest_result = await db.update_quest_progress(user_id, guild_id, quest_type)
                if type_quest_result and type_quest_result.get('completed_quests'):
                    if not quest_result:
                        quest_result = type_quest_result
                    else:
                        quest_result['total_currency'] += type_quest_result['total_currency']
                        quest_result['completed_quests'].extend(type_quest_result['completed_quests'])

            # Award quest currency rewards if quests were completed
            quest_currency_earned = 0
            if quest_result and quest_result.get('total_currency', 0) > 0:
                quest_currency_earned = quest_result['total_currency']
                await db.add_currency(user_id, guild_id, quest_currency_earned)

            # Send catch confirmation with time and currency reward
            embed = create_catch_embed(pokemon, message.author, time_taken, is_shiny=is_shiny, currency_reward=currency_reward)
            catch_message = await message.channel.send(embed=embed)

            # Store recent catch for laugh reactions (expire after 10 seconds)
            recent_catches[channel_id] = {
                'message': catch_message,
                'timestamp': datetime.now(),
                'catcher_id': user_id
            }

            # If quests were completed, notify user
            if quest_result and quest_result.get('completed_quests'):
                quest_currency = quest_result.get('total_currency', 0)
                quest_count = len(quest_result['completed_quests'])
                quest_embed = discord.Embed(
                    title="✅ Daily Quest Complete!",
                    description=f"You completed {quest_count} quest(s) and earned **₽{quest_currency}**!",
                    color=discord.Color.green()
                )
                await message.channel.send(embed=quest_embed)

                # Check if ALL quests are now complete
                all_quests = await db.get_daily_quests(user_id, guild_id)
                if all_quests:
                    all_complete = all(
                        all_quests.get(f'quest_{i}_completed', False)
                        for i in range(1, 4)
                    )
                    if all_complete:
                        all_complete_embed = discord.Embed(
                            title="🎉 All Daily Quests Complete!",
                            description="Congratulations! You've completed all your daily quests!\nNew quests will be available tomorrow.",
                            color=discord.Color.gold()
                        )
                        await message.channel.send(embed=all_complete_embed)
        else:
            # No active spawn - check if someone just caught it
            if channel_id in recent_catches:
                recent_catch = recent_catches[channel_id]
                time_since_catch = (datetime.now() - recent_catch['timestamp']).total_seconds()

                # If caught within last 10 seconds and it's not the person who caught it
                if time_since_catch < 10 and message.author.id != recent_catch['catcher_id']:
                    # Add laugh reaction to the user's failed "ball" attempt
                    try:
                        await message.add_reaction('😂')
                    except:
                        pass  # Ignore if reaction fails


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

        # Check if guild has gone too long without a spawn (10 minutes max)
        force_spawn = False
        if guild_id in last_guild_spawn:
            time_since_last = (datetime.now() - last_guild_spawn[guild_id]).total_seconds()
            if time_since_last > 600:  # 10 minutes = 600 seconds
                force_spawn = True

        # Random chance to spawn (creates randomness), or force if it's been too long
        if not force_spawn and random.random() > 0.25:  # 25% chance per minute = avg ~4 min
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
                spawn_time = datetime.now()
                active_spawns[str(channel.id)] = {
                    'pokemon': pokemon,
                    'spawn_time': spawn_time
                }

                # Track last spawn time for this guild
                last_guild_spawn[guild_id] = spawn_time

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
    # Defer IMMEDIATELY before any checks to prevent timeout
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

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


@bot.tree.command(name='clear', description='Clear all spawn channels (Admin only)')
@app_commands.default_permissions(administrator=True)
async def clear_channels(interaction: discord.Interaction):
    """Clear all spawn channels for this server"""
    # Defer IMMEDIATELY before any checks
    await interaction.response.defer(ephemeral=True)

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    try:
        # Get current spawn channels
        config = await db.get_guild_config(interaction.guild.id)

        if not config or not config.get('spawn_channels'):
            await interaction.followup.send("No spawn channels configured for this server!", ephemeral=True)
            return

        # Clear all spawn channels by updating to empty array
        async with db.pool.acquire() as conn:
            await conn.execute('''
                UPDATE guilds
                SET spawn_channels = ARRAY[]::BIGINT[]
                WHERE guild_id = $1
            ''', interaction.guild.id)

        await interaction.followup.send("✅ All spawn channels have been cleared! Use `/setup` to configure new ones.", ephemeral=True)
        print(f"Cleared spawn channels for {interaction.guild.name}")

    except Exception as e:
        await interaction.followup.send(f"❌ Error clearing channels: {str(e)}", ephemeral=True)
        print(f"Error in clear command: {e}")


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


# Gym Leader Selection View
class GymSelectView(View):
    def __init__(self, user: discord.Member, guild_id: int, user_pokemon: list, user_badges: list, region: str = 'kanto'):
        super().__init__(timeout=300)
        self.user = user
        self.guild_id = guild_id
        self.user_pokemon = user_pokemon
        self.user_badges = user_badges
        self.region = region

        # Create dropdown for gym selection
        self.gym_select = Select(
            placeholder="Choose a Gym Leader to challenge...",
            min_values=1,
            max_values=1
        )

        # Add gym leaders as options based on region
        gym_list = gym_leaders.get_all_gym_leaders() if region == 'kanto' else gym_leaders.get_all_gym_leaders_johto()

        for gym_key, gym_data in gym_list:
            has_badge = gym_key in user_badges
            label = f"{'✅' if has_badge else '⭕'} {gym_data['name']} ({gym_data['type']})"
            description = f"{gym_data['location']} - {'⭐' * gym_data['difficulty']}"
            self.gym_select.add_option(
                label=label,
                value=gym_key,
                description=description,
                emoji=gym_data['badge_emoji']
            )

        self.gym_select.callback = self.gym_selected
        self.add_item(self.gym_select)

    def create_embed(self):
        """Create the gym selection embed"""
        region_name = "Kanto" if self.region == 'kanto' else "Johto"
        region_emoji = "🗾" if self.region == 'kanto' else "🌸"

        # Count badges for this region
        gym_list = gym_leaders.get_all_gym_leaders() if self.region == 'kanto' else gym_leaders.get_all_gym_leaders_johto()
        region_badges = sum(1 for gym_key, _ in gym_list if gym_key in self.user_badges)

        embed = discord.Embed(
            title=f"{region_emoji} {region_name} Gym Leaders",
            description=f"**{self.user.display_name}** | {region_name} Badges: **{region_badges}/8**\n\nSelect a gym leader to challenge!",
            color=discord.Color.gold() if region_badges == 8 else discord.Color.blue()
        )

        return embed

    async def gym_selected(self, interaction: discord.Interaction):
        """Handle gym leader selection"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your gym challenge!", ephemeral=True)
            return

        gym_key = self.gym_select.values[0]
        gym_data = gym_leaders.get_gym_leader(gym_key)

        # Defer response FIRST before any database operations
        await interaction.response.defer()

        # Check if already defeated (after defer)
        if gym_key in self.user_badges:
            # Just add a note, don't prevent the challenge
            pass

        # Create gym battle view (now handles Pokemon selection internally with pagination)
        gym_battle_view = GymBattleView(self.user, self.guild_id, gym_key, gym_data, self.user_pokemon, gym_key in self.user_badges)

        # Delete the gym selection message
        await interaction.delete_original_response()

        embed = gym_battle_view.create_selection_embed()
        await interaction.followup.send(embed=embed, view=gym_battle_view)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id


# Gym Battle View - NPC Battle System
class GymBattleView(View):
    def __init__(self, user: discord.Member, guild_id: int, gym_key: str, gym_data: dict, user_pokemon: list, already_defeated: bool):
        super().__init__(timeout=600)
        self.user = user
        self.guild_id = guild_id
        self.gym_key = gym_key
        self.gym_data = gym_data
        self.user_pokemon = user_pokemon
        self.already_defeated = already_defeated

        # Battle state
        self.user_team = []  # User's team of Pokemon
        self.user_pokemon_index = 0  # Current user Pokemon index
        self.gym_pokemon_index = 0  # Current gym leader Pokemon index
        self.battle_started = False
        self.battle_message = None  # Store reference to battle message for updates

        # Current active Pokemon (set when battle starts)
        self.user_choice = None
        self.gym_current_pokemon = None

        # HP tracking
        self.user_current_hp = 0
        self.user_max_hp = 0
        self.gym_current_hp = 0
        self.gym_max_hp = 0

        # Turn tracking
        self.turn_count = 0
        self.battle_log = []

        # Stat stages (user and gym Pokemon)
        self.user_stat_stages = {
            'attack': 0, 'defense': 0, 'special-attack': 0,
            'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
        }
        self.gym_stat_stages = {
            'attack': 0, 'defense': 0, 'special-attack': 0,
            'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
        }

        # Status conditions
        self.user_status = None  # 'burn', 'paralysis', 'sleep', 'poison', 'freeze', etc.
        self.user_status_turns = 0  # For sleep duration or poison counter
        self.gym_status = None
        self.gym_status_turns = 0

        # Team size based on gym leader's team
        self.team_size = len(self.gym_data['pokemon'])

        # Pagination for Pokemon selection
        self.current_page = 0
        self.pokemon_per_page = 25
        self.selected_pokemon_ids = []  # Track selected Pokemon IDs across pages

        # Deduplicate Pokemon by species
        seen_species = {}
        for pokemon in user_pokemon:
            species_id = pokemon['pokemon_id']
            if species_id not in seen_species:
                seen_species[species_id] = pokemon

        self.unique_pokemon = list(seen_species.values())
        self.total_pages = (len(self.unique_pokemon) + self.pokemon_per_page - 1) // self.pokemon_per_page

        # Create initial selection UI
        self.update_pokemon_selection()

    def update_pokemon_selection(self):
        """Update Pokemon dropdown for current page"""
        self.clear_items()

        # Calculate pagination
        start_idx = self.current_page * self.pokemon_per_page
        end_idx = min(start_idx + self.pokemon_per_page, len(self.unique_pokemon))
        page_pokemon = self.unique_pokemon[start_idx:end_idx]

        # Show selected Pokemon if any
        if self.selected_pokemon_ids:
            selected_names = []
            for pid in self.selected_pokemon_ids:
                p = next((poke for poke in self.unique_pokemon if poke['id'] == pid), None)
                if p:
                    selected_names.append(p['pokemon_name'])

            selection_button = Button(
                label=f"Selected: {', '.join(selected_names[:3])}{'...' if len(selected_names) > 3 else ''} ({len(self.selected_pokemon_ids)}/{self.team_size})",
                style=discord.ButtonStyle.primary,
                disabled=True,
                row=0
            )
            self.add_item(selection_button)

        # Create dropdown (allows selecting/deselecting on current page)
        # Changed to allow 0 selections so users can navigate pages without selecting
        row_offset = 1 if self.selected_pokemon_ids else 0  # Adjust if selection button exists

        self.pokemon_select = Select(
            placeholder=f"Add/Remove Pokemon from team...",
            min_values=0,
            max_values=min(len(page_pokemon), 25),
            row=row_offset
        )

        for pokemon in page_pokemon:
            level = pokemon.get('level', 1)
            # Mark if already selected
            is_selected = pokemon['id'] in self.selected_pokemon_ids
            is_shiny = pokemon.get('is_shiny', False)
            shiny_indicator = "✨ " if is_shiny else ""
            label = f"{'✓ ' if is_selected else ''}Lv.{level} | #{pokemon['pokemon_id']:03d} {shiny_indicator}{pokemon['pokemon_name']}"
            self.pokemon_select.add_option(
                label=label[:100],  # Discord limit
                value=str(pokemon['id']),
                emoji="✨" if is_shiny else ("✅" if is_selected else "⚔️"),
                default=is_selected
            )

        self.pokemon_select.callback = self.pokemon_select_toggle
        self.add_item(self.pokemon_select)

        # Add pagination buttons if needed
        if self.total_pages > 1:
            prev_button = Button(
                label="◀ Previous",
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page == 0 or self.battle_started),
                custom_id="prev_page",
                row=row_offset + 1
            )
            prev_button.callback = self.previous_page
            self.add_item(prev_button)

            next_button = Button(
                label="Next ▶",
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page >= self.total_pages - 1 or self.battle_started),
                custom_id="next_page",
                row=row_offset + 1
            )
            next_button.callback = self.next_page
            self.add_item(next_button)

        # Add "Start Battle" button
        start_button = Button(
            label=f"Start Battle! ({len(self.selected_pokemon_ids)}/{self.team_size} selected)",
            style=discord.ButtonStyle.green if len(self.selected_pokemon_ids) == self.team_size else discord.ButtonStyle.gray,
            disabled=(len(self.selected_pokemon_ids) != self.team_size or self.battle_started),
            custom_id="start_battle",
            row=row_offset + 2
        )
        start_button.callback = self.start_battle_button
        self.add_item(start_button)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page of Pokemon"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
            return

        # Prevent page changes if battle has started
        if self.battle_started:
            await interaction.response.send_message("❌ Battle has already started!", ephemeral=True)
            return

        self.current_page = max(0, self.current_page - 1)
        self.update_pokemon_selection()

        embed = self.create_selection_embed()
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • {len(self.unique_pokemon)} total Pokemon • Select {self.team_size} Pokemon")
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        """Go to next page of Pokemon"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
            return

        # Prevent page changes if battle has started
        if self.battle_started:
            await interaction.response.send_message("❌ Battle has already started!", ephemeral=True)
            return

        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.update_pokemon_selection()

        embed = self.create_selection_embed()
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • {len(self.unique_pokemon)} total Pokemon • {len(self.selected_pokemon_ids)}/{self.team_size} selected")
        await interaction.response.edit_message(embed=embed, view=self)

    async def pokemon_select_toggle(self, interaction: discord.Interaction):
        """Toggle Pokemon selection on current page"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
            return

        # Get selected values from dropdown
        selected_on_page = [int(val) for val in self.pokemon_select.values]

        # Get Pokemon on current page
        start_idx = self.current_page * self.pokemon_per_page
        end_idx = min(start_idx + self.pokemon_per_page, len(self.unique_pokemon))
        page_pokemon_ids = [p['id'] for p in self.unique_pokemon[start_idx:end_idx]]

        # Remove any from current page that aren't selected
        self.selected_pokemon_ids = [pid for pid in self.selected_pokemon_ids if pid not in page_pokemon_ids]

        # Add newly selected from current page (up to team_size limit)
        for pid in selected_on_page:
            if pid not in self.selected_pokemon_ids and len(self.selected_pokemon_ids) < self.team_size:
                self.selected_pokemon_ids.append(pid)

        # Update the view
        self.update_pokemon_selection()
        embed = self.create_selection_embed()
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • {len(self.unique_pokemon)} total Pokemon • {len(self.selected_pokemon_ids)}/{self.team_size} selected")
        await interaction.response.edit_message(embed=embed, view=self)

    async def start_battle_button(self, interaction: discord.Interaction):
        """Start the battle with selected Pokemon"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
            return

        if len(self.selected_pokemon_ids) != self.team_size:
            await interaction.response.send_message(f"❌ You must select exactly {self.team_size} Pokemon!", ephemeral=True)
            return

        # Use the selected IDs instead of dropdown values
        await self.pokemon_selected_from_list(interaction, self.selected_pokemon_ids)

    async def pokemon_selected_from_list(self, interaction: discord.Interaction, selected_ids: list):
        """Handle Pokemon team selection and start battle"""
        await interaction.response.defer()

        # Build user's team (use local data for speed)
        for selected_id in selected_ids:
            selected_pokemon = next((p for p in self.user_pokemon if p['id'] == selected_id), None)

            if not selected_pokemon:
                continue

            # Use local Pokemon data loader (much faster than API calls)
            pokemon_id = selected_pokemon['pokemon_id']

            # Get Pokemon types
            types = poke_data.get_pokemon_types(pokemon_id)

            # Get species level
            species_level = await db.get_species_level(self.user.id, self.guild_id, pokemon_id, selected_pokemon['pokemon_name'])

            # Get 4 moves for this level
            moves = poke_data.get_pokemon_moves(pokemon_id, num_moves=4, max_level=species_level)

            # Get base stats and calculate battle stats
            base_stats = poke_data.get_pokemon_stats(pokemon_id)
            user_stats = pkmn.calculate_battle_stats(base_stats, species_level)

            # Get sprite
            sprite = poke_data.get_pokemon_sprite(pokemon_id)

            # Add to team
            self.user_team.append({
                'id': selected_pokemon['id'],
                'pokemon_name': selected_pokemon['pokemon_name'],
                'pokemon_id': pokemon_id,
                'types': types,
                'moves': moves,
                'level': species_level,
                'stats': user_stats,
                'sprite': sprite,
                'max_hp': user_stats['hp'],
                'current_hp': user_stats['hp']
            })

        if not self.user_team:
            await interaction.followup.send("❌ Error loading Pokemon team!", ephemeral=True)
            return

        # Set first Pokemon as active
        self.user_choice = self.user_team[0]
        self.user_max_hp = self.user_choice['max_hp']
        self.user_current_hp = self.user_choice['current_hp']

        # Start battle
        self.battle_started = True
        self.gym_pokemon_index = 0
        self.user_pokemon_index = 0

        # Update quest progress for challenging a gym
        await db.update_quest_progress(self.user.id, self.guild_id, 'challenge_gyms')

        # Load first gym Pokemon
        await self.load_gym_pokemon()

        # Create battle UI
        self.clear_items()
        await self.create_battle_buttons()

        embed = self.create_battle_embed()

        # Delete the selection message and send new battle message
        await interaction.delete_original_response()
        self.battle_message = await interaction.followup.send(embed=embed, view=self)

    def create_selection_embed(self):
        """Create embed for Pokemon selection"""
        gym_team_text = "\n".join([
            f"**{p['name']}** (Lv.{p['level']}) - {'/'.join(p['types']).title()}"
            for p in self.gym_data['pokemon']
        ])

        embed = discord.Embed(
            title=f"🏟️ Challenge {self.gym_data['name']}!",
            description=f"**{self.gym_data['title']}**\n📍 {self.gym_data['location']}",
            color=discord.Color.orange()
        )

        embed.add_field(
            name=f"{self.gym_data['type']} Type Specialist",
            value=f"**Gym Team:**\n{gym_team_text}",
            inline=False
        )

        rewards_text = f"₽{self.gym_data['rewards']['pokedollars']} Pokedollars\n"
        rewards_text += f"1x {self.gym_data['rewards']['pack']}\n"
        rewards_text += f"**{self.gym_data['badge']}**"

        if self.already_defeated:
            embed.add_field(
                name="⚠️ Already Defeated",
                value="You've already beaten this gym! You can battle for fun and still earn XP, but won't earn badge/money/pack rewards again.",
                inline=False
            )
        else:
            embed.add_field(
                name="🎁 Rewards (First Victory)",
                value=rewards_text,
                inline=False
            )

        embed.set_footer(text=f"Select {self.team_size} Pokemon for your team to begin the challenge!")

        return embed


    async def load_gym_pokemon(self):
        """Load current gym leader Pokemon"""
        gym_poke = self.gym_data['pokemon'][self.gym_pokemon_index]

        # Fetch Pokemon data from PokeAPI
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://pokeapi.co/api/v2/pokemon/{gym_poke["id"]}') as resp:
                if resp.status != 200:
                    return
                poke_data = await resp.json()

            # Get 4 random moves
            moves = await fetch_pokemon_moves(session, gym_poke['id'], 4)

        # Calculate stats for gym Pokemon
        base_stats = {stat['stat']['name']: stat['base_stat'] for stat in poke_data['stats']}
        gym_stats = pkmn.calculate_battle_stats(base_stats, gym_poke['level'])

        self.gym_current_pokemon = {
            'pokemon_name': gym_poke['name'],
            'pokemon_id': gym_poke['id'],
            'types': gym_poke['types'],
            'moves': moves,
            'level': gym_poke['level'],
            'stats': gym_stats,
            'sprite': poke_data['sprites']['front_default']
        }

        # Initialize gym Pokemon HP
        self.gym_max_hp = gym_stats['hp']
        self.gym_current_hp = gym_stats['hp']

        # Reset gym Pokemon stat stages and status (new Pokemon)
        self.gym_stat_stages = {
            'attack': 0, 'defense': 0, 'special-attack': 0,
            'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
        }
        self.gym_status = None
        self.gym_status_turns = 0

    async def create_battle_buttons(self):
        """Create move buttons for battle"""
        for i, move in enumerate(self.user_choice['moves']):
            # Determine button color based on move damage class
            if move['damage_class'] == 'status' or move.get('power', 0) == 0:
                button_style = discord.ButtonStyle.secondary  # Gray for status moves
            elif move['damage_class'] == 'physical':
                button_style = discord.ButtonStyle.danger  # Red for physical attacks
            else:  # special
                button_style = discord.ButtonStyle.primary  # Blue for special attacks

            button = Button(
                label=f"{move['name']} ({move['type']})",
                style=button_style,
                custom_id=f"move_{i}",
                row=i // 2  # 2 buttons per row
            )
            button.callback = self.create_move_callback(i)
            self.add_item(button)

        # Add Switch Pokemon button if user has more than one Pokemon and has others alive
        alive_pokemon = [p for i, p in enumerate(self.user_team) if p['current_hp'] > 0 and i != self.user_pokemon_index]
        if len(alive_pokemon) > 0:
            switch_button = Button(
                label="🔄 Switch Pokemon",
                style=discord.ButtonStyle.secondary,
                custom_id="switch_pokemon",
                row=2
            )
            switch_button.callback = self.switch_pokemon_callback()
            self.add_item(switch_button)

    def switch_pokemon_callback(self):
        """Create callback for switch button"""
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
                return

            # Show Pokemon selection dropdown
            alive_pokemon = [p for i, p in enumerate(self.user_team) if p['current_hp'] > 0 and i != self.user_pokemon_index]

            if not alive_pokemon:
                await interaction.response.send_message("❌ No other Pokemon available to switch!", ephemeral=True)
                return

            # Create dropdown with alive Pokemon
            switch_select = Select(
                placeholder="Choose a Pokemon to switch to...",
                min_values=1,
                max_values=1
            )

            for i, pokemon in enumerate(self.user_team):
                if pokemon['current_hp'] > 0 and i != self.user_pokemon_index:
                    hp_percent = int((pokemon['current_hp'] / pokemon['max_hp']) * 100)
                    switch_select.add_option(
                        label=f"{pokemon['pokemon_name']} (Lv.{pokemon['level']})",
                        description=f"HP: {pokemon['current_hp']}/{pokemon['max_hp']} ({hp_percent}%)",
                        value=str(i)
                    )

            async def switch_selected(select_interaction: discord.Interaction):
                if select_interaction.user.id != self.user.id:
                    await select_interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
                    return

                await select_interaction.response.defer()

                new_index = int(switch_select.values[0])

                # Switch to new Pokemon
                self.user_pokemon_index = new_index
                self.user_choice = self.user_team[new_index]
                self.user_max_hp = self.user_choice['max_hp']
                self.user_current_hp = self.user_choice['current_hp']

                # Reset stat stages and status for switched Pokemon
                self.user_stat_stages = {
                    'attack': 0, 'defense': 0, 'special-attack': 0,
                    'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
                }
                self.user_status = None
                self.user_status_turns = 0

                # Execute gym leader's turn (switching costs a turn)
                self.turn_count += 1
                self.battle_log.append(f"**Turn {self.turn_count}:**")
                self.battle_log.append(f"You switched to **{self.user_choice['pokemon_name']}**!")

                # Gym leader attacks
                gym_move = random.choice(self.gym_current_pokemon['moves'])

                if gym_move['damage_class'] == 'status':
                    self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** used **{gym_move['name']}**!")
                    status_msg = self.execute_status_move(gym_move, is_user_move=False)
                    if status_msg:
                        self.battle_log.append(status_msg)
                else:
                    gym_damage, gym_crit, gym_hit = await self.calculate_damage(
                        gym_move,
                        self.gym_current_pokemon,
                        self.user_choice,
                        self.gym_stat_stages,
                        self.gym_status,
                        self.user_stat_stages
                    )

                    if gym_hit:
                        self.user_current_hp -= gym_damage
                        self.user_team[self.user_pokemon_index]['current_hp'] = self.user_current_hp
                        crit_text = " **Critical hit!**" if gym_crit else ""
                        self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** used **{gym_move['name']}**! Dealt {gym_damage} damage!{crit_text}")

                        # Check for self-destruct moves
                        move_name_lower = gym_move['name'].lower()
                        if 'self-destruct' in move_name_lower or 'selfdestruct' in move_name_lower or move_name_lower == 'explosion':
                            self.gym_current_hp = 0
                            self.battle_log.append(f"💥 **{self.gym_current_pokemon['pokemon_name']}** fainted from the recoil!")
                    else:
                        self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** used **{gym_move['name']}**... but it missed!")

                # Check if switched Pokemon fainted
                if self.user_current_hp <= 0:
                    self.user_current_hp = 0
                    self.user_team[self.user_pokemon_index]['current_hp'] = 0
                    self.battle_log.append(f"**{self.user_choice['pokemon_name']}** fainted!")

                    # Find next alive Pokemon
                    found_alive = False
                    for i in range(len(self.user_team)):
                        if self.user_team[i]['current_hp'] > 0:
                            self.user_pokemon_index = i
                            self.user_choice = self.user_team[i]
                            self.user_max_hp = self.user_choice['max_hp']
                            self.user_current_hp = self.user_choice['current_hp']

                            # Reset stat stages and status for new Pokemon
                            self.user_stat_stages = {
                                'attack': 0, 'defense': 0, 'special-attack': 0,
                                'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
                            }
                            self.user_status = None
                            self.user_status_turns = 0

                            self.battle_log.append(f"Go, **{self.user_choice['pokemon_name']}**!")
                            found_alive = True
                            break

                    if not found_alive:
                        # User is out of Pokemon
                        await self.handle_defeat(select_interaction)
                        return

                # Update UI with new Pokemon's moves
                self.clear_items()
                await self.create_battle_buttons()
                embed = self.create_battle_embed()

                # Update the main battle message with new moves
                if self.battle_message:
                    await self.battle_message.edit(embed=embed, view=self)

                # Close the switch selection
                await select_interaction.edit_original_response(content="✅ Switched Pokemon!", embed=None, view=None)

            switch_select.callback = switch_selected

            switch_view = View(timeout=60)
            switch_view.add_item(switch_select)

            await interaction.response.send_message("Choose a Pokemon to switch to:", view=switch_view, ephemeral=True)

        return callback

    def create_move_callback(self, move_index: int):
        """Create callback for move button"""
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
                return

            await interaction.response.defer()
            await self.execute_turn(move_index, interaction)

        return callback

    async def execute_turn(self, user_move_index: int, interaction: discord.Interaction):
        """Execute a battle turn"""
        self.turn_count += 1

        # User's move
        user_move = self.user_choice['moves'][user_move_index]

        # Gym Pokemon randomly selects a move
        gym_move = random.choice(self.gym_current_pokemon['moves'])

        # Determine turn order based on speed (paralysis affects speed)
        user_speed = self.user_choice['stats']['speed']
        gym_speed = self.gym_current_pokemon['stats']['speed']

        # Apply paralysis speed reduction
        if self.user_status == 'paralysis':
            user_speed = int(user_speed * 0.25)
        if self.gym_status == 'paralysis':
            gym_speed = int(gym_speed * 0.25)

        if user_speed >= gym_speed:
            # User goes first
            # Check if user is immobilized
            is_immobilized, immobilize_msg = self.check_immobilized(
                self.user_choice['pokemon_name'],
                self.user_status,
                self.user_status_turns
            )

            if is_immobilized:
                self.battle_log.append(immobilize_msg)
            else:
                # Execute user's move
                if user_move['damage_class'] == 'status':
                    # Status move
                    self.battle_log.append(f"**{self.user_choice['pokemon_name']}** used **{user_move['name']}**!")
                    status_msg = self.execute_status_move(user_move, is_user_move=True)
                    if status_msg:
                        self.battle_log.append(status_msg)
                else:
                    # Damaging move
                    user_damage, user_crit, user_hit = await self.calculate_damage(
                        user_move,
                        self.user_choice,
                        self.gym_current_pokemon,
                        self.user_stat_stages,
                        self.user_status,
                        self.gym_stat_stages
                    )

                    if user_hit:
                        self.gym_current_hp -= user_damage
                        crit_text = " **Critical hit!**" if user_crit else ""
                        self.battle_log.append(f"**{self.user_choice['pokemon_name']}** used **{user_move['name']}**! Dealt {user_damage} damage!{crit_text}")

                        # Check for self-destruct moves
                        move_name_lower = user_move['name'].lower()
                        if 'self-destruct' in move_name_lower or 'selfdestruct' in move_name_lower or move_name_lower == 'explosion':
                            self.user_current_hp = 0
                            self.user_team[self.user_pokemon_index]['current_hp'] = 0
                            self.battle_log.append(f"💥 **{self.user_choice['pokemon_name']}** fainted from the recoil!")
                    else:
                        self.battle_log.append(f"**{self.user_choice['pokemon_name']}** used **{user_move['name']}**... but it missed!")

            # Check if gym Pokemon fainted
            if self.gym_current_hp <= 0:
                self.gym_current_hp = 0
                self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** fainted!")

                # Check if there are more gym Pokemon
                if self.gym_pokemon_index < len(self.gym_data['pokemon']) - 1:
                    self.gym_pokemon_index += 1
                    await self.load_gym_pokemon()
                    self.battle_log.append(f"**{self.gym_data['name']}** sent out **{self.gym_current_pokemon['pokemon_name']}**!")
                else:
                    # User won!
                    await self.handle_victory(interaction)
                    return
            else:
                # Gym Pokemon's turn
                # Check if gym Pokemon is immobilized
                is_immobilized, immobilize_msg = self.check_immobilized(
                    self.gym_current_pokemon['pokemon_name'],
                    self.gym_status,
                    self.gym_status_turns
                )

                if is_immobilized:
                    self.battle_log.append(immobilize_msg)
                else:
                    # Execute gym Pokemon's move
                    if gym_move['damage_class'] == 'status':
                        # Status move
                        self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** used **{gym_move['name']}**!")
                        status_msg = self.execute_status_move(gym_move, is_user_move=False)
                        if status_msg:
                            self.battle_log.append(status_msg)
                    else:
                        # Damaging move
                        gym_damage, gym_crit, gym_hit = await self.calculate_damage(
                            gym_move,
                            self.gym_current_pokemon,
                            self.user_choice,
                            self.gym_stat_stages,
                            self.gym_status,
                            self.user_stat_stages
                        )

                        if gym_hit:
                            self.user_current_hp -= gym_damage
                            self.user_team[self.user_pokemon_index]['current_hp'] = self.user_current_hp
                            crit_text = " **Critical hit!**" if gym_crit else ""
                            self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** used **{gym_move['name']}**! Dealt {gym_damage} damage!{crit_text}")
                        else:
                            self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** used **{gym_move['name']}**... but it missed!")

                # Check if user Pokemon fainted
                if self.user_current_hp <= 0:
                    self.user_current_hp = 0
                    self.user_team[self.user_pokemon_index]['current_hp'] = 0
                    self.battle_log.append(f"**{self.user_choice['pokemon_name']}** fainted!")

                    # Find next alive Pokemon
                    found_alive = False
                    for i in range(len(self.user_team)):
                        if self.user_team[i]['current_hp'] > 0:
                            self.user_pokemon_index = i
                            self.user_choice = self.user_team[i]
                            self.user_max_hp = self.user_choice['max_hp']
                            self.user_current_hp = self.user_choice['current_hp']

                            # Reset stat stages and status for new Pokemon
                            self.user_stat_stages = {
                                'attack': 0, 'defense': 0, 'special-attack': 0,
                                'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
                            }
                            self.user_status = None
                            self.user_status_turns = 0

                            self.battle_log.append(f"Go, **{self.user_choice['pokemon_name']}**!")

                            # Update move buttons for new Pokemon
                            self.clear_items()
                            await self.create_battle_buttons()
                            found_alive = True
                            break

                    if not found_alive:
                        # User is out of Pokemon
                        await self.handle_defeat(interaction)
                        return
        else:
            # Gym Pokemon goes first
            # Check if gym Pokemon is immobilized
            is_immobilized, immobilize_msg = self.check_immobilized(
                self.gym_current_pokemon['pokemon_name'],
                self.gym_status,
                self.gym_status_turns
            )

            if is_immobilized:
                self.battle_log.append(immobilize_msg)
            else:
                # Execute gym Pokemon's move
                if gym_move['damage_class'] == 'status':
                    # Status move
                    self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** used **{gym_move['name']}**!")
                    status_msg = self.execute_status_move(gym_move, is_user_move=False)
                    if status_msg:
                        self.battle_log.append(status_msg)
                else:
                    # Damaging move
                    gym_damage, gym_crit, gym_hit = await self.calculate_damage(
                        gym_move,
                        self.gym_current_pokemon,
                        self.user_choice,
                        self.gym_stat_stages,
                        self.gym_status,
                        self.user_stat_stages
                    )

                    if gym_hit:
                        self.user_current_hp -= gym_damage
                        self.user_team[self.user_pokemon_index]['current_hp'] = self.user_current_hp
                        crit_text = " **Critical hit!**" if gym_crit else ""
                        self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** used **{gym_move['name']}**! Dealt {gym_damage} damage!{crit_text}")

                        # Check for self-destruct moves
                        move_name_lower = gym_move['name'].lower()
                        if 'self-destruct' in move_name_lower or 'selfdestruct' in move_name_lower or move_name_lower == 'explosion':
                            self.gym_current_hp = 0
                            self.battle_log.append(f"💥 **{self.gym_current_pokemon['pokemon_name']}** fainted from the recoil!")
                    else:
                        self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** used **{gym_move['name']}**... but it missed!")

            # Check if user Pokemon fainted
            if self.user_current_hp <= 0:
                self.user_current_hp = 0
                self.user_team[self.user_pokemon_index]['current_hp'] = 0
                self.battle_log.append(f"**{self.user_choice['pokemon_name']}** fainted!")

                # Find next alive Pokemon
                found_alive = False
                for i in range(len(self.user_team)):
                    if self.user_team[i]['current_hp'] > 0:
                        self.user_pokemon_index = i
                        self.user_choice = self.user_team[i]
                        self.user_max_hp = self.user_choice['max_hp']
                        self.user_current_hp = self.user_choice['current_hp']

                        # Reset stat stages and status for new Pokemon
                        self.user_stat_stages = {
                            'attack': 0, 'defense': 0, 'special-attack': 0,
                            'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
                        }
                        self.user_status = None
                        self.user_status_turns = 0

                        self.battle_log.append(f"Go, **{self.user_choice['pokemon_name']}**!")

                        # Update move buttons for new Pokemon
                        self.clear_items()
                        await self.create_battle_buttons()
                        found_alive = True
                        break

                if not found_alive:
                    # User is out of Pokemon
                    await self.handle_defeat(interaction)
                    return

            # User's turn
            # Check if user is immobilized
            is_immobilized, immobilize_msg = self.check_immobilized(
                self.user_choice['pokemon_name'],
                self.user_status,
                self.user_status_turns
            )

            if is_immobilized:
                self.battle_log.append(immobilize_msg)
            else:
                # Execute user's move
                if user_move['damage_class'] == 'status':
                    # Status move
                    self.battle_log.append(f"**{self.user_choice['pokemon_name']}** used **{user_move['name']}**!")
                    status_msg = self.execute_status_move(user_move, is_user_move=True)
                    if status_msg:
                        self.battle_log.append(status_msg)
                else:
                    # Damaging move
                    user_damage, user_crit, user_hit = await self.calculate_damage(
                        user_move,
                        self.user_choice,
                        self.gym_current_pokemon,
                        self.user_stat_stages,
                        self.user_status,
                        self.gym_stat_stages
                    )

                    if user_hit:
                        self.gym_current_hp -= user_damage
                        crit_text = " **Critical hit!**" if user_crit else ""
                        self.battle_log.append(f"**{self.user_choice['pokemon_name']}** used **{user_move['name']}**! Dealt {user_damage} damage!{crit_text}")

                        # Check for self-destruct moves
                        move_name_lower = user_move['name'].lower()
                        if 'self-destruct' in move_name_lower or 'selfdestruct' in move_name_lower or move_name_lower == 'explosion':
                            self.user_current_hp = 0
                            self.user_team[self.user_pokemon_index]['current_hp'] = 0
                            self.battle_log.append(f"💥 **{self.user_choice['pokemon_name']}** fainted from the recoil!")
                    else:
                        self.battle_log.append(f"**{self.user_choice['pokemon_name']}** used **{user_move['name']}**... but it missed!")

            # Check if gym Pokemon fainted
            if self.gym_current_hp <= 0:
                self.gym_current_hp = 0
                self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** fainted!")

                # Check if there are more gym Pokemon
                if self.gym_pokemon_index < len(self.gym_data['pokemon']) - 1:
                    self.gym_pokemon_index += 1
                    await self.load_gym_pokemon()
                    self.battle_log.append(f"**{self.gym_data['name']}** sent out **{self.gym_current_pokemon['pokemon_name']}**!")
                else:
                    # User won!
                    await self.handle_victory(interaction)
                    return

        # Apply end-of-turn status effects
        end_turn_messages = self.apply_end_of_turn_effects()
        for msg in end_turn_messages:
            self.battle_log.append(msg)

        # Check if either Pokemon fainted from status damage
        if self.user_current_hp <= 0:
            self.user_current_hp = 0
            self.user_team[self.user_pokemon_index]['current_hp'] = 0
            self.battle_log.append(f"**{self.user_choice['pokemon_name']}** fainted!")

            # Find next alive Pokemon
            found_alive = False
            for i in range(len(self.user_team)):
                if self.user_team[i]['current_hp'] > 0:
                    self.user_pokemon_index = i
                    self.user_choice = self.user_team[i]
                    self.user_max_hp = self.user_choice['max_hp']
                    self.user_current_hp = self.user_choice['current_hp']

                    # Reset stat stages and status for new Pokemon
                    self.user_stat_stages = {
                        'attack': 0, 'defense': 0, 'special-attack': 0,
                        'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
                    }
                    self.user_status = None
                    self.user_status_turns = 0

                    self.battle_log.append(f"Go, **{self.user_choice['pokemon_name']}**!")

                    # Update move buttons for new Pokemon
                    self.clear_items()
                    await self.create_battle_buttons()
                    found_alive = True
                    break

            if not found_alive:
                # User is out of Pokemon
                await self.handle_defeat(interaction)
                return

        if self.gym_current_hp <= 0:
            self.gym_current_hp = 0
            self.battle_log.append(f"**{self.gym_current_pokemon['pokemon_name']}** fainted!")

            # Check if there are more gym Pokemon
            if self.gym_pokemon_index < len(self.gym_data['pokemon']) - 1:
                self.gym_pokemon_index += 1
                await self.load_gym_pokemon()
                self.battle_log.append(f"**{self.gym_data['name']}** sent out **{self.gym_current_pokemon['pokemon_name']}**!")
            else:
                # User won!
                await self.handle_victory(interaction)
                return

        # Update embed
        embed = self.create_battle_embed()
        if self.battle_message:
            await self.battle_message.edit(embed=embed, view=self)
        else:
            await interaction.edit_original_response(embed=embed, view=self)

    async def calculate_damage(self, move, attacker, defender, attacker_stat_stages, attacker_status, defender_stat_stages):
        """Calculate damage for a move with stat stages and status conditions"""
        # Check accuracy (with accuracy/evasion stages)
        accuracy = move.get('accuracy', 100)
        accuracy_stage = attacker_stat_stages.get('accuracy', 0)
        evasion_stage = defender_stat_stages.get('evasion', 0)
        net_accuracy_stage = accuracy_stage - evasion_stage
        accuracy_multiplier = pkmn.get_stat_stage_multiplier(net_accuracy_stage)

        final_accuracy = min(100, accuracy * accuracy_multiplier)
        if random.randint(1, 100) > final_accuracy:
            return 0, False, False

        # Check critical hit
        is_crit = random.random() < 0.0625  # 6.25% crit chance

        # Get base stats
        if move['damage_class'] == 'physical':
            attack = attacker['stats']['attack']
            defense = defender['stats']['defense']
            attack_stage = attacker_stat_stages.get('attack', 0)
            defense_stage = defender_stat_stages.get('defense', 0)

            # Apply burn to physical attacks (halves attack)
            if attacker_status == 'burn' and not is_crit:  # Crit ignores burn
                attack = int(attack * 0.5)
        elif move['damage_class'] == 'special':
            attack = attacker['stats']['special-attack']
            defense = defender['stats']['special-defense']
            attack_stage = attacker_stat_stages.get('special-attack', 0)
            defense_stage = defender_stat_stages.get('special-defense', 0)
        else:
            # Status move, no damage
            return 0, False, True

        # Calculate base damage
        power = move.get('power', 0)
        if power == 0:
            return 0, False, True

        # Apply stat stages to attack and defense
        attack = pkmn.apply_stat_stages(attack, attack_stage)
        defense = pkmn.apply_stat_stages(defense, defense_stage)

        level = attacker['level']

        # Damage formula
        damage = ((2 * level / 5 + 2) * power * (attack / defense) / 50) + 2

        # Apply type effectiveness
        effectiveness = pkmn.get_type_effectiveness([move['type']], defender['types'])
        damage *= effectiveness

        # Apply critical hit (ignores negative attack stages and positive defense stages)
        if is_crit:
            damage *= 1.5

        # Random factor (0.85 - 1.0)
        damage *= random.uniform(0.85, 1.0)

        return int(damage), is_crit, True

    def apply_stat_change(self, target_stat_stages: dict, stat: str, stages: int) -> tuple:
        """Apply stat change and return message and if it was successful"""
        old_stage = target_stat_stages.get(stat, 0)
        new_stage = max(-6, min(6, old_stage + stages))

        if new_stage == old_stage:
            # Stat is already at max/min
            if stages > 0:
                return f"won't go higher!", False
            else:
                return f"won't go lower!", False

        target_stat_stages[stat] = new_stage

        # Generate message
        stat_name = stat.replace('-', ' ').title()
        if stages > 0:
            if stages == 1:
                return f"{stat_name} rose!", True
            elif stages == 2:
                return f"{stat_name} rose sharply!", True
            else:
                return f"{stat_name} rose drastically!", True
        else:
            if stages == -1:
                return f"{stat_name} fell!", True
            elif stages == -2:
                return f"{stat_name} fell harshly!", True
            else:
                return f"{stat_name} fell severely!", True

    def execute_status_move(self, move: dict, is_user_move: bool) -> str:
        """Execute a status move and return battle log message"""
        move_name = move['name'].lower()
        stat_changes = pkmn.get_move_stat_changes(move_name)

        if not stat_changes:
            # Move doesn't have stat changes (e.g., Confuse Ray, Thunder Wave, etc.)
            return ""

        messages = []

        # Determine which Pokemon is using the move
        if is_user_move:
            user_name = self.user_choice['pokemon_name']
        else:
            user_name = self.gym_current_pokemon['pokemon_name']

        # Apply primary stat change
        if stat_changes['target'] == 'user':
            # Buff user's stats
            if is_user_move:
                message, success = self.apply_stat_change(
                    self.user_stat_stages,
                    stat_changes['stat'],
                    stat_changes['stages']
                )
                if success:
                    messages.append(f"**{user_name}**'s {message}")
            else:
                message, success = self.apply_stat_change(
                    self.gym_stat_stages,
                    stat_changes['stat'],
                    stat_changes['stages']
                )
                if success:
                    messages.append(f"**{user_name}**'s {message}")
        else:
            # Debuff opponent's stats
            if is_user_move:
                message, success = self.apply_stat_change(
                    self.gym_stat_stages,
                    stat_changes['stat'],
                    stat_changes['stages']
                )
                if success:
                    messages.append(f"**{self.gym_current_pokemon['pokemon_name']}**'s {message}")
            else:
                message, success = self.apply_stat_change(
                    self.user_stat_stages,
                    stat_changes['stat'],
                    stat_changes['stages']
                )
                if success:
                    messages.append(f"**{self.user_choice['pokemon_name']}**'s {message}")

        # Apply secondary stat change if exists
        if 'secondary' in stat_changes:
            secondary = stat_changes['secondary']
            if stat_changes['target'] == 'user':
                if is_user_move:
                    message, success = self.apply_stat_change(
                        self.user_stat_stages,
                        secondary['stat'],
                        secondary['stages']
                    )
                    if success:
                        messages.append(f"**{user_name}**'s {message}")
                else:
                    message, success = self.apply_stat_change(
                        self.gym_stat_stages,
                        secondary['stat'],
                        secondary['stages']
                    )
                    if success:
                        messages.append(f"**{user_name}**'s {message}")

        return " ".join(messages)

    def apply_end_of_turn_effects(self) -> list:
        """Apply end-of-turn status condition effects. Returns list of messages."""
        messages = []

        # User status effects
        if self.user_status:
            status_data = pkmn.get_status_condition_effect(self.user_status)

            if self.user_status == 'burn' or self.user_status == 'poison':
                # Damage over time
                damage = int(self.user_max_hp * status_data['damage_percent'])
                damage = max(1, damage)
                self.user_current_hp -= damage
                self.user_current_hp = max(0, self.user_current_hp)
                self.user_team[self.user_pokemon_index]['current_hp'] = self.user_current_hp
                messages.append(f"**{self.user_choice['pokemon_name']}** took {damage} damage from {status_data['name']}! {status_data['emoji']}")

            elif self.user_status == 'badly_poison':
                # Badly poisoned damage increases each turn
                self.user_status_turns += 1
                damage = int(self.user_max_hp * status_data['base_damage'] * self.user_status_turns)
                damage = max(1, damage)
                self.user_current_hp -= damage
                self.user_current_hp = max(0, self.user_current_hp)
                self.user_team[self.user_pokemon_index]['current_hp'] = self.user_current_hp
                messages.append(f"**{self.user_choice['pokemon_name']}** took {damage} damage from {status_data['name']}! {status_data['emoji']}")

            elif self.user_status == 'sleep':
                # Decrement sleep counter
                self.user_status_turns -= 1
                if self.user_status_turns <= 0:
                    self.user_status = None
                    messages.append(f"**{self.user_choice['pokemon_name']}** woke up!")

        # Gym Pokemon status effects
        if self.gym_status:
            status_data = pkmn.get_status_condition_effect(self.gym_status)

            if self.gym_status == 'burn' or self.gym_status == 'poison':
                damage = int(self.gym_max_hp * status_data['damage_percent'])
                damage = max(1, damage)
                self.gym_current_hp -= damage
                self.gym_current_hp = max(0, self.gym_current_hp)
                messages.append(f"**{self.gym_current_pokemon['pokemon_name']}** took {damage} damage from {status_data['name']}! {status_data['emoji']}")

            elif self.gym_status == 'badly_poison':
                self.gym_status_turns += 1
                damage = int(self.gym_max_hp * status_data['base_damage'] * self.gym_status_turns)
                damage = max(1, damage)
                self.gym_current_hp -= damage
                self.gym_current_hp = max(0, self.gym_current_hp)
                messages.append(f"**{self.gym_current_pokemon['pokemon_name']}** took {damage} damage from {status_data['name']}! {status_data['emoji']}")

            elif self.gym_status == 'sleep':
                self.gym_status_turns -= 1
                if self.gym_status_turns <= 0:
                    self.gym_status = None
                    messages.append(f"**{self.gym_current_pokemon['pokemon_name']}** woke up!")

        return messages

    def check_immobilized(self, pokemon_name: str, status: str, status_turns: int) -> tuple:
        """Check if Pokemon is immobilized by status. Returns (is_immobilized, message)"""
        if not status:
            return False, ""

        status_data = pkmn.get_status_condition_effect(status)

        if status == 'sleep':
            return True, f"**{pokemon_name}** is fast asleep! {status_data['emoji']}"

        elif status == 'freeze':
            # Check for thaw
            if random.random() < status_data['thaw_chance']:
                return False, f"**{pokemon_name}** thawed out!"
            return True, f"**{pokemon_name}** is frozen solid! {status_data['emoji']}"

        elif status == 'paralysis':
            # 25% chance to be fully paralyzed
            if random.random() < status_data['immobilize_chance']:
                return True, f"**{pokemon_name}** is fully paralyzed! {status_data['emoji']}"

        return False, ""

    def create_battle_embed(self):
        """Create battle status embed"""
        embed = discord.Embed(
            title=f"🏟️ Gym Battle: {self.gym_data['name']} vs. {self.user.display_name}",
            description=f"**Turn {self.turn_count}**",
            color=discord.Color.red()
        )

        # User Pokemon status
        user_hp_percent = (self.user_current_hp / self.user_max_hp) * 100
        user_hp_bar = pkmn.create_hp_bar(user_hp_percent)

        # Add status condition indicator
        user_status_text = ""
        if self.user_status:
            status_data = pkmn.get_status_condition_effect(self.user_status)
            user_status_text = f"\n**Status:** {status_data['emoji']} {status_data['name']}"

        # Add stat stages indicator (only show non-zero stages)
        user_stages_text = ""
        active_stages = [f"{stat.replace('-', ' ').title()}: {'+' if stage > 0 else ''}{stage}"
                        for stat, stage in self.user_stat_stages.items() if stage != 0]
        if active_stages:
            user_stages_text = f"\n**Stages:** {', '.join(active_stages[:3])}"  # Show max 3

        # Show team status
        alive_count = sum(1 for p in self.user_team if p['current_hp'] > 0)
        team_status = f"Team: {alive_count}/{len(self.user_team)}"
        user_shiny = "✨ " if self.user_choice.get('is_shiny', False) else ""

        embed.add_field(
            name=f"Your {user_shiny}{self.user_choice['pokemon_name']} (Lv.{self.user_choice['level']}) - {team_status}",
            value=f"{user_hp_bar}\nHP: {self.user_current_hp}/{self.user_max_hp}{user_status_text}{user_stages_text}",
            inline=True
        )

        # Gym Pokemon status
        gym_hp_percent = (self.gym_current_hp / self.gym_max_hp) * 100
        gym_hp_bar = pkmn.create_hp_bar(gym_hp_percent)

        # Add status condition indicator
        gym_status_text = ""
        if self.gym_status:
            status_data = pkmn.get_status_condition_effect(self.gym_status)
            gym_status_text = f"\n**Status:** {status_data['emoji']} {status_data['name']}"

        # Add stat stages indicator
        gym_stages_text = ""
        active_stages = [f"{stat.replace('-', ' ').title()}: {'+' if stage > 0 else ''}{stage}"
                        for stat, stage in self.gym_stat_stages.items() if stage != 0]
        if active_stages:
            gym_stages_text = f"\n**Stages:** {', '.join(active_stages[:3])}"  # Show max 3

        gym_info = f"{self.gym_data['name']}'s {self.gym_current_pokemon['pokemon_name']} (Lv.{self.gym_current_pokemon['level']})"
        gym_remaining = f"\n**Remaining:** {len(self.gym_data['pokemon']) - self.gym_pokemon_index}/{len(self.gym_data['pokemon'])} Pokemon"

        embed.add_field(
            name=gym_info,
            value=f"{gym_hp_bar}\nHP: {self.gym_current_hp}/{self.gym_max_hp}{gym_status_text}{gym_stages_text}{gym_remaining}",
            inline=True
        )

        # Battle log (last 5 messages)
        if self.battle_log:
            log_text = "\n".join(self.battle_log[-5:])
            embed.add_field(
                name="📜 Battle Log",
                value=log_text,
                inline=False
            )

        embed.set_footer(text="Choose your move!")

        return embed

    async def handle_victory(self, interaction: discord.Interaction):
        """Handle gym victory"""
        self.clear_items()

        embed = discord.Embed(
            title=f"🏆 Victory!",
            description=f"**{self.user.display_name}** defeated **{self.gym_data['name']}**!",
            color=discord.Color.gold()
        )

        # Add badge icon as thumbnail
        if 'badge_icon' in self.gym_data:
            embed.set_thumbnail(url=self.gym_data['badge_icon'])

        # Award species XP for victory to ALL Pokemon in team
        for pokemon in self.user_team:
            await db.add_species_xp(
                self.user.id,
                self.guild_id,
                pokemon['pokemon_id'],
                pokemon['pokemon_name'],
                25,  # XP for gym victory
                is_win=True
            )

        # Track quest progress
        quest_currency = 0
        quest_completed = []

        if not self.already_defeated:
            # Award badge
            await db.award_gym_badge(self.user.id, self.guild_id, self.gym_key)

            # Update quest progress for defeating gym and earning badge
            defeat_quest = await db.update_quest_progress(self.user.id, self.guild_id, 'defeat_gym_leader')
            badge_quest = await db.update_quest_progress(self.user.id, self.guild_id, 'earn_badge')

            # Combine quest rewards
            if defeat_quest and defeat_quest.get('completed_quests'):
                quest_completed.extend(defeat_quest['completed_quests'])
                quest_currency += defeat_quest.get('total_currency', 0)
            if badge_quest and badge_quest.get('completed_quests'):
                quest_completed.extend(badge_quest['completed_quests'])
                quest_currency += badge_quest.get('total_currency', 0)

            # Award quest currency if any
            if quest_currency > 0:
                await db.add_currency(self.user.id, self.guild_id, quest_currency)

            # Award Pokedollars
            pokedollars_earned = self.gym_data['rewards']['pokedollars']
            await db.add_currency(self.user.id, self.guild_id, pokedollars_earned)

            # Update quest for earning pokedollars
            earn_quest = await db.update_quest_progress(self.user.id, self.guild_id, 'earn_pokedollars', increment=pokedollars_earned)
            if earn_quest and earn_quest.get('completed_quests'):
                quest_completed.extend(earn_quest['completed_quests'])
                quest_currency += earn_quest.get('total_currency', 0)
                await db.add_currency(self.user.id, self.guild_id, earn_quest.get('total_currency', 0))

            # Award pack
            # Get pack from shop
            pack_name = self.gym_data['rewards']['pack']
            shop_items = await db.get_shop_items()
            pack_item = next((item for item in shop_items if item['item_name'] == pack_name), None)

            if pack_item:
                await db.add_pack(self.user.id, self.guild_id, pack_name, pack_item['pack_config'])

            # Show rewards
            rewards_text = f"**{self.gym_data['badge']}**\n"
            rewards_text += f"₽{pokedollars_earned} Pokedollars\n"
            rewards_text += f"1x {pack_name}"

            embed.add_field(
                name="🎁 Rewards Earned",
                value=rewards_text,
                inline=False
            )
        else:
            embed.add_field(
                name="ℹ️ Already Defeated",
                value="You've already earned rewards from this gym. Great battle practice though!",
                inline=False
            )

        # Show XP gained for all team members
        team_names = [p['pokemon_name'] for p in self.user_team]
        if len(team_names) == 1:
            xp_text = f"**{team_names[0]}** gained +25 XP!"
        elif len(team_names) == 2:
            xp_text = f"**{team_names[0]}** and **{team_names[1]}** each gained +25 XP!"
        else:
            xp_text = f"**{', '.join(team_names[:-1])}, and {team_names[-1]}** each gained +25 XP!"

        embed.add_field(
            name=f"⭐ Team XP Gained!",
            value=xp_text,
            inline=False
        )

        # Add quest completion notification if any
        if quest_completed:
            quest_text = []
            seen = set()
            for q in quest_completed:
                desc = q.get('description', 'Quest')
                if desc not in seen:
                    seen.add(desc)
                    quest_text.append(f"✅ {desc} (+₽{q['reward']})")

            if quest_text:
                embed.add_field(
                    name="🎯 Quests Completed!",
                    value='\n'.join(quest_text),
                    inline=False
                )

        await interaction.edit_original_response(embed=embed, view=self)

    async def handle_defeat(self, interaction: discord.Interaction):
        """Handle gym defeat"""
        self.clear_items()

        # Award some XP for participation to ALL Pokemon in team
        for pokemon in self.user_team:
            await db.add_species_xp(
                self.user.id,
                self.guild_id,
                pokemon['pokemon_id'],
                pokemon['pokemon_name'],
                10,  # Small XP for defeat
                is_win=False
            )

        embed = discord.Embed(
            title=f"💔 Defeat",
            description=f"**{self.user.display_name}** was defeated by **{self.gym_data['name']}**!",
            color=discord.Color.dark_gray()
        )

        embed.add_field(
            name="💪 Keep Training!",
            value=f"Train your Pokemon and try again! You made it past {self.gym_pokemon_index}/{len(self.gym_data['pokemon'])} of their Pokemon.",
            inline=False
        )

        # Show XP gained for all team members
        team_names = [p['pokemon_name'] for p in self.user_team]
        if len(team_names) == 1:
            xp_text = f"**{team_names[0]}** gained +10 XP for the battle experience!"
        elif len(team_names) == 2:
            xp_text = f"**{team_names[0]}** and **{team_names[1]}** each gained +10 XP for the battle experience!"
        else:
            xp_text = f"**{', '.join(team_names[:-1])}, and {team_names[-1]}** each gained +10 XP for the battle experience!"

        embed.add_field(
            name=f"⭐ Team XP Gained",
            value=xp_text,
            inline=False
        )

        await interaction.edit_original_response(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user.id


# Interactive Battle View - Turn-Based System
class BattleView(View):
    def __init__(self, user1: discord.Member, user2: discord.Member, guild_id: int):
        super().__init__(timeout=600)  # 10 minute timeout for turn-based
        self.user1 = user1
        self.user2 = user2
        self.guild_id = guild_id
        self.user1_pokemon = []
        self.user2_pokemon = []
        self.user1_choice = None  # {id, pokemon_name, pokemon_id, types, moves}
        self.user2_choice = None
        self.user1_ready = False
        self.user2_ready = False
        self.battle_started = False
        self.battle_log = []
        self.winner = None
        self.battle_channel = None  # Store channel for posting battle log

        # Battle state
        self.current_turn = None  # 1 or 2
        self.p1_hp = 0
        self.p2_hp = 0
        self.p1_max_hp = 0
        self.p2_max_hp = 0
        self.p1_stats = {}
        self.p2_stats = {}
        self.p1_level = 1
        self.p2_level = 1
        self.turn_count = 0

        # Stat stages (player 1 and player 2)
        self.p1_stat_stages = {
            'attack': 0, 'defense': 0, 'special-attack': 0,
            'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
        }
        self.p2_stat_stages = {
            'attack': 0, 'defense': 0, 'special-attack': 0,
            'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
        }

        # Status conditions
        self.p1_status = None
        self.p1_status_turns = 0
        self.p2_status = None
        self.p2_status_turns = 0

        # Pagination state
        self.user1_page = 0
        self.user2_page = 0
        self.pokemon_per_page = 25

        # Dynamic selects (will be populated later)
        self.user1_select = None
        self.user2_select = None

    async def load_pokemon(self):
        """Load Pokemon for both users"""
        self.user1_pokemon = await db.get_user_pokemon_for_trade(self.user1.id, self.guild_id)
        self.user2_pokemon = await db.get_user_pokemon_for_trade(self.user2.id, self.guild_id)

    def calculate_stats(self, pokemon_id: int, level: int):
        """Calculate battle stats based on base stats and level"""
        base = pkmn.get_pokemon_stats(pokemon_id)
        return {
            'hp': base['hp'] + (level * 2),
            'attack': base['attack'] + int(level * 1.5),
            'defense': base['defense'] + level,
            'speed': base['speed']
        }

    def calculate_damage(self, move: dict, attacker_stats: dict, defender_stats: dict, defender_types: list, attacker_stat_stages: dict, defender_stat_stages: dict, attacker_status: str = None) -> tuple:
        """Calculate damage from a move. Returns (damage, is_crit, hit_success)"""
        # Check accuracy (with accuracy/evasion stages)
        accuracy = move.get('accuracy', 100)
        accuracy_stage = attacker_stat_stages.get('accuracy', 0)
        evasion_stage = defender_stat_stages.get('evasion', 0)
        net_accuracy_stage = accuracy_stage - evasion_stage
        accuracy_multiplier = pkmn.get_stat_stage_multiplier(net_accuracy_stage)

        final_accuracy = min(100, accuracy * accuracy_multiplier)
        if random.randint(1, 100) > final_accuracy:
            return 0, False, False  # Miss!

        # Check if it's a status move
        if move['damage_class'] == 'status' or move.get('power', 0) == 0:
            return 0, False, True  # Status move, no damage but it "hit"

        # Check critical hit
        is_crit = random.random() < 0.0625  # 6.25% crit chance

        # Base damage from move power
        if move['damage_class'] == 'physical':
            attack = attacker_stats['attack']
            defense = defender_stats['defense']
            attack_stage = attacker_stat_stages.get('attack', 0)
            defense_stage = defender_stat_stages.get('defense', 0)

            # Apply burn to physical attacks (halves attack)
            if attacker_status == 'burn' and not is_crit:
                attack = int(attack * 0.5)

            # Apply stat stages
            attack = pkmn.apply_stat_stages(attack, attack_stage)
            defense = pkmn.apply_stat_stages(defense, defense_stage)

            base_damage = max(1, int((move['power'] * attack) / (defense * 2)))
        elif move['damage_class'] == 'special':
            # Use attack as special attack for simplicity
            attack = attacker_stats['attack']
            defense = defender_stats['defense']
            attack_stage = attacker_stat_stages.get('special-attack', 0)
            defense_stage = defender_stat_stages.get('special-defense', 0)

            # Apply stat stages
            attack = pkmn.apply_stat_stages(attack, attack_stage)
            defense = pkmn.apply_stat_stages(defense, defense_stage)

            base_damage = max(1, int((move['power'] * attack) / (defense * 2)))
        else:
            return 0, False, True

        # Type effectiveness
        type_mult = pkmn.get_type_effectiveness([move['type']], defender_types)

        # Random variation (85-100%)
        random_mult = random.uniform(0.85, 1.0)

        # Critical hit
        crit_mult = 1.5 if is_crit else 1.0

        damage = int(base_damage * type_mult * random_mult * crit_mult)
        return max(1, damage), is_crit, True

    def apply_stat_change(self, target_stat_stages: dict, stat: str, stages: int) -> tuple:
        """Apply stat change and return message and if it was successful"""
        old_stage = target_stat_stages.get(stat, 0)
        new_stage = max(-6, min(6, old_stage + stages))

        if new_stage == old_stage:
            # Stat is already at max/min
            if stages > 0:
                return f"won't go higher!", False
            else:
                return f"won't go lower!", False

        target_stat_stages[stat] = new_stage

        # Generate message
        stat_name = stat.replace('-', ' ').title()
        if stages > 0:
            if stages == 1:
                return f"{stat_name} rose!", True
            elif stages == 2:
                return f"{stat_name} rose sharply!", True
            else:
                return f"{stat_name} rose drastically!", True
        else:
            if stages == -1:
                return f"{stat_name} fell!", True
            elif stages == -2:
                return f"{stat_name} fell harshly!", True
            else:
                return f"{stat_name} fell severely!", True

    def execute_status_move(self, move: dict, is_p1_move: bool) -> str:
        """Execute a status move and return battle log message"""
        move_name = move['name'].lower()
        stat_changes = pkmn.get_move_stat_changes(move_name)

        if not stat_changes:
            # Move doesn't have stat changes (e.g., Confuse Ray, Thunder Wave, etc.)
            return ""

        messages = []

        # Determine which Pokemon is using the move
        if is_p1_move:
            user_name = self.user1_choice['pokemon_name']
        else:
            user_name = self.user2_choice['pokemon_name']

        # Apply primary stat change
        if stat_changes['target'] == 'user':
            # Buff user's stats
            if is_p1_move:
                message, success = self.apply_stat_change(
                    self.p1_stat_stages,
                    stat_changes['stat'],
                    stat_changes['stages']
                )
                if success:
                    messages.append(f"**{user_name}**'s {message}")
            else:
                message, success = self.apply_stat_change(
                    self.p2_stat_stages,
                    stat_changes['stat'],
                    stat_changes['stages']
                )
                if success:
                    messages.append(f"**{user_name}**'s {message}")
        else:
            # Debuff opponent's stats
            if is_p1_move:
                message, success = self.apply_stat_change(
                    self.p2_stat_stages,
                    stat_changes['stat'],
                    stat_changes['stages']
                )
                if success:
                    messages.append(f"**{self.user2_choice['pokemon_name']}**'s {message}")
            else:
                message, success = self.apply_stat_change(
                    self.p1_stat_stages,
                    stat_changes['stat'],
                    stat_changes['stages']
                )
                if success:
                    messages.append(f"**{self.user1_choice['pokemon_name']}**'s {message}")

        # Apply secondary stat change if exists
        if 'secondary' in stat_changes:
            secondary = stat_changes['secondary']
            if stat_changes['target'] == 'user':
                if is_p1_move:
                    message, success = self.apply_stat_change(
                        self.p1_stat_stages,
                        secondary['stat'],
                        secondary['stages']
                    )
                    if success:
                        messages.append(f"**{user_name}**'s {message}")
                else:
                    message, success = self.apply_stat_change(
                        self.p2_stat_stages,
                        secondary['stat'],
                        secondary['stages']
                    )
                    if success:
                        messages.append(f"**{user_name}**'s {message}")

        return " ".join(messages)

    async def start_battle(self):
        """Initialize battle after both players are ready"""
        self.battle_started = True

        # Get Pokemon species levels (shared across all of same species)
        self.p1_level = await db.get_species_level(
            self.user1.id, self.guild_id,
            self.user1_choice['pokemon_id'], self.user1_choice['pokemon_name']
        )
        self.p2_level = await db.get_species_level(
            self.user2.id, self.guild_id,
            self.user2_choice['pokemon_id'], self.user2_choice['pokemon_name']
        )

        # Calculate stats
        self.p1_stats = self.calculate_stats(self.user1_choice['pokemon_id'], self.p1_level)
        self.p2_stats = self.calculate_stats(self.user2_choice['pokemon_id'], self.p2_level)

        # Set HP
        self.p1_hp = self.p1_stats['hp']
        self.p2_hp = self.p2_stats['hp']
        self.p1_max_hp = self.p1_hp
        self.p2_max_hp = self.p2_hp

        # Determine who goes first based on speed
        if self.p1_stats['speed'] >= self.p2_stats['speed']:
            self.current_turn = 1
        else:
            self.current_turn = 2

        # Battle log
        self.battle_log.append(f"⚔️ **Battle Start!**")
        self.battle_log.append(f"{self.user1.display_name}'s **{self.user1_choice['pokemon_name']}** (Lv.{self.p1_level})")
        self.battle_log.append(f"vs {self.user2.display_name}'s **{self.user2_choice['pokemon_name']}** (Lv.{self.p2_level})")
        self.battle_log.append("")

        # Add move buttons dynamically
        self.add_move_buttons()

    def add_move_buttons(self):
        """Add move buttons for both players"""
        # Clear existing move buttons if any
        items_to_remove = [item for item in self.children if isinstance(item, Button) and item.custom_id and 'move' in item.custom_id]
        for item in items_to_remove:
            self.remove_item(item)

        # User 1 moves
        for i, move in enumerate(self.user1_choice.get('moves', [])):
            button = Button(
                label=move['name'],
                style=discord.ButtonStyle.primary,
                custom_id=f"user1_move_{i}",
                row=2
            )
            button.callback = self.create_move_callback(1, i, move)
            self.add_item(button)

        # User 2 moves
        for i, move in enumerate(self.user2_choice.get('moves', [])):
            button = Button(
                label=move['name'],
                style=discord.ButtonStyle.green,
                custom_id=f"user2_move_{i}",
                row=3
            )
            button.callback = self.create_move_callback(2, i, move)
            self.add_item(button)

        # Update button states
        self.update_button_states()

    def create_move_callback(self, player: int, move_index: int, move: dict):
        """Create a callback for a move button"""
        async def callback(interaction: discord.Interaction):
            # Check if it's this player's turn
            if player != self.current_turn:
                await interaction.response.send_message("❌ It's not your turn!", ephemeral=True)
                return

            # Check if correct user
            if player == 1 and interaction.user.id != self.user1.id:
                await interaction.response.send_message("❌ This is not your battle!", ephemeral=True)
                return
            elif player == 2 and interaction.user.id != self.user2.id:
                await interaction.response.send_message("❌ This is not your battle!", ephemeral=True)
                return

            # Process the attack
            await self.process_turn(interaction, player, move)

        return callback

    async def process_turn(self, interaction: discord.Interaction, attacker: int, move: dict):
        """Process a single turn of battle"""
        self.turn_count += 1

        if attacker == 1:
            attacker_name = self.user1_choice['pokemon_name']
            defender_name = self.user2_choice['pokemon_name']
            attacker_stats = self.p1_stats
            defender_stats = self.p2_stats
            defender_types = self.user2_choice.get('types', ['normal'])
            attacker_stat_stages = self.p1_stat_stages
            defender_stat_stages = self.p2_stat_stages
            attacker_status = self.p1_status
        else:
            attacker_name = self.user2_choice['pokemon_name']
            defender_name = self.user1_choice['pokemon_name']
            attacker_stats = self.p2_stats
            defender_stats = self.p1_stats
            defender_types = self.user1_choice.get('types', ['normal'])
            attacker_stat_stages = self.p2_stat_stages
            defender_stat_stages = self.p1_stat_stages
            attacker_status = self.p2_status

        # Build turn log
        self.battle_log.append(f"**Turn {self.turn_count}:**")

        # Check if it's a status move
        if move['damage_class'] == 'status':
            self.battle_log.append(f"**{attacker_name}** used **{move['name']}**!")
            status_msg = self.execute_status_move(move, is_p1_move=(attacker == 1))
            if status_msg:
                self.battle_log.append(status_msg)
        else:
            # Calculate damage
            damage, is_crit, hit = self.calculate_damage(move, attacker_stats, defender_stats, defender_types, attacker_stat_stages, defender_stat_stages, attacker_status)

            self.battle_log.append(f"⚡ **{attacker_name}** used **{move['name']}**!")

            if not hit:
                self.battle_log.append(f"💨 The attack missed!")
            else:
                # Apply damage
                if attacker == 1:
                    self.p2_hp -= damage
                    self.p2_hp = max(0, self.p2_hp)
                else:
                    self.p1_hp -= damage
                    self.p1_hp = max(0, self.p1_hp)

                crit_text = " **Critical hit!**" if is_crit else ""
                self.battle_log.append(f"Dealt {damage} damage!{crit_text}")

                # Check for self-destruct moves
                move_name_lower = move['name'].lower()
                if 'self-destruct' in move_name_lower or 'selfdestruct' in move_name_lower or move_name_lower == 'explosion':
                    if attacker == 1:
                        self.p1_hp = 0
                    else:
                        self.p2_hp = 0
                    self.battle_log.append(f"💥 **{attacker_name}** fainted from the recoil!")

                # Type effectiveness message
                type_eff = pkmn.get_type_effectiveness([move['type']], defender_types)
                if type_eff == 0:
                    effect_text = "It has no effect..."
                elif type_eff > 1:
                    effect_text = "It's super effective!"
                elif type_eff < 1:
                    effect_text = "It's not very effective..."
                else:
                    effect_text = ""

                if effect_text:
                    self.battle_log.append(f"✨ {effect_text}")

                # Show HP status
                current_hp = self.p2_hp if attacker == 1 else self.p1_hp
                max_hp = self.p2_max_hp if attacker == 1 else self.p1_max_hp
                self.battle_log.append(f"**{defender_name}** HP: {current_hp}/{max_hp}")

        self.battle_log.append("")

        # Check for winner
        if self.p1_hp <= 0:
            self.winner = 2
            self.battle_log.append(f"🏆 **{self.user2.display_name}'s {self.user2_choice['pokemon_name']} wins!**")
            await self.end_battle()
        elif self.p2_hp <= 0:
            self.winner = 1
            self.battle_log.append(f"🏆 **{self.user1.display_name}'s {self.user1_choice['pokemon_name']} wins!**")
            await self.end_battle()
        else:
            # Switch turns
            self.current_turn = 2 if self.current_turn == 1 else 1
            self.update_button_states()

        await self.update_display(interaction)

    def update_button_states(self):
        """Enable/disable buttons based on current turn"""
        for item in self.children:
            if isinstance(item, Button) and item.custom_id and 'move' in item.custom_id:
                if 'user1' in item.custom_id:
                    item.disabled = (self.current_turn != 1)
                elif 'user2' in item.custom_id:
                    item.disabled = (self.current_turn != 2)

    async def end_battle(self):
        """Clean up battle and record results"""
        # Disable all buttons
        for item in self.children:
            item.disabled = True

        # Determine winner/loser
        if self.winner == 1:
            winner_id, loser_id = self.user1.id, self.user2.id
            winner_pokemon_id, loser_pokemon_id = self.user1_choice['id'], self.user2_choice['id']
            winner_name, loser_name = self.user1_choice['pokemon_name'], self.user2_choice['pokemon_name']
            winner_pokemon_species_id, loser_pokemon_species_id = self.user1_choice['pokemon_id'], self.user2_choice['pokemon_id']
            winner_user, loser_user = self.user1, self.user2
        else:
            winner_id, loser_id = self.user2.id, self.user1.id
            winner_pokemon_id, loser_pokemon_id = self.user2_choice['id'], self.user1_choice['id']
            winner_name, loser_name = self.user2_choice['pokemon_name'], self.user1_choice['pokemon_name']
            winner_pokemon_species_id, loser_pokemon_species_id = self.user2_choice['pokemon_id'], self.user1_choice['pokemon_id']
            winner_user, loser_user = self.user2, self.user1

        # Record battle
        await db.record_battle(
            self.guild_id, winner_id, loser_id,
            winner_pokemon_id, loser_pokemon_id,
            winner_name, loser_name, self.turn_count
        )

        # Update quest progress for winner (win_battles)
        battle_quest_result = await db.update_quest_progress(winner_id, self.guild_id, 'win_battles')

        # Notify if quest completed
        if battle_quest_result and battle_quest_result.get('completed_quests'):
            quest_currency = battle_quest_result.get('total_currency', 0)
            quest_count = len(battle_quest_result['completed_quests'])
            self.battle_log.append("")
            self.battle_log.append(f"✅ **{winner_user.display_name} completed {quest_count} daily quest(s)!**")
            self.battle_log.append(f"Earned **₽{quest_currency}** Pokedollars!")

        # Award Pokemon species XP
        winner_xp_result = await db.add_species_xp(
            winner_id, self.guild_id,
            winner_pokemon_species_id, winner_name,
            50,  # Winner gets 50 XP
            is_win=True
        )

        loser_xp_result = await db.add_species_xp(
            loser_id, self.guild_id,
            loser_pokemon_species_id, loser_name,
            20,  # Loser gets 20 XP
            is_win=False
        )

        # Add level up notifications to battle log
        if winner_xp_result and winner_xp_result.get('leveled_up'):
            self.battle_log.append("")
            self.battle_log.append(f"✨ **{winner_user.display_name}'s {winner_name} leveled up!**")
            self.battle_log.append(f"Level {winner_xp_result['old_level']} → Level {winner_xp_result['new_level']}")

        if loser_xp_result and loser_xp_result.get('leveled_up'):
            self.battle_log.append("")
            self.battle_log.append(f"✨ **{loser_user.display_name}'s {loser_name} leveled up!**")
            self.battle_log.append(f"Level {loser_xp_result['old_level']} → Level {loser_xp_result['new_level']}")

        # Post full battle log to channel
        if self.battle_channel:
            await self.post_battle_log()

    async def post_battle_log(self):
        """Post the complete battle log as a message in the channel"""
        # Create battle summary embed
        embed = discord.Embed(
            title="⚔️ Battle Complete!",
            description=f"**{self.user1.display_name}** vs **{self.user2.display_name}**",
            color=discord.Color.gold()
        )

        # Winner announcement
        if self.winner == 1:
            winner_name = self.user1.display_name
            winner_pokemon = self.user1_choice['pokemon_name']
        else:
            winner_name = self.user2.display_name
            winner_pokemon = self.user2_choice['pokemon_name']

        embed.add_field(
            name="🏆 Victor",
            value=f"**{winner_name}** with {winner_pokemon}!",
            inline=False
        )

        embed.add_field(
            name=f"📊 Battle Stats",
            value=f"Turns: {self.turn_count}",
            inline=False
        )

        # Split battle log into chunks if needed (Discord has a 4096 char limit)
        full_log = '\n'.join(self.battle_log)

        # Add battle log (truncate if too long)
        if len(full_log) > 4000:
            full_log = full_log[:4000] + "\n...(battle log truncated)"

        embed.add_field(
            name="📜 Battle Log",
            value=full_log,
            inline=False
        )

        await self.battle_channel.send(embed=embed)

    def create_embed(self):
        """Create the battle embed"""
        if not self.battle_started:
            # Pre-battle selection
            embed = discord.Embed(
                title="⚔️ Pokemon Battle!",
                description=f"**{self.user1.display_name}** vs **{self.user2.display_name}**",
                color=discord.Color.red()
            )

            # User 1's choice
            user1_text = "Not selected"
            if self.user1_choice:
                shiny_indicator = "✨ " if self.user1_choice.get('is_shiny', False) else ""
                user1_text = f"#{self.user1_choice['pokemon_id']:03d} {shiny_indicator}{self.user1_choice['pokemon_name']}"
                if self.user1_ready:
                    user1_text += " ✅"

            embed.add_field(
                name=f"{self.user1.display_name}'s Pokemon",
                value=user1_text,
                inline=True
            )

            # User 2's choice
            user2_text = "Not selected"
            if self.user2_choice:
                shiny_indicator = "✨ " if self.user2_choice.get('is_shiny', False) else ""
                user2_text = f"#{self.user2_choice['pokemon_id']:03d} {shiny_indicator}{self.user2_choice['pokemon_name']}"
                if self.user2_ready:
                    user2_text += " ✅"

            embed.add_field(
                name=f"{self.user2.display_name}'s Pokemon",
                value=user2_text,
                inline=True
            )

            # Status
            status_parts = []
            if self.user1_ready:
                status_parts.append(f"✅ {self.user1.display_name} is ready!")
            if self.user2_ready:
                status_parts.append(f"✅ {self.user2.display_name} is ready!")

            if status_parts:
                embed.add_field(
                    name="Status",
                    value='\n'.join(status_parts),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Status",
                    value="⏳ Both trainers must select a Pokemon and ready up!",
                    inline=False
                )

            embed.set_footer(text="Select your Pokemon and click 'Ready to Battle!' when ready")
        else:
            # Active battle
            if self.winner:
                title = "⚔️ Battle Complete!"
                color = discord.Color.gold()
            else:
                turn_player = self.user1.display_name if self.current_turn == 1 else self.user2.display_name
                title = f"⚔️ Battle - {turn_player}'s Turn!"
                color = discord.Color.blue() if self.current_turn == 1 else discord.Color.green()

            embed = discord.Embed(
                title=title,
                color=color
            )

            # HP bars
            p1_hp_bar = self.create_hp_bar(self.p1_hp, self.p1_max_hp)
            p2_hp_bar = self.create_hp_bar(self.p2_hp, self.p2_max_hp)

            p1_shiny = "✨ " if self.user1_choice.get('is_shiny', False) else ""
            p2_shiny = "✨ " if self.user2_choice.get('is_shiny', False) else ""

            embed.add_field(
                name=f"{self.user1.display_name}'s {p1_shiny}{self.user1_choice['pokemon_name']}",
                value=f"{p1_hp_bar} {self.p1_hp}/{self.p1_max_hp} HP",
                inline=False
            )

            embed.add_field(
                name=f"{self.user2.display_name}'s {p2_shiny}{self.user2_choice['pokemon_name']}",
                value=f"{p2_hp_bar} {self.p2_hp}/{self.p2_max_hp} HP",
                inline=False
            )

            # Battle log (last 10 lines to avoid character limit)
            log_lines = self.battle_log[-10:]
            if log_lines:
                embed.add_field(
                    name="Battle Log",
                    value='\n'.join(log_lines),
                    inline=False
                )

        return embed

    def create_hp_bar(self, current: int, maximum: int) -> str:
        """Create a visual HP bar"""
        if maximum == 0:
            percentage = 0
        else:
            percentage = current / maximum

        bar_length = 10
        filled = int(percentage * bar_length)
        empty = bar_length - filled

        return f"[{'█' * filled}{'░' * empty}]"

    async def update_display(self, interaction: discord.Interaction):
        """Update the display"""
        embed = self.create_embed()
        # Check if interaction was already responded to (deferred)
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
        else:
            await interaction.response.edit_message(embed=embed, view=self)

    def update_pokemon_selects(self):
        """Update Pokemon selection dropdowns with pagination"""
        self.clear_items()

        # User 1 select
        start_idx = self.user1_page * self.pokemon_per_page
        end_idx = min(start_idx + self.pokemon_per_page, len(self.user1_pokemon))
        user1_page_pokemon = self.user1_pokemon[start_idx:end_idx]

        self.user1_select = Select(
            placeholder=f"{self.user1.display_name}: Select your Pokemon...",
            custom_id="battle_user1_select",
            min_values=1,
            max_values=1,
            row=0
        )

        for pokemon in user1_page_pokemon:
            level = pokemon.get('level', 1)
            is_shiny = pokemon.get('is_shiny', False)
            shiny_indicator = "✨ " if is_shiny else ""
            label = f"Lv.{level} | #{pokemon['pokemon_id']:03d} {shiny_indicator}{pokemon['pokemon_name']}"
            self.user1_select.add_option(
                label=label[:100],  # Discord limit
                value=str(pokemon['id']),
                emoji="✨" if is_shiny else "⚔️"
            )

        self.user1_select.callback = self.user1_select_callback
        self.add_item(self.user1_select)

        # User 2 select
        start_idx = self.user2_page * self.pokemon_per_page
        end_idx = min(start_idx + self.pokemon_per_page, len(self.user2_pokemon))
        user2_page_pokemon = self.user2_pokemon[start_idx:end_idx]

        self.user2_select = Select(
            placeholder=f"{self.user2.display_name}: Select your Pokemon...",
            custom_id="battle_user2_select",
            min_values=1,
            max_values=1,
            row=1
        )

        for pokemon in user2_page_pokemon:
            level = pokemon.get('level', 1)
            is_shiny = pokemon.get('is_shiny', False)
            shiny_indicator = "✨ " if is_shiny else ""
            label = f"Lv.{level} | #{pokemon['pokemon_id']:03d} {shiny_indicator}{pokemon['pokemon_name']}"
            self.user2_select.add_option(
                label=label[:100],  # Discord limit
                value=str(pokemon['id']),
                emoji="✨" if is_shiny else "⚔️"
            )

        self.user2_select.callback = self.user2_select_callback
        self.add_item(self.user2_select)

        # Add pagination buttons for user 1
        user1_total_pages = (len(self.user1_pokemon) + self.pokemon_per_page - 1) // self.pokemon_per_page
        if user1_total_pages > 1:
            prev1_button = Button(
                label=f"◀ {self.user1.display_name}",
                style=discord.ButtonStyle.secondary,
                disabled=(self.user1_page == 0 or self.battle_started),
                custom_id="user1_prev",
                row=2
            )
            prev1_button.callback = self.user1_previous_page
            self.add_item(prev1_button)

            next1_button = Button(
                label=f"{self.user1.display_name} ▶",
                style=discord.ButtonStyle.secondary,
                disabled=(self.user1_page >= user1_total_pages - 1 or self.battle_started),
                custom_id="user1_next",
                row=2
            )
            next1_button.callback = self.user1_next_page
            self.add_item(next1_button)

        # Add pagination buttons for user 2
        user2_total_pages = (len(self.user2_pokemon) + self.pokemon_per_page - 1) // self.pokemon_per_page
        if user2_total_pages > 1:
            prev2_button = Button(
                label=f"◀ {self.user2.display_name}",
                style=discord.ButtonStyle.secondary,
                disabled=(self.user2_page == 0 or self.battle_started),
                custom_id="user2_prev",
                row=3
            )
            prev2_button.callback = self.user2_previous_page
            self.add_item(prev2_button)

            next2_button = Button(
                label=f"{self.user2.display_name} ▶",
                style=discord.ButtonStyle.secondary,
                disabled=(self.user2_page >= user2_total_pages - 1 or self.battle_started),
                custom_id="user2_next",
                row=3
            )
            next2_button.callback = self.user2_next_page
            self.add_item(next2_button)

        # Add ready button
        ready_button = Button(
            label="Ready to Battle!",
            style=discord.ButtonStyle.green,
            custom_id="battle_ready",
            row=4
        )
        ready_button.callback = self.ready_button_callback
        self.add_item(ready_button)

    async def user1_select_callback(self, interaction: discord.Interaction):
        """User 1 selects their Pokemon"""
        if interaction.user.id != self.user1.id:
            await interaction.response.send_message("This is not your battle!", ephemeral=True)
            return

        catch_id = int(self.user1_select.values[0])
        selected = next((p for p in self.user1_pokemon if p['id'] == catch_id), None)

        if selected:
            # Fetch Pokemon details including types and moves
            async with aiohttp.ClientSession() as session:
                pokemon_data = await fetch_pokemon(session, selected['pokemon_id'])
                if pokemon_data:
                    selected['types'] = pokemon_data['types']

                # Fetch moves
                moves = await fetch_pokemon_moves(session, selected['pokemon_id'])
                selected['moves'] = moves

            self.user1_choice = selected
            self.user1_ready = False
            await self.update_display(interaction)

    async def user2_select_callback(self, interaction: discord.Interaction):
        """User 2 selects their Pokemon"""
        if interaction.user.id != self.user2.id:
            await interaction.response.send_message("This is not your battle!", ephemeral=True)
            return

        catch_id = int(self.user2_select.values[0])
        selected = next((p for p in self.user2_pokemon if p['id'] == catch_id), None)

        if selected:
            # Fetch Pokemon details including types and moves
            async with aiohttp.ClientSession() as session:
                pokemon_data = await fetch_pokemon(session, selected['pokemon_id'])
                if pokemon_data:
                    selected['types'] = pokemon_data['types']

                # Fetch moves
                moves = await fetch_pokemon_moves(session, selected['pokemon_id'])
                selected['moves'] = moves

            self.user2_choice = selected
            self.user2_ready = False
            await self.update_display(interaction)

    async def user1_previous_page(self, interaction: discord.Interaction):
        """User 1 goes to previous page"""
        if interaction.user.id != self.user1.id:
            await interaction.response.send_message("You can only change your own pages!", ephemeral=True)
            return

        if self.battle_started:
            await interaction.response.send_message("❌ Battle has already started!", ephemeral=True)
            return

        self.user1_page = max(0, self.user1_page - 1)
        self.update_pokemon_selects()
        await self.update_display(interaction)

    async def user1_next_page(self, interaction: discord.Interaction):
        """User 1 goes to next page"""
        if interaction.user.id != self.user1.id:
            await interaction.response.send_message("You can only change your own pages!", ephemeral=True)
            return

        if self.battle_started:
            await interaction.response.send_message("❌ Battle has already started!", ephemeral=True)
            return

        user1_total_pages = (len(self.user1_pokemon) + self.pokemon_per_page - 1) // self.pokemon_per_page
        self.user1_page = min(user1_total_pages - 1, self.user1_page + 1)
        self.update_pokemon_selects()
        await self.update_display(interaction)

    async def user2_previous_page(self, interaction: discord.Interaction):
        """User 2 goes to previous page"""
        if interaction.user.id != self.user2.id:
            await interaction.response.send_message("You can only change your own pages!", ephemeral=True)
            return

        if self.battle_started:
            await interaction.response.send_message("❌ Battle has already started!", ephemeral=True)
            return

        self.user2_page = max(0, self.user2_page - 1)
        self.update_pokemon_selects()
        await self.update_display(interaction)

    async def user2_next_page(self, interaction: discord.Interaction):
        """User 2 goes to next page"""
        if interaction.user.id != self.user2.id:
            await interaction.response.send_message("You can only change your own pages!", ephemeral=True)
            return

        if self.battle_started:
            await interaction.response.send_message("❌ Battle has already started!", ephemeral=True)
            return

        user2_total_pages = (len(self.user2_pokemon) + self.pokemon_per_page - 1) // self.pokemon_per_page
        self.user2_page = min(user2_total_pages - 1, self.user2_page + 1)
        self.update_pokemon_selects()
        await self.update_display(interaction)

    async def ready_button_callback(self, interaction: discord.Interaction):
        """Ready button callback"""
        return await self.ready_button(interaction, None)

    @discord.ui.button(label="Ready to Battle!", style=discord.ButtonStyle.green, custom_id="battle_ready", row=4)
    async def ready_button(self, interaction: discord.Interaction, button: Button):
        """Mark ready for battle"""
        if interaction.user.id not in [self.user1.id, self.user2.id]:
            await interaction.response.send_message("This is not your battle!", ephemeral=True)
            return

        # Check if user has selected a Pokemon
        if interaction.user.id == self.user1.id:
            if not self.user1_choice:
                await interaction.response.send_message("Please select a Pokemon first!", ephemeral=True)
                return
            self.user1_ready = True
        else:
            if not self.user2_choice:
                await interaction.response.send_message("Please select a Pokemon first!", ephemeral=True)
                return
            self.user2_ready = True

        # Check if both are ready
        if self.user1_ready and self.user2_ready:
            # Defer the interaction immediately to prevent timeout
            await interaction.response.defer()

            # Store channel for posting battle log later
            self.battle_channel = interaction.channel

            # Start battle (this does async DB calls)
            await self.start_battle()

            # Remove the ready button
            self.remove_item(button)

            # Update display (will use edit_original_response since we deferred)
            await self.update_display(interaction)
        else:
            # Not both ready yet, just update normally
            await self.update_display(interaction)

    @discord.ui.button(label="Forfeit", style=discord.ButtonStyle.red, custom_id="battle_forfeit", row=4)
    async def forfeit_button(self, interaction: discord.Interaction, button: Button):
        """Forfeit the battle"""
        if interaction.user.id not in [self.user1.id, self.user2.id]:
            await interaction.response.send_message("This is not your battle!", ephemeral=True)
            return

        # Store channel for posting battle log
        self.battle_channel = interaction.channel

        self.battle_started = True
        self.battle_log = [f"❌ **{interaction.user.display_name} forfeited the battle!**"]

        if interaction.user.id == self.user1.id:
            self.winner = 2
        else:
            self.winner = 1

        # Disable all controls
        for item in self.children:
            item.disabled = True

        await self.update_display(interaction)


# Interactive Trade View
class TradeView(View):
    def __init__(self, user1: discord.Member, user2: discord.Member, guild_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user1 = user1
        self.user2 = user2
        self.guild_id = guild_id
        self.user1_pokemon = []
        self.user2_pokemon = []
        self.user1_offer = None  # {catch_id, pokemon_name, pokemon_id}
        self.user2_offer = None
        self.user1_accepted = False
        self.user2_accepted = False
        self.trade_completed = False
        self.trade_cancelled = False

    async def load_pokemon(self):
        """Load Pokemon for both users"""
        self.user1_pokemon = await db.get_user_pokemon_for_trade(self.user1.id, self.guild_id)
        self.user2_pokemon = await db.get_user_pokemon_for_trade(self.user2.id, self.guild_id)

    def create_embed(self):
        """Create the trade embed"""
        embed = discord.Embed(
            title="🔄 Pokemon Trade",
            description=f"**{self.user1.display_name}** ↔️ **{self.user2.display_name}**",
            color=discord.Color.blue()
        )

        # User 1's offer
        user1_offer_text = "Nothing selected"
        if self.user1_offer:
            user1_offer_text = f"#{self.user1_offer['pokemon_id']:03d} {self.user1_offer['pokemon_name']}"
            if self.user1_accepted:
                user1_offer_text += " ✅"

        embed.add_field(
            name=f"{self.user1.display_name}'s Offer",
            value=user1_offer_text,
            inline=True
        )

        # User 2's offer
        user2_offer_text = "Nothing selected"
        if self.user2_offer:
            user2_offer_text = f"#{self.user2_offer['pokemon_id']:03d} {self.user2_offer['pokemon_name']}"
            if self.user2_accepted:
                user2_offer_text += " ✅"

        embed.add_field(
            name=f"{self.user2.display_name}'s Offer",
            value=user2_offer_text,
            inline=True
        )

        # Status
        if self.trade_completed:
            embed.add_field(
                name="Status",
                value="✅ Trade completed successfully!",
                inline=False
            )
        elif self.trade_cancelled:
            embed.add_field(
                name="Status",
                value="❌ Trade cancelled",
                inline=False
            )
        else:
            status_parts = []
            if self.user1_accepted:
                status_parts.append(f"✅ {self.user1.display_name} accepted")
            if self.user2_accepted:
                status_parts.append(f"✅ {self.user2.display_name} accepted")

            if status_parts:
                embed.add_field(
                    name="Status",
                    value="\n".join(status_parts),
                    inline=False
                )
            else:
                embed.add_field(
                    name="Status",
                    value="⏳ Waiting for both users to select Pokemon and accept",
                    inline=False
                )

        embed.set_footer(text="Both users must select a Pokemon and click Accept to complete the trade")

        return embed

    async def update_display(self, interaction: discord.Interaction):
        """Update the display"""
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.select(placeholder=f"Select your Pokemon to offer...", custom_id="user1_select", min_values=1, max_values=1)
    async def user1_select(self, interaction: discord.Interaction, select: Select):
        """User 1 selects their Pokemon"""
        if interaction.user.id != self.user1.id:
            await interaction.response.send_message("This is not your trade!", ephemeral=True)
            return

        # Find selected Pokemon
        catch_id = int(select.values[0])
        selected = next((p for p in self.user1_pokemon if p['id'] == catch_id), None)

        if selected:
            self.user1_offer = selected
            self.user1_accepted = False  # Reset acceptance when changing offer
            await self.update_display(interaction)

    @discord.ui.select(placeholder=f"Select your Pokemon to offer...", custom_id="user2_select", min_values=1, max_values=1)
    async def user2_select(self, interaction: discord.Interaction, select: Select):
        """User 2 selects their Pokemon"""
        if interaction.user.id != self.user2.id:
            await interaction.response.send_message("This is not your trade!", ephemeral=True)
            return

        # Find selected Pokemon
        catch_id = int(select.values[0])
        selected = next((p for p in self.user2_pokemon if p['id'] == catch_id), None)

        if selected:
            self.user2_offer = selected
            self.user2_accepted = False  # Reset acceptance when changing offer
            await self.update_display(interaction)

    @discord.ui.button(label="Accept Trade", style=discord.ButtonStyle.green, custom_id="accept")
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        """Accept the trade"""
        if interaction.user.id not in [self.user1.id, self.user2.id]:
            await interaction.response.send_message("This is not your trade!", ephemeral=True)
            return

        # Check if user has selected a Pokemon
        if interaction.user.id == self.user1.id:
            if not self.user1_offer:
                await interaction.response.send_message("Please select a Pokemon to offer first!", ephemeral=True)
                return
            self.user1_accepted = True
        else:
            if not self.user2_offer:
                await interaction.response.send_message("Please select a Pokemon to offer first!", ephemeral=True)
                return
            self.user2_accepted = True

        # Check if both accepted
        if self.user1_accepted and self.user2_accepted:
            # Execute trade
            success = await db.execute_trade(
                self.user1_offer['id'],
                self.user2_offer['id'],
                self.user1.id,
                self.user2.id,
                self.guild_id
            )

            if success:
                self.trade_completed = True
                # Update quest progress for both users (complete_trade)
                user1_trade_quest = await db.update_quest_progress(self.user1.id, self.guild_id, 'complete_trade')
                user2_trade_quest = await db.update_quest_progress(self.user2.id, self.guild_id, 'complete_trade')

                # Send quest completion notifications
                if user1_trade_quest and user1_trade_quest.get('completed_quests'):
                    quest_currency = user1_trade_quest.get('total_currency', 0)
                    quest_count = len(user1_trade_quest['completed_quests'])
                    quest_embed = discord.Embed(
                        title="✅ Daily Quest Complete!",
                        description=f"{self.user1.mention} completed {quest_count} quest(s) and earned **₽{quest_currency}**!",
                        color=discord.Color.green()
                    )
                    await interaction.channel.send(embed=quest_embed)

                if user2_trade_quest and user2_trade_quest.get('completed_quests'):
                    quest_currency = user2_trade_quest.get('total_currency', 0)
                    quest_count = len(user2_trade_quest['completed_quests'])
                    quest_embed = discord.Embed(
                        title="✅ Daily Quest Complete!",
                        description=f"{self.user2.mention} completed {quest_count} quest(s) and earned **₽{quest_currency}**!",
                        color=discord.Color.green()
                    )
                    await interaction.channel.send(embed=quest_embed)

                # Disable all buttons
                for item in self.children:
                    item.disabled = True
            else:
                await interaction.response.send_message("❌ Trade failed! Please try again.", ephemeral=True)
                return

        await self.update_display(interaction)

    @discord.ui.button(label="Cancel Trade", style=discord.ButtonStyle.red, custom_id="cancel")
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        """Cancel the trade"""
        if interaction.user.id not in [self.user1.id, self.user2.id]:
            await interaction.response.send_message("This is not your trade!", ephemeral=True)
            return

        self.trade_cancelled = True
        # Disable all buttons
        for item in self.children:
            item.disabled = True

        await self.update_display(interaction)


# Interactive Leaderboard View
class LeaderboardView(View):
    def __init__(self, guild: discord.Guild):
        super().__init__(timeout=300)  # 5 minute timeout
        self.guild = guild
        self.sort_by = 'most_caught'
        self.leaderboard_data = []

        # Add dropdown for sorting
        self.sort_select = Select(
            placeholder="Choose leaderboard type...",
            options=[
                discord.SelectOption(label="🏆 Most Pokemon Caught", value="most_caught", description="Total catches", default=True),
                discord.SelectOption(label="📚 Most Unique Pokemon", value="unique", description="Unique species"),
                discord.SelectOption(label="👑 Most Legendaries", value="legendaries", description="Legendary Pokemon"),
                discord.SelectOption(label="💰 Collection Value", value="collection_value", description="Total Pokedollar value"),
            ]
        )
        self.sort_select.callback = self.sort_callback
        self.add_item(self.sort_select)

    async def sort_callback(self, interaction: discord.Interaction):
        """Handle sort selection"""
        self.sort_by = self.sort_select.values[0]

        # Update dropdown to show selected option
        for option in self.sort_select.options:
            option.default = (option.value == self.sort_by)

        await self.update_display(interaction)

    async def load_leaderboard(self):
        """Load leaderboard based on current sort"""
        if self.sort_by == 'most_caught':
            self.leaderboard_data = await db.get_leaderboard_most_caught(self.guild.id, limit=10)
        elif self.sort_by == 'unique':
            self.leaderboard_data = await db.get_leaderboard_unique(self.guild.id, limit=10)
        elif self.sort_by == 'legendaries':
            self.leaderboard_data = await db.get_leaderboard_legendaries(self.guild.id, limit=10)
        elif self.sort_by == 'collection_value':
            self.leaderboard_data = await db.get_leaderboard_collection_value(self.guild.id, limit=10)

    async def create_embed(self):
        """Create the leaderboard embed"""
        # Get sort display name
        sort_names = {
            'most_caught': '🏆 Most Pokemon Caught',
            'unique': '📚 Most Unique Pokemon',
            'legendaries': '👑 Most Legendaries',
            'collection_value': '💰 Collection Value'
        }
        sort_display = sort_names.get(self.sort_by, 'Leaderboard')

        embed = discord.Embed(
            title=f"{self.guild.name} Leaderboard",
            description=f"**{sort_display}**",
            color=discord.Color.gold()
        )

        # Get rarest Pokemon showcase
        rarest_data = await db.get_user_with_rarest(self.guild.id)
        if rarest_data:
            try:
                rarest_user = await self.guild.fetch_member(rarest_data['user_id'])
                rarest_name = rarest_user.display_name if rarest_user else f"User {rarest_data['user_id']}"

                embed.add_field(
                    name="⭐ Rarest Pokemon in Server",
                    value=f"**{rarest_name}** owns #{rarest_data['pokemon_id']:03d} **{rarest_data['pokemon_name']}**\n"
                          f"Only caught **{rarest_data['total_caught']}** times by **{rarest_data['unique_owners']}** trainer(s)!",
                    inline=False
                )
            except:
                pass  # Skip if we can't fetch the user

        # Create ranked list
        if self.leaderboard_data:
            leaderboard_text = []
            for idx, entry in enumerate(self.leaderboard_data, start=1):
                try:
                    user = await self.guild.fetch_member(entry['user_id'])
                    username = user.display_name if user else f"User {entry['user_id']}"

                    # Determine medal
                    if idx == 1:
                        medal = "🥇"
                    elif idx == 2:
                        medal = "🥈"
                    elif idx == 3:
                        medal = "🥉"
                    else:
                        medal = f"`#{idx:2d}`"

                    # Determine value to display
                    if self.sort_by == 'most_caught':
                        value = f"{entry['total_caught']} caught"
                    elif self.sort_by == 'unique':
                        value = f"{entry['unique_pokemon']}/151 unique"
                    elif self.sort_by == 'legendaries':
                        value = f"{entry['legendary_count']} legendaries"
                    elif self.sort_by == 'collection_value':
                        value = f"₽{entry['collection_value']:,}"

                    leaderboard_text.append(f"{medal} **{username}** - {value}")
                except:
                    continue  # Skip users we can't fetch

            if leaderboard_text:
                embed.add_field(
                    name=f"📊 Top {len(leaderboard_text)} Trainers",
                    value='\n'.join(leaderboard_text),
                    inline=False
                )
        else:
            embed.add_field(
                name="📊 Leaderboard",
                value="No data available yet. Start catching Pokemon!",
                inline=False
            )

        embed.set_footer(text=f"Server: {self.guild.name}")

        return embed

    async def update_display(self, interaction: discord.Interaction):
        """Update the display with new data"""
        await self.load_leaderboard()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)


# Interactive Pokedex View
class PokedexView(View):
    def __init__(self, user_id: int, guild_id: int, username: str):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user_id = user_id
        self.guild_id = guild_id
        self.username = username
        self.current_page = 0
        self.sort_by = 'most_caught'
        self.pokemon_list = []
        self.per_page = 10

        # Add dropdown for sorting
        self.sort_select = Select(
            placeholder="Choose sorting method...",
            options=[
                discord.SelectOption(label="🔢 Most Caught", value="most_caught", description="Sort by catch count", default=True),
                discord.SelectOption(label="🔤 Alphabetical", value="alphabetical", description="Sort A-Z"),
                discord.SelectOption(label="📋 Pokedex Number", value="pokedex_number", description="Sort by Pokedex #"),
                discord.SelectOption(label="📈 Highest Level", value="highest_level", description="Sort by highest level"),
                discord.SelectOption(label="⭐ Rarest (Caught Once)", value="rarest", description="Pokemon caught only once"),
                discord.SelectOption(label="👑 Legendaries Only", value="legendaries", description="Legendary Pokemon"),
                discord.SelectOption(label="✨ Shinies Only", value="shinies", description="Shiny Pokemon"),
                discord.SelectOption(label="📅 Recently Caught", value="recently_caught", description="Last unique catches"),
            ]
        )
        self.sort_select.callback = self.sort_callback
        self.add_item(self.sort_select)

    async def sort_callback(self, interaction: discord.Interaction):
        """Handle sort selection"""
        self.sort_by = self.sort_select.values[0]
        self.current_page = 0  # Reset to first page

        # Update dropdown to show selected option
        for option in self.sort_select.options:
            option.default = (option.value == self.sort_by)

        await self.update_display(interaction)

    async def load_pokemon(self):
        """Load Pokemon based on current sort"""
        if self.sort_by == 'legendaries':
            self.pokemon_list = await db.get_legendary_pokemon(self.user_id, self.guild_id)
        elif self.sort_by == 'shinies':
            self.pokemon_list = await db.get_shiny_pokemon(self.user_id, self.guild_id)
        else:
            self.pokemon_list = await db.get_pokemon_with_counts(self.user_id, self.guild_id, self.sort_by)

        # Fetch levels in batch for better performance
        if self.pokemon_list:
            pokemon_ids = [p['pokemon_id'] for p in self.pokemon_list]
            level_dict = await db.get_multiple_species_levels(self.user_id, self.guild_id, pokemon_ids)

            # Assign levels to pokemon
            for pokemon in self.pokemon_list:
                pokemon['level'] = level_dict.get(pokemon['pokemon_id'], 1)

            # Sort by highest level if requested
            if self.sort_by == 'highest_level':
                self.pokemon_list.sort(key=lambda p: p['level'], reverse=True)

    def create_embed(self, stats: dict):
        """Create the Pokedex embed"""
        total_pages = max(1, (len(self.pokemon_list) + self.per_page - 1) // self.per_page)

        # Get sort display name
        sort_names = {
            'most_caught': '🔢 Most Caught',
            'alphabetical': '🔤 Alphabetical',
            'pokedex_number': '📋 Pokedex Number',
            'highest_level': '📈 Highest Level',
            'rarest': '⭐ Rarest (x1)',
            'legendaries': '👑 Legendaries',
            'shinies': '✨ Shinies',
            'recently_caught': '📅 Recently Caught'
        }
        sort_display = sort_names.get(self.sort_by, 'Most Caught')

        embed = discord.Embed(
            title=f"{self.username}'s Pokedex",
            description=f"**Total Caught:** {stats['total']}\n**Unique Pokemon:** {stats['unique']}/251 ({stats['unique']/251*100:.1f}%)",
            color=discord.Color.blue()
        )

        # Get Pokemon for current page
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_pokemon = self.pokemon_list[start_idx:end_idx]

        if page_pokemon:
            # Create table header
            header = " #    Name         Gen Lvl Qty  Value\n" + "─" * 40

            # Create table rows
            pokemon_rows = [header]
            for poke in page_pokemon:
                pokedex_num = f"{poke['pokemon_id']:03d}"
                name = poke['pokemon_name'][:12].ljust(12)  # Limit name to 12 chars
                gen = poke_data.get_pokemon_generation(poke['pokemon_id'])
                level = f"{poke.get('level', 1):<3}"
                count = f"x{poke['count']:<2}"
                sell_value = db.calculate_sell_price(poke['pokemon_id'])
                value = f"₽{sell_value}"

                row = f"{pokedex_num}  {name} {gen}   {level} {count}  {value}"
                pokemon_rows.append(row)

            embed.add_field(
                name=f"📊 {sort_display}",
                value=f"```\n" + '\n'.join(pokemon_rows) + "\n```",
                inline=False
            )
        else:
            embed.add_field(
                name=f"📊 {sort_display}",
                value="No Pokemon found with this filter.",
                inline=False
            )

        embed.set_footer(text=f"Page {self.current_page + 1}/{total_pages}")

        return embed

    async def update_display(self, interaction: discord.Interaction):
        """Update the display with new data"""
        await self.load_pokemon()
        stats = await db.get_user_stats(self.user_id, self.guild_id)
        embed = self.create_embed(stats)

        # Update button states
        total_pages = max(1, (len(self.pokemon_list) + self.per_page - 1) // self.per_page)
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= total_pages - 1)

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀️ Prev", style=discord.ButtonStyle.gray)
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        """Previous page button"""
        if self.current_page > 0:
            self.current_page -= 1
        await self.update_display(interaction)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.gray)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        """Next page button"""
        total_pages = max(1, (len(self.pokemon_list) + self.per_page - 1) // self.per_page)
        if self.current_page < total_pages - 1:
            self.current_page += 1
        await self.update_display(interaction)


@bot.tree.command(name='pokedex', description='View your Pokedex or another user\'s')
@app_commands.describe(member='The user whose Pokedex you want to view (optional)')
async def pokedex(interaction: discord.Interaction, member: discord.Member = None):
    """View your or another user's caught Pokemon"""
    try:
        # Defer IMMEDIATELY before any checks
        await interaction.response.defer()
    except discord.errors.NotFound:
        # Interaction expired, ignore
        return

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    target = member or interaction.user
    user_id = target.id
    guild_id = interaction.guild.id

    # Get user stats from database
    stats = await db.get_user_stats(user_id, guild_id)

    if stats['total'] == 0:
        await interaction.followup.send(f"{target.display_name} hasn't caught any Pokemon yet!")
        return

    # Create interactive view
    view = PokedexView(user_id, guild_id, target.display_name)
    await view.load_pokemon()
    embed = view.create_embed(stats)

    # Set initial button states
    total_pages = max(1, (len(view.pokemon_list) + view.per_page - 1) // view.per_page)
    view.prev_button.disabled = True  # Start on page 1
    view.next_button.disabled = (total_pages <= 1)

    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name='count', description='See how many of each Pokemon you\'ve caught')
async def count(interaction: discord.Interaction):
    """Show how many of each Pokemon you've caught"""
    # Defer IMMEDIATELY before any checks
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

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


class StatsView(View):
    """View for paginated Pokemon stats selection"""

    def __init__(self, user_id: int, guild_id: int, pokemon_list: list, user: discord.Member):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.guild_id = guild_id
        self.pokemon_list = pokemon_list
        self.user = user
        self.current_page = 0
        self.pokemon_per_page = 25
        self.total_pages = (len(pokemon_list) + self.pokemon_per_page - 1) // self.pokemon_per_page

        # Create initial dropdown
        self.update_dropdown()

    def update_dropdown(self):
        """Update dropdown for current page"""
        self.clear_items()

        # Calculate pagination
        start_idx = self.current_page * self.pokemon_per_page
        end_idx = min(start_idx + self.pokemon_per_page, len(self.pokemon_list))
        page_pokemon = self.pokemon_list[start_idx:end_idx]

        # Create dropdown
        options = []
        for pokemon in page_pokemon:
            is_shiny = pokemon.get('is_shiny', False)
            shiny_indicator = "✨ " if is_shiny else ""
            label = f"Lv.{pokemon['level']} | #{pokemon['pokemon_id']:03d} {shiny_indicator}{pokemon['pokemon_name']}"
            options.append(discord.SelectOption(
                label=label,
                value=str(pokemon['pokemon_id']),
                emoji="✨" if is_shiny else "📊"
            ))

        pokemon_select = Select(
            placeholder="Select a Pokemon to view stats...",
            options=options,
            custom_id="stats_select"
        )
        pokemon_select.callback = self.pokemon_selected
        self.add_item(pokemon_select)

        # Add pagination buttons if needed
        if self.total_pages > 1:
            prev_button = Button(
                label="◀ Previous",
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page == 0),
                custom_id="prev_page",
                row=1
            )
            prev_button.callback = self.previous_page
            self.add_item(prev_button)

            next_button = Button(
                label="Next ▶",
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page >= self.total_pages - 1),
                custom_id="next_page",
                row=1
            )
            next_button.callback = self.next_page
            self.add_item(next_button)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your stats menu!", ephemeral=True)
            return

        self.current_page = max(0, self.current_page - 1)
        self.update_dropdown()

        embed = discord.Embed(
            title="📊 Pokemon Stats",
            description="Select a Pokemon to view its detailed stats, level, and battle record!",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • {len(self.pokemon_list)} unique Pokemon")

        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your stats menu!", ephemeral=True)
            return

        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.update_dropdown()

        embed = discord.Embed(
            title="📊 Pokemon Stats",
            description="Select a Pokemon to view its detailed stats, level, and battle record!",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • {len(self.pokemon_list)} unique Pokemon")

        await interaction.response.edit_message(embed=embed, view=self)

    async def pokemon_selected(self, interaction: discord.Interaction):
        """Handle Pokemon selection"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your stats menu!", ephemeral=True)
            return

        selected_pokemon_id = int(interaction.data['values'][0])

        # Check if this Pokemon is shiny (from the pokemon_list)
        selected_pokemon = next((p for p in self.pokemon_list if p['pokemon_id'] == selected_pokemon_id), None)
        is_shiny = selected_pokemon.get('is_shiny', False) if selected_pokemon else False

        # Get detailed stats from database
        species_stats = await db.get_pokemon_species_stats(self.user_id, self.guild_id, selected_pokemon_id)

        if not species_stats:
            # Pokemon not in species_stats table yet (no battles)
            species_stats = {
                'pokemon_id': selected_pokemon_id,
                'pokemon_name': next((p['pokemon_name'] for p in self.pokemon_list if p['pokemon_id'] == selected_pokemon_id), 'Unknown'),
                'level': 1,
                'experience': 0,
                'battles_won': 0,
                'battles_lost': 0
            }

        # Get Pokemon data
        pokemon_name = species_stats['pokemon_name']
        pokemon_id = species_stats['pokemon_id']
        level = species_stats['level']
        experience = species_stats['experience']
        battles_won = species_stats['battles_won']
        battles_lost = species_stats['battles_lost']

        # Calculate stats
        base_stats = poke_data.get_pokemon_stats(pokemon_id)
        battle_stats = pkmn.calculate_battle_stats(base_stats, level)
        types = poke_data.get_pokemon_types(pokemon_id)
        sprite = poke_data.get_pokemon_sprite(pokemon_id, shiny=is_shiny)

        # Calculate XP progress
        current_level_xp = experience % 100
        xp_needed = 100
        xp_progress = f"{current_level_xp}/{xp_needed}"

        # Calculate win rate
        total_battles = battles_won + battles_lost
        win_rate = (battles_won / total_battles * 100) if total_battles > 0 else 0

        # Create embed with shiny indicator
        shiny_indicator = "✨ " if is_shiny else ""
        shiny_note = "\n✨ **This is a Shiny Pokemon!** ✨" if is_shiny else ""
        embed = discord.Embed(
            title=f"#{pokemon_id:03d} {shiny_indicator}{pokemon_name.title()}",
            description=f"**Level {level}** | {' / '.join([t.title() for t in types])}{shiny_note}",
            color=discord.Color.purple() if is_shiny else discord.Color.blue()
        )

        if sprite:
            embed.set_thumbnail(url=sprite)

        # XP and Level Progress
        embed.add_field(
            name="📈 Experience",
            value=f"**Total XP:** {experience}\n**Progress:** {xp_progress} XP to next level",
            inline=True
        )

        # Battle Record
        embed.add_field(
            name="⚔️ Battle Record",
            value=f"**Wins:** {battles_won}\n**Losses:** {battles_lost}\n**Win Rate:** {win_rate:.1f}%",
            inline=True
        )

        # Blank field for spacing
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Battle Stats
        stats_text = (
            f"**HP:** {battle_stats['hp']}\n"
            f"**Attack:** {battle_stats['attack']}\n"
            f"**Defense:** {battle_stats['defense']}\n"
            f"**Sp. Atk:** {battle_stats.get('special-attack', battle_stats.get('special_attack', 0))}\n"
            f"**Sp. Def:** {battle_stats.get('special-defense', battle_stats.get('special_defense', 0))}\n"
            f"**Speed:** {battle_stats['speed']}"
        )
        embed.add_field(
            name="💪 Battle Stats",
            value=stats_text,
            inline=True
        )

        # Base Stats
        base_stats_text = (
            f"**HP:** {base_stats['hp']}\n"
            f"**Attack:** {base_stats['attack']}\n"
            f"**Defense:** {base_stats['defense']}\n"
            f"**Sp. Atk:** {base_stats.get('special-attack', base_stats.get('special_attack', 0))}\n"
            f"**Sp. Def:** {base_stats.get('special-defense', base_stats.get('special_defense', 0))}\n"
            f"**Speed:** {base_stats['speed']}"
        )
        embed.add_field(
            name="📊 Base Stats",
            value=base_stats_text,
            inline=True
        )

        embed.set_footer(text=f"Requested by {self.user.display_name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name='stats', description='View detailed stats for one of your Pokemon')
async def stats(interaction: discord.Interaction):
    """View detailed stats for a specific Pokemon"""
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    user_id = interaction.user.id
    guild_id = interaction.guild.id

    # Get user's Pokemon
    user_pokemon = await db.get_user_pokemon_for_trade(user_id, guild_id)

    if not user_pokemon:
        await interaction.followup.send("You don't have any Pokemon yet! Catch some Pokemon first using `/catch`!", ephemeral=True)
        return

    # Get unique Pokemon species (no duplicates in the dropdown)
    seen_ids = set()
    unique_pokemon = []
    for pokemon in user_pokemon:
        if pokemon['pokemon_id'] not in seen_ids:
            seen_ids.add(pokemon['pokemon_id'])
            unique_pokemon.append(pokemon)

    # Get levels for all unique Pokemon
    pokemon_ids = [p['pokemon_id'] for p in unique_pokemon]
    level_dict = await db.get_multiple_species_levels(user_id, guild_id, pokemon_ids)

    # Add levels and sort alphabetically by name
    pokemon_with_levels = [{**p, 'level': level_dict.get(p['pokemon_id'], 1)} for p in unique_pokemon]
    pokemon_with_levels.sort(key=lambda p: p['pokemon_name'].lower())

    # Create stats view with pagination
    stats_view = StatsView(user_id, guild_id, pokemon_with_levels, interaction.user)

    embed = discord.Embed(
        title="📊 Pokemon Stats",
        description="Select a Pokemon to view its detailed stats, level, and battle record!",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Page 1/{stats_view.total_pages} • {len(pokemon_with_levels)} unique Pokemon")

    await interaction.followup.send(embed=embed, view=stats_view)


# Battlepass command removed - progression merged with quest system
# Legacy battlepass data is preserved in the database for historical records


@bot.tree.command(name='pack', description='Open a Pokemon pack from your inventory')
async def pack(interaction: discord.Interaction):
    """Open a Pokemon pack"""
    # Defer IMMEDIATELY before any checks to prevent timeout
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    user_id = interaction.user.id
    guild_id = interaction.guild.id

    # Get user's packs
    user_packs = await db.get_user_packs(user_id, guild_id)

    if not user_packs:
        embed = discord.Embed(
            title="No Packs Available",
            description="You don't have any packs to open!",
            color=discord.Color.red()
        )
        embed.add_field(
            name="💰 Buy Packs",
            value="Use `/shop` to buy packs with Pokedollars",
            inline=False
        )
        embed.add_field(
            name="🎁 Earn Packs",
            value="- Complete daily quests for currency rewards\n- Defeat gym leaders for free packs\n- Buy packs from the shop with your earnings!",
            inline=False
        )
        await interaction.followup.send(embed=embed)
        return

    # If user has multiple packs, show selection menu
    import json
    if len(user_packs) > 1:
        # Show pack selection view - let user choose which pack to open
        from pack_view import PackSelectionView
        pack_view = PackSelectionView(interaction.user, guild_id, user_packs)
        embed = pack_view.create_inventory_embed()
        await interaction.followup.send(embed=embed, view=pack_view)
        return

    # Only one pack, open it directly
    pack_to_open = user_packs[0]

    # Open the pack
    # Use the pack (removes it from inventory)
    pack_data = await db.use_pack(user_id, guild_id, pack_to_open['id'])

    if not pack_data:
        await interaction.followup.send("Failed to open pack. Please try again!")
        return

    # Parse pack config from the returned pack_data
    try:
        if isinstance(pack_data['pack_config'], str):
            pack_config = json.loads(pack_data['pack_config'])
        elif isinstance(pack_data['pack_config'], dict):
            pack_config = pack_data['pack_config']
        else:
            raise TypeError(f"Unexpected pack_config type: {type(pack_data['pack_config'])}")

        # Validate it's a dict
        if not isinstance(pack_config, dict):
            raise TypeError(f"pack_config is not a dict after parsing: {type(pack_config)}")

    except (json.JSONDecodeError, TypeError, KeyError) as e:
        print(f"[ERROR] Failed to parse pack config: {e}")
        await interaction.followup.send("Error opening pack - invalid pack configuration!")
        return

    # Determine pack size based on config
    min_poke = pack_config.get('min_pokemon', 3)
    max_poke = pack_config.get('max_pokemon', 5)
    mega_chance = pack_config.get('mega_pack_chance', 0)
    mega_size = pack_config.get('mega_pack_size', 0)

    # Check for mega pack
    is_mega_pack = False
    if mega_chance > 0 and random.random() < mega_chance:
        pack_size = mega_size
        is_mega_pack = True
    else:
        pack_size = random.randint(min_poke, max_poke)

    # Generate Pokemon
    pokemon_list = []
    shiny_caught = False
    legendary_caught = 0
    # Gen 1: Articuno, Zapdos, Moltres, Mewtwo, Mew
    # Gen 2: Raikou, Entei, Suicune, Lugia, Ho-Oh, Celebi
    legendary_ids = [144, 145, 146, 150, 151, 243, 244, 245, 249, 250, 251]

    async with aiohttp.ClientSession() as session:
        for _ in range(pack_size):
            # Force legendary if needed
            force_legendary = False
            if pack_config.get('guaranteed_rare') and legendary_caught < pack_config.get('guaranteed_rare_count', 1):
                if random.random() < pack_config['legendary_chance'] * 2:  # Boost chance for guaranteed
                    force_legendary = True

            if force_legendary:
                pokemon_id = random.choice(legendary_ids)
                pokemon = await fetch_pokemon(session, pokemon_id)
            else:
                pokemon = await fetch_pokemon(session)

            if pokemon:
                # Shiny chance
                is_shiny = random.random() < pack_config['shiny_chance']
                if is_shiny:
                    pokemon['is_shiny'] = True
                    shiny_caught = True
                else:
                    pokemon['is_shiny'] = False

                if pokemon['id'] in legendary_ids:
                    legendary_caught += 1

                pokemon_list.append(pokemon)
                # Add to user's collection
                await db.add_catch(
                    user_id=user_id,
                    guild_id=guild_id,
                    pokemon_name=pokemon['name'],
                    pokemon_id=pokemon['id'],
                    pokemon_types=pokemon['types'],
                    is_shiny=is_shiny
                )

        # Handle Master Collection guarantee
        if pack_config.get('guaranteed_shiny_or_legendaries'):
            min_legendaries = pack_config.get('guaranteed_legendary_count', 3)
            if not shiny_caught and legendary_caught < min_legendaries:
                # Add more legendaries to meet guarantee
                while legendary_caught < min_legendaries:
                    pokemon_id = random.choice(legendary_ids)
                    pokemon = await fetch_pokemon(session, pokemon_id)
                    if pokemon:
                        pokemon['is_shiny'] = False
                        pokemon_list.append(pokemon)
                        legendary_caught += 1
                        await db.add_catch(
                            user_id=user_id,
                            guild_id=guild_id,
                            pokemon_name=pokemon['name'],
                            pokemon_id=pokemon['id'],
                            pokemon_types=pokemon['types'],
                            is_shiny=False
                        )

    if not pokemon_list:
        await interaction.followup.send("Error opening pack. Please try again!")
        return

    # Update quest progress
    pack_quest_result = await db.update_quest_progress(user_id, guild_id, 'open_packs')

    # Send quest completion notification if needed
    if pack_quest_result and pack_quest_result.get('completed_quests'):
        quest_currency = pack_quest_result.get('total_currency', 0)
        quest_count = len(pack_quest_result['completed_quests'])
        quest_embed = discord.Embed(
            title="✅ Daily Quest Complete!",
            description=f"You completed {quest_count} quest(s) and earned **₽{quest_currency}**!",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=quest_embed)

    # Create pack opening embed
    title = "🎉 MEGA PACK! 🎉" if is_mega_pack else f"📦 {pack_to_open['pack_name']} Opened!"
    if shiny_caught:
        title = "✨ SHINY PACK! ✨"

    # Determine color based on pack type
    colors = {
        'Basic Pack': discord.Color.light_grey(),
        'Booster Pack': discord.Color.green(),
        'Premium Pack': discord.Color.blue(),
        'Elite Trainer Pack': discord.Color.purple(),
        'Master Collection': discord.Color.gold()
    }
    color = colors.get(pack_to_open['pack_name'], discord.Color.gold())
    if shiny_caught:
        color = discord.Color.purple()

    embed = discord.Embed(
        title=title,
        description=f"{interaction.user.display_name} opened a **{pack_to_open['pack_name']}** and got **{len(pokemon_list)}** Pokemon!",
        color=color
    )

    # List all Pokemon
    pokemon_names = []
    for p in pokemon_list:
        shiny_marker = " ✨" if p.get('is_shiny') else ""
        legendary_marker = " 👑" if p['id'] in legendary_ids else ""
        pokemon_names.append(f"#{p['id']:03d} {p['name']}{shiny_marker}{legendary_marker}")

    # Display in columns based on pack size
    if len(pokemon_names) <= 10:
        embed.add_field(name="Pokemon Caught", value='\n'.join(pokemon_names), inline=False)
    else:
        # Split into multiple columns
        mid = len(pokemon_names) // 2
        col1 = '\n'.join(pokemon_names[:mid])
        col2 = '\n'.join(pokemon_names[mid:])
        embed.add_field(name=f"Pokemon (1-{mid})", value=col1, inline=True)
        embed.add_field(name=f"Pokemon ({mid+1}-{len(pokemon_names)})", value=col2, inline=True)

    # Show special pulls
    if shiny_caught or legendary_caught > 0:
        special_text = []
        if shiny_caught:
            special_text.append(f"✨ **SHINY POKEMON!**")
        if legendary_caught > 0:
            special_text.append(f"👑 **{legendary_caught} Legendary Pokemon!**")

        embed.add_field(name="🌟 Special Pulls", value='\n'.join(special_text), inline=False)

    remaining_packs = await db.get_pack_count(user_id, guild_id)
    pack_word = 'pack' if remaining_packs == 1 else 'packs'
    embed.set_footer(text=f"Remaining packs: {remaining_packs} {pack_word}")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name='battle', description='Battle another user with Pokemon!')
@app_commands.describe(user='The user you want to battle')
async def battle(interaction: discord.Interaction, user: discord.Member):
    """Initiate a Pokemon battle with another user"""
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        return

    # Can't battle yourself
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ You can't battle yourself!", ephemeral=True)
        return

    # Can't battle bots
    if user.bot:
        await interaction.response.send_message("❌ You can't battle bots!", ephemeral=True)
        return

    # Defer the response
    await interaction.response.defer()

    # Create battle view
    view = BattleView(interaction.user, user, interaction.guild.id)
    await view.load_pokemon()

    # Check if both users have Pokemon
    if not view.user1_pokemon:
        await interaction.followup.send(f"❌ {interaction.user.display_name} doesn't have any Pokemon to battle with!")
        return

    if not view.user2_pokemon:
        await interaction.followup.send(f"❌ {user.display_name} doesn't have any Pokemon to battle with!")
        return

    # Get levels in batch for both users
    user1_ids = [p['pokemon_id'] for p in view.user1_pokemon]
    user2_ids = [p['pokemon_id'] for p in view.user2_pokemon]

    user1_levels = await db.get_multiple_species_levels(interaction.user.id, interaction.guild.id, user1_ids)
    user2_levels = await db.get_multiple_species_levels(user.id, interaction.guild.id, user2_ids)

    # Add levels and sort
    user1_with_levels = [{**p, 'level': user1_levels.get(p['pokemon_id'], 1)} for p in view.user1_pokemon]
    user1_with_levels.sort(key=lambda p: p['level'], reverse=True)

    user2_with_levels = [{**p, 'level': user2_levels.get(p['pokemon_id'], 1)} for p in view.user2_pokemon]
    user2_with_levels.sort(key=lambda p: p['level'], reverse=True)

    # Update view's pokemon lists with level info
    view.user1_pokemon = user1_with_levels
    view.user2_pokemon = user2_with_levels

    # Update view with pagination
    view.update_pokemon_selects()

    embed = view.create_embed()
    await interaction.followup.send(embed=embed, view=view)


# Simple Trainer Battle Views for /trainer command

class TrainerBattlePokemonSelect(View):
    """View for selecting which Pokemon to use for trainer battle"""

    def __init__(self, user: discord.Member, guild_id: int, pokemon_list: list, battles_remaining: int):
        super().__init__(timeout=180)
        self.user = user
        self.guild_id = guild_id
        self.pokemon_list = pokemon_list  # Already has levels
        self.battles_remaining = battles_remaining

        # Pagination
        self.current_page = 0
        self.pokemon_per_page = 25
        self.total_pages = (len(pokemon_list) + self.pokemon_per_page - 1) // self.pokemon_per_page

        self.update_select()

    def update_select(self):
        """Update the select dropdown for current page"""
        self.clear_items()

        # Calculate page range
        start_idx = self.current_page * self.pokemon_per_page
        end_idx = min(start_idx + self.pokemon_per_page, len(self.pokemon_list))
        page_pokemon = self.pokemon_list[start_idx:end_idx]

        # Create select and store as instance variable
        self.pokemon_select = Select(
            placeholder="Choose your Pokemon...",
            min_values=1,
            max_values=1
        )

        for pokemon in page_pokemon:
            level = pokemon.get('level', 1)
            is_shiny = pokemon.get('is_shiny', False)
            shiny_indicator = "✨ " if is_shiny else ""
            types = poke_data.get_pokemon_types(pokemon['pokemon_id'])
            types_str = '/'.join([t.title() for t in types]) if types else 'Unknown'

            self.pokemon_select.add_option(
                label=f"{shiny_indicator}{pokemon['pokemon_name']} (Lv.{level})",
                value=str(pokemon['pokemon_id']),
                description=f"#{pokemon['pokemon_id']} - {types_str}",
                emoji="✨" if is_shiny else "⚔️"
            )

        self.pokemon_select.callback = self.pokemon_selected
        self.add_item(self.pokemon_select)

        # Add pagination buttons if needed
        if self.total_pages > 1:
            prev_button = Button(
                label="◀ Previous",
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page == 0)
            )
            prev_button.callback = self.previous_page
            self.add_item(prev_button)

            next_button = Button(
                label="Next ▶",
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page >= self.total_pages - 1)
            )
            next_button.callback = self.next_page
            self.add_item(next_button)

    async def previous_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your trainer battle!", ephemeral=True)
            return

        self.current_page = max(0, self.current_page - 1)
        self.update_select()

        # Update embed with new page info
        embed = interaction.message.embeds[0]
        if self.total_pages > 1:
            embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages}")

        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your trainer battle!", ephemeral=True)
            return

        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.update_select()

        # Update embed with new page info
        embed = interaction.message.embeds[0]
        if self.total_pages > 1:
            embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages}")

        await interaction.response.edit_message(embed=embed, view=self)

    async def pokemon_selected(self, interaction: discord.Interaction):
        """Handle Pokemon selection and start battle"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your trainer battle!", ephemeral=True)
            return

        await interaction.response.defer()

        # Get selected Pokemon ID from the select component
        selected_pokemon_id = int(self.pokemon_select.values[0])
        selected_pokemon = next((p for p in self.pokemon_list if p['pokemon_id'] == selected_pokemon_id), None)

        if not selected_pokemon:
            await interaction.followup.send("❌ Pokemon not found!", ephemeral=True)
            return

        # Use a trainer battle
        success = await db.use_trainer_battle(self.user.id, self.guild_id)
        if not success:
            await interaction.followup.send("❌ No battles remaining!", ephemeral=True)
            return

        # Generate opponent trainer Pokemon with similar level (±2)
        user_level = selected_pokemon.get('level', 1)
        min_level = max(1, user_level - 2)
        max_level = user_level + 2
        opponent_level = random.randint(min_level, max_level)

        # Pick a random Pokemon for the trainer
        opponent_pokemon_id = random.randint(1, 251)  # Gen 1 & 2 Pokemon

        # Generate a random trainer with quote
        trainer = trainer_data.get_random_trainer()

        # Create battle view
        battle_view = SimpleTrainerBattleView(
            self.user,
            self.guild_id,
            selected_pokemon,
            opponent_pokemon_id,
            opponent_level,
            self.battles_remaining - 1,
            trainer
        )

        # Disable selection
        self.clear_items()
        await interaction.message.edit(view=self)

        # Start battle
        await battle_view.start_battle(interaction)


class SimpleTrainerBattleView(View):
    """View for simple trainer battles (player vs NPC trainer)"""

    def __init__(self, user: discord.Member, guild_id: int, user_pokemon: dict, opponent_pokemon_id: int, opponent_level: int, battles_remaining: int, trainer: dict = None):
        super().__init__(timeout=600)
        self.user = user
        self.guild_id = guild_id
        self.user_pokemon = user_pokemon
        self.opponent_pokemon_id = opponent_pokemon_id
        self.opponent_level = opponent_level
        self.battles_remaining = battles_remaining
        self.trainer = trainer if trainer else {'name': 'Wild Trainer', 'class': 'Trainer', 'sprite': '⚔️', 'quote': 'Let\'s battle!'}

        # Battle state
        self.turn_count = 0
        self.battle_log = []

        # Will be initialized in start_battle
        self.user_current_hp = 0
        self.user_max_hp = 0
        self.opponent_current_hp = 0
        self.opponent_max_hp = 0

        self.user_stats = None
        self.opponent_stats = None
        self.user_moves = []
        self.opponent_moves = []
        self.opponent_name = ""

    async def start_battle(self, interaction: discord.Interaction):
        """Initialize battle stats and start"""
        # Get user Pokemon stats
        user_level = self.user_pokemon.get('level', 1)
        user_base_stats = poke_data.get_pokemon_stats(self.user_pokemon['pokemon_id'])
        self.user_stats = pkmn.calculate_battle_stats(user_base_stats, user_level)
        self.user_max_hp = self.user_stats['hp']
        self.user_current_hp = self.user_max_hp
        self.user_moves = poke_data.get_pokemon_moves(self.user_pokemon['pokemon_id'], num_moves=4, max_level=user_level)

        # Get opponent Pokemon stats
        self.opponent_name = poke_data.get_pokemon_name(self.opponent_pokemon_id)
        opponent_base_stats = poke_data.get_pokemon_stats(self.opponent_pokemon_id)
        self.opponent_stats = pkmn.calculate_battle_stats(opponent_base_stats, self.opponent_level)
        self.opponent_max_hp = self.opponent_stats['hp']
        self.opponent_current_hp = self.opponent_max_hp
        self.opponent_moves = poke_data.get_pokemon_moves(self.opponent_pokemon_id, num_moves=4, max_level=self.opponent_level)

        # Create move buttons
        self.create_move_buttons()

        # Initial battle log with trainer quote
        trainer_quote = self.trainer.get('quote', "Let's battle!")
        self.battle_log = [
            f"⚔️ **{self.trainer['sprite']} {self.trainer['name']} challenges you!**",
            f"💬 *\"{trainer_quote}\"*"
        ]

        # Send battle embed
        embed = self.create_battle_embed()
        await interaction.followup.send(embed=embed, view=self)

    def create_move_buttons(self):
        """Create move buttons"""
        self.clear_items()

        for i, move in enumerate(self.user_moves):
            if move['damage_class'] == 'status' or move.get('power', 0) == 0:
                button_style = discord.ButtonStyle.secondary
            elif move['damage_class'] == 'physical':
                button_style = discord.ButtonStyle.danger
            else:
                button_style = discord.ButtonStyle.primary

            button = Button(
                label=f"{move['name']} ({move['type']})",
                style=button_style,
                row=i // 2
            )
            button.callback = self.create_move_callback(i)
            self.add_item(button)

    def create_move_callback(self, move_index: int):
        """Create callback for move button"""
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
                return

            await interaction.response.defer()
            await self.execute_turn(move_index, interaction)

        return callback

    async def execute_turn(self, user_move_index: int, interaction: discord.Interaction):
        """Execute a battle turn"""
        self.turn_count += 1
        self.battle_log = [f"**Turn {self.turn_count}:**"]

        user_move = self.user_moves[user_move_index]
        opponent_move = random.choice(self.opponent_moves)

        # Determine turn order by speed
        user_goes_first = self.user_stats['speed'] >= self.opponent_stats['speed']

        # Execute moves
        if user_goes_first:
            await self.user_attacks(user_move)
            if self.opponent_current_hp > 0:
                await self.opponent_attacks(opponent_move)
        else:
            await self.opponent_attacks(opponent_move)
            if self.user_current_hp > 0:
                await self.user_attacks(user_move)

        # Check battle end
        if self.user_current_hp <= 0:
            await self.handle_defeat(interaction)
            return

        if self.opponent_current_hp <= 0:
            await self.handle_victory(interaction)
            return

        # Update battle UI
        self.create_move_buttons()
        embed = self.create_battle_embed()
        await interaction.message.edit(embed=embed, view=self)

    async def user_attacks(self, move: dict):
        """User's Pokemon attacks"""
        damage, is_crit, hit = self.calculate_damage(
            move,
            self.user_pokemon['pokemon_id'],
            self.opponent_pokemon_id,
            self.user_stats,
            self.opponent_stats
        )

        if hit:
            self.opponent_current_hp = max(0, self.opponent_current_hp - damage)
            crit_text = " **Critical hit!**" if is_crit else ""
            self.battle_log.append(f"**{self.user_pokemon['pokemon_name']}** used **{move['name']}**! Dealt {damage} damage!{crit_text}")

            # Check for self-destruct moves
            move_name_lower = move['name'].lower()
            if 'self-destruct' in move_name_lower or 'selfdestruct' in move_name_lower or move_name_lower == 'explosion':
                self.user_current_hp = 0
                self.battle_log.append(f"💥 **{self.user_pokemon['pokemon_name']}** fainted from the recoil!")

            if self.opponent_current_hp <= 0:
                self.battle_log.append(f"**{self.opponent_name}** fainted!")
        else:
            self.battle_log.append(f"**{self.user_pokemon['pokemon_name']}** used **{move['name']}**... but it missed!")

    async def opponent_attacks(self, move: dict):
        """Opponent's Pokemon attacks"""
        damage, is_crit, hit = self.calculate_damage(
            move,
            self.opponent_pokemon_id,
            self.user_pokemon['pokemon_id'],
            self.opponent_stats,
            self.user_stats
        )

        if hit:
            self.user_current_hp = max(0, self.user_current_hp - damage)
            crit_text = " **Critical hit!**" if is_crit else ""
            self.battle_log.append(f"**{self.opponent_name}** used **{move['name']}**! Dealt {damage} damage!{crit_text}")

            # Check for self-destruct moves
            move_name_lower = move['name'].lower()
            if 'self-destruct' in move_name_lower or 'selfdestruct' in move_name_lower or move_name_lower == 'explosion':
                self.opponent_current_hp = 0
                self.battle_log.append(f"💥 **{self.opponent_name}** fainted from the recoil!")

            if self.user_current_hp <= 0:
                self.battle_log.append(f"**{self.user_pokemon['pokemon_name']}** fainted!")
        else:
            self.battle_log.append(f"**{self.opponent_name}** used **{move['name']}**... but it missed!")

    def calculate_damage(self, move: dict, attacker_id: int, defender_id: int, attacker_stats: dict, defender_stats: dict) -> tuple:
        """Calculate damage. Returns (damage, is_crit, hit)"""
        # Check accuracy
        accuracy = move.get('accuracy', 100)
        if random.randint(1, 100) > accuracy:
            return 0, False, False

        # Status moves do no damage
        if move['damage_class'] == 'status' or move.get('power', 0) == 0:
            return 0, False, True

        # Critical hit
        is_crit = random.random() < 0.0625

        # Get attacker and defender types
        attacker_types = poke_data.get_pokemon_types(attacker_id)
        defender_types = poke_data.get_pokemon_types(defender_id)

        # Calculate base damage
        power = move.get('power', 50)
        attacker_level = self.user_pokemon.get('level', 1) if attacker_id == self.user_pokemon['pokemon_id'] else self.opponent_level

        if move['damage_class'] == 'physical':
            attack = attacker_stats['attack']
            defense = defender_stats['defense']
        else:
            attack = attacker_stats.get('special-attack', attacker_stats.get('special_attack', 50))
            defense = defender_stats.get('special-defense', defender_stats.get('special_defense', 50))

        # Damage formula
        damage = ((2 * attacker_level / 5 + 2) * power * attack / defense / 50) + 2

        # Critical hit
        if is_crit:
            damage *= 1.5

        # Random factor
        damage *= random.uniform(0.85, 1.0)

        # Type effectiveness
        move_type = move.get('type', 'normal')
        effectiveness = pkmn.get_type_effectiveness([move_type], defender_types)
        damage *= effectiveness

        # STAB
        if move_type in attacker_types:
            damage *= 1.5

        return int(max(1, damage)), is_crit, True

    def create_battle_embed(self):
        """Create battle embed"""
        embed = discord.Embed(
            title="⚔️ Trainer Battle",
            description=f"**{self.user.display_name}** vs **{self.trainer['sprite']} {self.trainer['name']}**",
            color=discord.Color.orange()
        )

        # User's Pokemon
        user_hp_percent = (self.user_current_hp / self.user_max_hp) * 100
        user_hp_bar = pkmn.create_hp_bar(user_hp_percent)
        user_shiny = "✨ " if self.user_pokemon.get('is_shiny', False) else ""

        embed.add_field(
            name=f"Your {user_shiny}{self.user_pokemon['pokemon_name']} (Lv.{self.user_pokemon.get('level', 1)})",
            value=f"{user_hp_bar}\nHP: {self.user_current_hp}/{self.user_max_hp}",
            inline=True
        )

        # Opponent's Pokemon
        opponent_hp_percent = (self.opponent_current_hp / self.opponent_max_hp) * 100
        opponent_hp_bar = pkmn.create_hp_bar(opponent_hp_percent)

        embed.add_field(
            name=f"{self.trainer['sprite']} {self.opponent_name} (Lv.{self.opponent_level})",
            value=f"{opponent_hp_bar}\nHP: {self.opponent_current_hp}/{self.opponent_max_hp}",
            inline=True
        )

        # Battle log
        log_text = "\n".join(self.battle_log[-5:])
        if log_text:
            embed.add_field(name="📝 Battle Log", value=log_text, inline=False)

        embed.set_footer(text=f"Turn {self.turn_count} • {self.battles_remaining} battles remaining this hour")

        return embed

    async def handle_victory(self, interaction: discord.Interaction):
        """Handle victory"""
        # Award XP
        xp_gained = 50
        xp_result = await db.add_species_xp(
            self.user.id, self.guild_id,
            self.user_pokemon['pokemon_id'], self.user_pokemon['pokemon_name'],
            xp_gained, is_win=True
        )

        # Update quest progress
        quest_result = await db.update_quest_progress(self.user.id, self.guild_id, 'win_trainer_battles')

        # Create victory embed
        embed = discord.Embed(
            title="🎉 Victory!",
            description=f"You defeated **{self.trainer['sprite']} {self.trainer['name']}**!",
            color=discord.Color.green()
        )

        reward_text = f"• **{self.user_pokemon['pokemon_name']}** gained **{xp_gained} XP**!"

        if xp_result and xp_result.get('leveled_up'):
            reward_text += f"\n• **{self.user_pokemon['pokemon_name']}** leveled up to **Lv.{xp_result['new_level']}**!"

        embed.add_field(name="🏆 Rewards", value=reward_text, inline=False)

        # Quest completion notification
        if quest_result and quest_result.get('completed_quests'):
            quest_currency = quest_result.get('total_currency', 0)
            quest_count = len(quest_result['completed_quests'])
            embed.add_field(
                name="✅ Quest Complete!",
                value=f"Completed {quest_count} quest(s) and earned **₽{quest_currency}**!",
                inline=False
            )

        embed.set_footer(text=f"{self.battles_remaining} battles remaining this hour")

        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)

    async def handle_defeat(self, interaction: discord.Interaction):
        """Handle defeat"""
        # Award small XP even for loss
        xp_gained = 10
        await db.add_species_xp(
            self.user.id, self.guild_id,
            self.user_pokemon['pokemon_id'], self.user_pokemon['pokemon_name'],
            xp_gained, is_win=False
        )

        # Create defeat embed
        embed = discord.Embed(
            title="💔 Defeated...",
            description=f"You were defeated by **{self.trainer['sprite']} {self.trainer['name']}**!",
            color=discord.Color.red()
        )

        embed.add_field(
            name="Consolation Prize",
            value=f"**{self.user_pokemon['pokemon_name']}** gained **{xp_gained} XP** for participating!",
            inline=False
        )

        embed.set_footer(text=f"{self.battles_remaining} battles remaining this hour")

        self.clear_items()
        await interaction.message.edit(embed=embed, view=self)


@bot.tree.command(name='trainer', description='Battle a trainer with one of your Pokemon for XP!')
async def trainer(interaction: discord.Interaction):
    """Initiate a trainer battle to gain XP for your Pokemon"""
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        return

    # Check cooldown
    cooldown = await db.check_trainer_cooldown(interaction.user.id, interaction.guild.id)

    if cooldown['battles_remaining'] <= 0:
        # Format time remaining
        seconds = cooldown['seconds_until_reset']
        minutes = seconds // 60
        seconds_remainder = seconds % 60

        time_str = f"{minutes}m {seconds_remainder}s" if minutes > 0 else f"{seconds_remainder}s"

        embed = discord.Embed(
            title="⏰ Trainer Battle Cooldown",
            description=f"You've used all 3 trainer battles this hour!\n\nNext reset in: **{time_str}**",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Defer the response
    await interaction.response.defer()

    # Get user's Pokemon
    user_pokemon = await db.get_user_pokemon_for_trade(interaction.user.id, interaction.guild.id)

    if not user_pokemon:
        await interaction.followup.send("❌ You don't have any Pokemon to battle with!")
        return

    # Get unique Pokemon species with their highest catch_id
    seen_species = {}
    for pokemon in user_pokemon:
        species_key = (pokemon['pokemon_id'], pokemon['pokemon_name'])
        if species_key not in seen_species:
            seen_species[species_key] = pokemon

    unique_pokemon = list(seen_species.values())

    # Get levels in batch
    pokemon_ids = [p['pokemon_id'] for p in unique_pokemon]
    levels = await db.get_multiple_species_levels(interaction.user.id, interaction.guild.id, pokemon_ids)

    # Add levels
    pokemon_with_levels = [{**p, 'level': levels.get(p['pokemon_id'], 1)} for p in unique_pokemon]
    pokemon_with_levels.sort(key=lambda p: p['level'], reverse=True)

    # Create view for Pokemon selection
    view = TrainerBattlePokemonSelect(interaction.user, interaction.guild.id, pokemon_with_levels, cooldown['battles_remaining'])

    embed = discord.Embed(
        title="⚔️ Trainer Battle",
        description=f"Select a Pokemon to battle against a trainer!\n\nThe trainer will use a Pokemon with a similar level to yours (±2 levels).\n\n**Battles Remaining:** {cooldown['battles_remaining']}/3",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="Rewards",
        value="🏆 Win: **50 XP**\n💫 Lose: **10 XP**",
        inline=False
    )

    # Add page info if there are multiple pages
    if view.total_pages > 1:
        embed.set_footer(text=f"Page 1/{view.total_pages}")

    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name='badges', description='View your gym badge collection!')
@app_commands.describe(region='Choose which region to view (optional - shows both if not specified)')
@app_commands.choices(region=[
    app_commands.Choice(name='Kanto (Gen 1)', value='kanto'),
    app_commands.Choice(name='Johto (Gen 2)', value='johto'),
    app_commands.Choice(name='Both Regions', value='both'),
])
async def badges(interaction: discord.Interaction, region: str = 'both'):
    """Display user's gym badge collection"""
    # Defer immediately to prevent timeout
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    # Get user's badges
    user_badges = await db.get_user_badges(interaction.user.id, interaction.guild.id)

    # Count badges by region
    kanto_gym_list = gym_leaders.get_all_gym_leaders()
    johto_gym_list = gym_leaders.get_all_gym_leaders_johto()
    kanto_badge_count = sum(1 for gym_key, _ in kanto_gym_list if gym_key in user_badges)
    johto_badge_count = sum(1 for gym_key, _ in johto_gym_list if gym_key in user_badges)
    total_badges = kanto_badge_count + johto_badge_count

    # Create embed based on region choice
    if region == 'both':
        embed = discord.Embed(
            title=f"🏆 {interaction.user.display_name}'s Badge Case",
            description=f"**Total Badges: {total_badges}/16**\n**Kanto:** {kanto_badge_count}/8 | **Johto:** {johto_badge_count}/8",
            color=discord.Color.gold() if total_badges == 16 else discord.Color.blue()
        )

        # Add Kanto badges
        kanto_badges = []
        for gym_key, gym_data in kanto_gym_list:
            has_badge = gym_key in user_badges
            status = f"✅ {gym_data['badge_emoji']} **{gym_data['badge']}**" if has_badge else f"⭕ {gym_data['badge_emoji']} ~~{gym_data['badge']}~~"
            kanto_badges.append(status)

        embed.add_field(
            name="🗾 Kanto Region",
            value="\n".join(kanto_badges),
            inline=True
        )

        # Add Johto badges
        johto_badges = []
        for gym_key, gym_data in johto_gym_list:
            has_badge = gym_key in user_badges
            status = f"✅ {gym_data['badge_emoji']} **{gym_data['badge']}**" if has_badge else f"⭕ {gym_data['badge_emoji']} ~~{gym_data['badge']}~~"
            johto_badges.append(status)

        embed.add_field(
            name="🌸 Johto Region",
            value="\n".join(johto_badges),
            inline=True
        )

        if total_badges == 16:
            embed.set_footer(text="🎉 All badges collected! You are a Pokemon Master!")
        else:
            embed.set_footer(text=f"Use /gym to challenge gym leaders! ({16 - total_badges} remaining)")

    elif region == 'kanto':
        embed = discord.Embed(
            title=f"🗾 {interaction.user.display_name}'s Kanto Badges",
            description=f"**Badges Collected: {kanto_badge_count}/8**",
            color=discord.Color.gold() if kanto_badge_count == 8 else discord.Color.blue()
        )

        kanto_badges = []
        for gym_key, gym_data in kanto_gym_list:
            has_badge = gym_key in user_badges
            if has_badge:
                status = f"✅ {gym_data['badge_emoji']} **{gym_data['badge']}** - {gym_data['name']}"
            else:
                status = f"⭕ {gym_data['badge_emoji']} ~~{gym_data['badge']}~~ - {gym_data['name']}"
            kanto_badges.append(status)

        embed.add_field(
            name="Kanto Gym Badges",
            value="\n".join(kanto_badges),
            inline=False
        )

        if kanto_badge_count == 8:
            embed.set_footer(text="🎉 All Kanto badges collected!")
        else:
            embed.set_footer(text=f"Use /gym region:kanto to challenge Kanto leaders! ({8 - kanto_badge_count} remaining)")

    else:  # johto
        embed = discord.Embed(
            title=f"🌸 {interaction.user.display_name}'s Johto Badges",
            description=f"**Badges Collected: {johto_badge_count}/8**",
            color=discord.Color.gold() if johto_badge_count == 8 else discord.Color.blue()
        )

        johto_badges = []
        for gym_key, gym_data in johto_gym_list:
            has_badge = gym_key in user_badges
            if has_badge:
                status = f"✅ {gym_data['badge_emoji']} **{gym_data['badge']}** - {gym_data['name']}"
            else:
                status = f"⭕ {gym_data['badge_emoji']} ~~{gym_data['badge']}~~ - {gym_data['name']}"
            johto_badges.append(status)

        embed.add_field(
            name="Johto Gym Badges",
            value="\n".join(johto_badges),
            inline=False
        )

        if johto_badge_count == 8:
            embed.set_footer(text="🎉 All Johto badges collected!")
        else:
            embed.set_footer(text=f"Use /gym region:johto to challenge Johto leaders! ({8 - johto_badge_count} remaining)")

    # Set thumbnail (first earned badge or default)
    first_badge = None
    for gym_key, gym_data in kanto_gym_list:
        if gym_key in user_badges:
            first_badge = gym_data['badge_icon']
            break
    if not first_badge:
        for gym_key, gym_data in johto_gym_list:
            if gym_key in user_badges:
                first_badge = gym_data['badge_icon']
                break
    if not first_badge:
        first_badge = gym_leaders.get_gym_leader('brock')['badge_icon']

    embed.set_thumbnail(url=first_badge)

    await interaction.followup.send(embed=embed)


@bot.tree.command(name='shinies', description='View your shiny Pokemon collection!')
async def shinies(interaction: discord.Interaction):
    """Display user's shiny Pokemon collection"""
    # Defer immediately to prevent timeout
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    # Get user's shiny Pokemon
    shiny_pokemon = await db.get_shiny_pokemon(interaction.user.id, interaction.guild.id)
    shiny_count = len(shiny_pokemon)

    # Get total Pokemon count for comparison
    user_stats = await db.get_user_stats(interaction.user.id, interaction.guild.id)
    total_caught = user_stats.get('total', 0)

    # Calculate shiny rate
    shiny_rate = (shiny_count / total_caught * 100) if total_caught > 0 else 0

    # Create embed
    embed = discord.Embed(
        title=f"✨ {interaction.user.display_name}'s Shiny Collection",
        description=f"**Shinies Caught: {shiny_count}**\n**Total Pokemon: {total_caught}**\n**Shiny Rate: {shiny_rate:.2f}%**\n\n*Shiny Pokemon are extremely rare with only a 0.2% spawn chance!*",
        color=discord.Color.purple()
    )

    if shiny_count == 0:
        embed.add_field(
            name="🔍 No Shinies Yet",
            value="Keep catching Pokemon! Shinies have a 1/512 (0.2%) chance of appearing.\n\nYou'll know it's shiny when you see the ✨ sparkles and purple embed!",
            inline=False
        )
    else:
        # Display shiny Pokemon list
        shiny_list = []
        for poke in shiny_pokemon:
            count_text = f"x{poke['count']}" if poke['count'] > 1 else ""
            shiny_list.append(f"✨ **#{poke['pokemon_id']} {poke['pokemon_name'].title()}** {count_text}")

        # Split into columns if more than 10
        if len(shiny_list) <= 10:
            embed.add_field(
                name="Shiny Pokemon",
                value="\n".join(shiny_list),
                inline=False
            )
        else:
            # Split into two columns
            half = (len(shiny_list) + 1) // 2
            embed.add_field(
                name="Shiny Pokemon (Part 1)",
                value="\n".join(shiny_list[:half]),
                inline=True
            )
            embed.add_field(
                name="Shiny Pokemon (Part 2)",
                value="\n".join(shiny_list[half:]),
                inline=True
            )

        # Show the first shiny as thumbnail
        if shiny_pokemon:
            first_shiny_sprite = poke_data.get_pokemon_sprite(shiny_pokemon[0]['pokemon_id'], shiny=True)
            if first_shiny_sprite:
                embed.set_thumbnail(url=first_shiny_sprite)

    embed.set_footer(text=f"Odds: 1/512 (0.195%) • Keep hunting for that sparkle! ✨")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name='shinyleaderboard', description='View the server shiny Pokemon leaderboard!')
async def shinyleaderboard(interaction: discord.Interaction):
    """Display server-wide shiny Pokemon leaderboard"""
    # Defer immediately to prevent timeout
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    # Get top 10 shiny collectors
    leaderboard = await db.get_leaderboard_shinies(interaction.guild.id, limit=10)

    if not leaderboard:
        await interaction.followup.send("No shiny Pokemon have been caught in this server yet! Be the first! ✨", ephemeral=True)
        return

    # Create embed
    embed = discord.Embed(
        title=f"✨ {interaction.guild.name} - Shiny Leaderboard",
        description="**Top 10 Shiny Pokemon Collectors**\n\n*Shiny Pokemon are extremely rare with only a 0.2% spawn chance!*",
        color=discord.Color.purple()
    )

    # Build leaderboard list
    leaderboard_text = []
    for idx, entry in enumerate(leaderboard, start=1):
        user = await bot.fetch_user(entry['user_id'])
        username = user.display_name if user else "Unknown User"

        # Medal emojis for top 3
        if idx == 1:
            medal = "🥇"
        elif idx == 2:
            medal = "🥈"
        elif idx == 3:
            medal = "🥉"
        else:
            medal = f"**{idx}.**"

        shiny_count = entry['shiny_count']
        leaderboard_text.append(f"{medal} **{username}** - {shiny_count} shinies")

    embed.add_field(
        name="Rankings",
        value="\n".join(leaderboard_text),
        inline=False
    )

    embed.set_footer(text=f"Odds: 1/512 (0.195%) • Use /shinies to view your collection!")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name='gym', description='Challenge Gym Leaders and earn badges!')
@app_commands.describe(region='Choose which region to challenge')
@app_commands.choices(region=[
    app_commands.Choice(name='Kanto (Gen 1)', value='kanto'),
    app_commands.Choice(name='Johto (Gen 2)', value='johto'),
])
async def gym(interaction: discord.Interaction, region: str):
    """Challenge gym leaders from a specific region"""
    # Defer immediately to prevent timeout
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    # Get user's badges
    user_badges = await db.get_user_badges(interaction.user.id, interaction.guild.id)

    # Load user's Pokemon
    user_pokemon = await db.get_user_pokemon_for_trade(interaction.user.id, interaction.guild.id)

    if not user_pokemon:
        await interaction.followup.send(f"❌ You don't have any Pokemon to battle with!", ephemeral=True)
        return

    # Get all levels in one batch query
    pokemon_ids = [p['pokemon_id'] for p in user_pokemon]
    level_dict = await db.get_multiple_species_levels(interaction.user.id, interaction.guild.id, pokemon_ids)

    # Add levels to Pokemon
    pokemon_with_levels = [{**p, 'level': level_dict.get(p['pokemon_id'], 1)} for p in user_pokemon]
    pokemon_with_levels.sort(key=lambda p: p['level'], reverse=True)

    # Create gym selection view for the chosen region
    view = GymSelectView(interaction.user, interaction.guild.id, pokemon_with_levels, user_badges, region)
    embed = view.create_embed()
    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name='gyms', description='View all available Gym Leaders')
@app_commands.describe(region='Choose which region to view (optional - shows both if not specified)')
@app_commands.choices(region=[
    app_commands.Choice(name='Kanto (Gen 1)', value='kanto'),
    app_commands.Choice(name='Johto (Gen 2)', value='johto'),
    app_commands.Choice(name='Both Regions', value='both'),
])
async def gyms(interaction: discord.Interaction, region: str = 'both'):
    """View all gym leaders across regions"""
    # Defer immediately to prevent timeout
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    # Get user's badges
    user_badges = await db.get_user_badges(interaction.user.id, interaction.guild.id)

    # Count badges by region
    kanto_gym_list = gym_leaders.get_all_gym_leaders()
    johto_gym_list = gym_leaders.get_all_gym_leaders_johto()
    kanto_badge_count = sum(1 for gym_key, _ in kanto_gym_list if gym_key in user_badges)
    johto_badge_count = sum(1 for gym_key, _ in johto_gym_list if gym_key in user_badges)
    total_badges = kanto_badge_count + johto_badge_count

    # Create embed based on region
    if region == 'both':
        embed = discord.Embed(
            title="🏟️ Pokemon Gym Leaders",
            description=f"**{interaction.user.display_name}** | Total: **{total_badges}/16** (Kanto: {kanto_badge_count}/8, Johto: {johto_badge_count}/8)\n\nUse `/gym region:<region>` to challenge gym leaders!",
            color=discord.Color.gold() if total_badges == 16 else discord.Color.blue()
        )

        # Add Kanto gym leaders
        kanto_list = []
        for gym_key, gym_data in kanto_gym_list:
            has_badge = gym_key in user_badges
            badge_indicator = gym_data['badge_emoji'] if has_badge else "⭕"
            status = "✅" if has_badge else "❌"
            kanto_list.append(f"{badge_indicator} **{gym_data['name']}** ({gym_data['type'].title()}) {status}")

        embed.add_field(
            name="🗾 Kanto Region",
            value="\n".join(kanto_list),
            inline=True
        )

        # Add Johto gym leaders
        johto_list = []
        for gym_key, gym_data in johto_gym_list:
            has_badge = gym_key in user_badges
            badge_indicator = gym_data['badge_emoji'] if has_badge else "⭕"
            status = "✅" if has_badge else "❌"
            johto_list.append(f"{badge_indicator} **{gym_data['name']}** ({gym_data['type'].title()}) {status}")

        embed.add_field(
            name="🌸 Johto Region",
            value="\n".join(johto_list),
            inline=True
        )

    elif region == 'kanto':
        embed = discord.Embed(
            title="🗾 Kanto Gym Leaders",
            description=f"**{interaction.user.display_name}** | Badges: **{kanto_badge_count}/8**\n\nUse `/gym region:kanto` to challenge!",
            color=discord.Color.gold() if kanto_badge_count == 8 else discord.Color.blue()
        )

        for gym_key, gym_data in kanto_gym_list:
            has_badge = gym_key in user_badges
            badge_indicator = gym_data['badge_emoji'] if has_badge else "⭕"
            status = "✅ Defeated" if has_badge else "❌ Not defeated"

            embed.add_field(
                name=f"{badge_indicator} {gym_data['name']} - {gym_data['title']}",
                value=f"**Type:** {gym_data['type'].title()}\n**Location:** {gym_data['location']}\n**Difficulty:** {'⭐' * gym_data['difficulty']}\n**Status:** {status}",
                inline=True
            )

    else:  # johto
        embed = discord.Embed(
            title="🌸 Johto Gym Leaders",
            description=f"**{interaction.user.display_name}** | Badges: **{johto_badge_count}/8**\n\nUse `/gym region:johto` to challenge!",
            color=discord.Color.gold() if johto_badge_count == 8 else discord.Color.blue()
        )

        for gym_key, gym_data in johto_gym_list:
            has_badge = gym_key in user_badges
            badge_indicator = gym_data['badge_emoji'] if has_badge else "⭕"
            status = "✅ Defeated" if has_badge else "❌ Not defeated"

            embed.add_field(
                name=f"{badge_indicator} {gym_data['name']} - {gym_data['title']}",
                value=f"**Type:** {gym_data['type'].title()}\n**Location:** {gym_data['location']}\n**Difficulty:** {'⭐' * gym_data['difficulty']}\n**Status:** {status}",
                inline=True
            )

    embed.set_footer(text="Challenge gym leaders to earn badges and rewards!")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name='trade', description='Trade Pokemon with another user')
@app_commands.describe(user='The user you want to trade with')
async def trade(interaction: discord.Interaction, user: discord.Member):
    """Initiate a trade with another user"""
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server!", ephemeral=True)
        return

    # Can't trade with yourself
    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ You can't trade with yourself!", ephemeral=True)
        return

    # Can't trade with bots
    if user.bot:
        await interaction.response.send_message("❌ You can't trade with bots!", ephemeral=True)
        return

    # Defer the response
    await interaction.response.defer()

    # Create trade view
    view = TradeView(interaction.user, user, interaction.guild.id)
    await view.load_pokemon()

    # Check if both users have Pokemon
    if not view.user1_pokemon:
        await interaction.followup.send(f"❌ {interaction.user.display_name} doesn't have any Pokemon to trade!")
        return

    if not view.user2_pokemon:
        await interaction.followup.send(f"❌ {user.display_name} doesn't have any Pokemon to trade!")
        return

    # Get levels in batch for both users
    user1_ids = [p['pokemon_id'] for p in view.user1_pokemon]
    user2_ids = [p['pokemon_id'] for p in view.user2_pokemon]

    user1_levels = await db.get_multiple_species_levels(interaction.user.id, interaction.guild.id, user1_ids)
    user2_levels = await db.get_multiple_species_levels(user.id, interaction.guild.id, user2_ids)

    # Add levels and sort
    user1_with_levels = [{**p, 'level': user1_levels.get(p['pokemon_id'], 1)} for p in view.user1_pokemon]
    user1_with_levels.sort(key=lambda p: p['level'], reverse=True)

    user2_with_levels = [{**p, 'level': user2_levels.get(p['pokemon_id'], 1)} for p in view.user2_pokemon]
    user2_with_levels.sort(key=lambda p: p['level'], reverse=True)

    # Update view's pokemon lists with level info
    view.user1_pokemon = user1_with_levels
    view.user2_pokemon = user2_with_levels

    # Populate dropdown options (max 25 options per dropdown)
    user1_options = []
    for pokemon in user1_with_levels[:25]:
        label = f"Lv.{pokemon['level']} | #{pokemon['pokemon_id']:03d} {pokemon['pokemon_name']}"
        user1_options.append(discord.SelectOption(
            label=label,
            value=str(pokemon['id']),
            emoji="🔄"  # Trade/exchange emoji
        ))

    user2_options = []
    for pokemon in user2_with_levels[:25]:
        label = f"Lv.{pokemon['level']} | #{pokemon['pokemon_id']:03d} {pokemon['pokemon_name']}"
        user2_options.append(discord.SelectOption(
            label=label,
            value=str(pokemon['id']),
            emoji="🔄"
        ))

    # Set dropdown options
    view.user1_select.options = user1_options
    view.user2_select.options = user2_options

    # Update placeholders with usernames
    view.user1_select.placeholder = f"{interaction.user.display_name}: Select your Pokemon..."
    view.user2_select.placeholder = f"{user.display_name}: Select your Pokemon..."

    embed = view.create_embed()
    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name='leaderboard', description='View server leaderboards')
async def leaderboard(interaction: discord.Interaction):
    """Show server leaderboards with different categories"""
    # Defer IMMEDIATELY before any checks
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    # Create interactive view
    view = LeaderboardView(interaction.guild)
    await view.load_leaderboard()
    embed = await view.create_embed()

    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name='wiki', description='View Pokemon lore and information')
@app_commands.describe(pokemon='Pokemon name or number (optional - random if not specified)')
async def wiki(interaction: discord.Interaction, pokemon: str = None):
    """Show Pokemon wiki information with Pokedex entries"""
    # Defer the response immediately to prevent timeout
    await interaction.response.defer()

    try:
        # Determine which Pokemon to fetch
        if pokemon:
            # User specified a Pokemon - try to parse as number or use as name
            try:
                pokemon_id = int(pokemon)
                if pokemon_id < 1 or pokemon_id > 151:
                    await interaction.followup.send(f"❌ Please specify a Gen 1 Pokemon (1-151)!")
                    return
                identifier = pokemon_id
            except ValueError:
                # It's a name
                identifier = pokemon.lower()
        else:
            # Random Gen 1 or Gen 2 Pokemon
            identifier = random.randint(1, 251)

        # Fetch Pokemon species data
        async with aiohttp.ClientSession() as session:
            species_data = await fetch_pokemon_species(session, identifier)

        if not species_data:
            await interaction.followup.send(f"❌ Could not find Pokemon: {pokemon}. Make sure it's a Gen 1 or Gen 2 Pokemon!")
            return

        # Create embed
        types_str = ' / '.join(species_data['types'])

        embed = discord.Embed(
            title=f"#{species_data['id']:03d} {species_data['name']}",
            description=f"*{species_data['genus']}*",
            color=discord.Color.blue()
        )

        if species_data['sprite']:
            embed.set_thumbnail(url=species_data['sprite'])

        # Add stats
        embed.add_field(
            name="Type",
            value=types_str,
            inline=True
        )

        embed.add_field(
            name="Height",
            value=f"{species_data['height']}m",
            inline=True
        )

        embed.add_field(
            name="Weight",
            value=f"{species_data['weight']}kg",
            inline=True
        )

        embed.add_field(
            name="Habitat",
            value=species_data['habitat'],
            inline=True
        )

        embed.add_field(
            name="Generation",
            value=species_data['generation'],
            inline=True
        )

        # Add random Pokedex entry
        if species_data['flavor_texts']:
            random_entry = random.choice(species_data['flavor_texts'])
            embed.add_field(
                name="📖 Pokedex Entry",
                value=random_entry,
                inline=False
            )

        embed.set_footer(text="Data from PokeAPI • Use /wiki [pokemon] to search specific Pokemon")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error fetching Pokemon data: {str(e)}")
        print(f"Error in wiki command: {e}")


@bot.tree.command(name='quests', description='View your daily quests and progress')
async def quests(interaction: discord.Interaction):
    """View daily quests for Pokedollar rewards"""
    # Defer IMMEDIATELY before any checks
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    user_id = interaction.user.id
    guild_id = interaction.guild.id

    # Get or create today's daily quests
    quests_data = await db.get_daily_quests(user_id, guild_id)

    if not quests_data:
        # Generate new quests for today
        new_quests = quest_system.generate_daily_quests()
        success = await db.create_daily_quests(user_id, guild_id, new_quests)

        if success:
            quests_data = await db.get_daily_quests(user_id, guild_id)
        else:
            await interaction.followup.send("❌ Failed to generate daily quests. Please try again!")
            return

    # Create embed
    embed = discord.Embed(
        title="📋 Daily Quests",
        description=f"{interaction.user.display_name}'s quests for today",
        color=discord.Color.blue()
    )

    total_currency_earned = 0
    all_complete = True

    # Display each quest
    for i in range(1, 4):
        quest_type = quests_data.get(f'quest_{i}_type')
        target = quests_data.get(f'quest_{i}_target')
        progress = quests_data.get(f'quest_{i}_progress', 0)
        completed = quests_data.get(f'quest_{i}_completed', False)
        reward = quests_data.get(f'quest_{i}_reward')

        if quest_type:
            # Get quest description
            quest_info = None
            for variant in quest_system.QUEST_TYPES.get(quest_type, {}).get('variants', []):
                if variant['target'] == target and variant['reward'] == reward:
                    quest_info = variant
                    break

            if quest_info:
                status_emoji = "✅" if completed else "⏳"
                progress_bar = f"{progress}/{target}"

                # Build field value
                field_value = f"{quest_info['description']}\n"
                field_value += f"**Progress:** {progress_bar}\n"
                field_value += f"**Reward:** ₽{reward}"

                embed.add_field(
                    name=f"{status_emoji} Quest {i}",
                    value=field_value,
                    inline=False
                )

                if completed:
                    total_currency_earned += reward
                else:
                    all_complete = False

    # Calculate time until midnight (quest reset)
    from datetime import datetime, timedelta
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    time_until_reset = tomorrow - now

    hours = int(time_until_reset.total_seconds() // 3600)
    minutes = int((time_until_reset.total_seconds() % 3600) // 60)

    reset_text = f"Resets in {hours}h {minutes}m"

    # Add summary
    if all_complete:
        embed.add_field(
            name="🎉 All Quests Complete!",
            value=f"You've earned **₽{total_currency_earned}** today!\nNew quests available after reset.",
            inline=False
        )
        embed.set_footer(text=f"⏰ {reset_text}")
    else:
        embed.set_footer(text=f"⏰ {reset_text}")

    await interaction.followup.send(embed=embed)


@bot.tree.command(name='balance', description='Check your Pokedollar balance')
async def balance(interaction: discord.Interaction):
    """Check Pokedollar balance"""
    # Defer IMMEDIATELY before any checks
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    user_id = interaction.user.id
    guild_id = interaction.guild.id

    # Get balance
    balance_amount = await db.get_balance(user_id, guild_id)

    # Create embed
    embed = discord.Embed(
        title="💰 Pokedollars",
        description=f"{interaction.user.display_name}'s Balance",
        color=discord.Color.gold()
    )

    embed.add_field(
        name="Balance",
        value=f"**{balance_amount}** Pokedollars",
        inline=False
    )

    embed.add_field(
        name="How to earn",
        value="• Catch Pokemon (5-15 💰)\n• Catch Legendaries (50 💰)\n• Sell duplicate Pokemon",
        inline=False
    )

    embed.set_footer(text="Use /shop to spend your Pokedollars!")

    await interaction.followup.send(embed=embed)


# Interactive Shop View
class ShopView(View):
    def __init__(self, user_id: int, guild_id: int, balance: int, shop_items: list):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user_id = user_id
        self.guild_id = guild_id
        self.balance = balance
        self.shop_items = shop_items
        self.current_page = 0
        self.items_per_page = 1  # Show 1 pack at a time for clean display

        # Add navigation and purchase buttons
        self.update_buttons()

    def update_buttons(self):
        """Update button states based on current page"""
        self.clear_items()

        total_pages = len(self.shop_items)
        current_item = self.shop_items[self.current_page]
        can_afford = self.balance >= current_item['price']

        # Previous button
        prev_btn = Button(
            label="◀️ Previous",
            style=discord.ButtonStyle.gray,
            disabled=(self.current_page == 0),
            row=0
        )
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)

        # Page indicator
        page_btn = Button(
            label=f"{self.current_page + 1}/{total_pages}",
            style=discord.ButtonStyle.gray,
            disabled=True,
            row=0
        )
        self.add_item(page_btn)

        # Next button
        next_btn = Button(
            label="Next ▶️",
            style=discord.ButtonStyle.gray,
            disabled=(self.current_page >= total_pages - 1),
            row=0
        )
        next_btn.callback = self.next_page
        self.add_item(next_btn)

        # Buy button
        buy_btn = Button(
            label=f"💰 Buy for {current_item['price']} Pokedollars",
            style=discord.ButtonStyle.green if can_afford else discord.ButtonStyle.red,
            disabled=not can_afford,
            row=1
        )
        buy_btn.callback = self.buy_item
        self.add_item(buy_btn)

        # Refresh button
        refresh_btn = Button(
            label="🔄 Refresh Balance",
            style=discord.ButtonStyle.blurple,
            row=1
        )
        refresh_btn.callback = self.refresh_balance
        self.add_item(refresh_btn)

    def create_embed(self):
        """Create the shop embed for current page"""
        current_item = self.shop_items[self.current_page]

        # Custom pokemoncard emoji
        pokemoncard = "<:pokemoncard:1426317656163750008>"

        # Determine tier emoji
        tier_emojis = {
            'Basic Pack': '1️⃣',
            'Booster Pack': '2️⃣',
            'Premium Pack': '3️⃣',
            'Elite Trainer Pack': '4️⃣',
            'Master Collection': '5️⃣'
        }
        tier_emoji = tier_emojis.get(current_item['item_name'], '📦')

        # Determine color based on tier
        colors = {
            'Basic Pack': discord.Color.light_grey(),
            'Booster Pack': discord.Color.green(),
            'Premium Pack': discord.Color.blue(),
            'Elite Trainer Pack': discord.Color.purple(),
            'Master Collection': discord.Color.gold()
        }
        color = colors.get(current_item['item_name'], discord.Color.blue())

        embed = discord.Embed(
            title=f"{pokemoncard} Pokemon Shop",
            description=f"**Your Balance:** {self.balance} 💰",
            color=color
        )

        # Pack details
        can_afford = self.balance >= current_item['price']
        afford_status = "✅ You can afford this!" if can_afford else "❌ Not enough Pokedollars"

        embed.add_field(
            name=f"{tier_emoji} {current_item['item_name']}",
            value=f"**{current_item['description']}**",
            inline=False
        )

        embed.add_field(
            name="💰 Price",
            value=f"{current_item['price']} Pokedollars",
            inline=True
        )

        embed.add_field(
            name="Status",
            value=afford_status,
            inline=True
        )

        # Add pack details if available
        if current_item.get('pack_config'):
            import json
            config = json.loads(current_item['pack_config']) if isinstance(current_item['pack_config'], str) else current_item['pack_config']

            details = []
            details.append(f"📊 **Pokemon:** {config['min_pokemon']}-{config['max_pokemon']}")
            details.append(f"✨ **Shiny Chance:** {config['shiny_chance']*100}%")
            details.append(f"👑 **Legendary Chance:** {config['legendary_chance']*100}%")

            if config.get('mega_pack_chance', 0) > 0:
                details.append(f"🎉 **Mega Pack:** {config['mega_pack_chance']*100}% chance for {config['mega_pack_size']} Pokemon!")

            if config.get('guaranteed_rare'):
                count = config.get('guaranteed_rare_count', 1)
                details.append(f"⭐ **Guaranteed:** {count} Rare Pokemon!")

            if config.get('guaranteed_shiny_or_legendaries'):
                details.append(f"🌟 **Special:** Guaranteed Shiny OR {config.get('guaranteed_legendary_count', 3)}+ Legendaries!")

            embed.add_field(
                name="📋 Pack Details",
                value="\n".join(details),
                inline=False
            )

        embed.set_footer(text="Use the buttons below to navigate and purchase packs!")

        return embed

    async def prev_page(self, interaction: discord.Interaction):
        """Go to previous page"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your shop!", ephemeral=True)
            return

        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("⬅️ You're already on the first page!", ephemeral=True)

    async def next_page(self, interaction: discord.Interaction):
        """Go to next page"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your shop!", ephemeral=True)
            return

        if self.current_page < len(self.shop_items) - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("➡️ You're already on the last page!", ephemeral=True)

    async def buy_item(self, interaction: discord.Interaction):
        """Purchase the current item"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your shop!", ephemeral=True)
            return

        current_item = self.shop_items[self.current_page]

        # Check balance again
        current_balance = await db.get_balance(self.user_id, self.guild_id)

        if current_balance < current_item['price']:
            await interaction.response.send_message(
                f"❌ Not enough Pokedollars! You need **{current_item['price'] - current_balance}** more.",
                ephemeral=True
            )
            return

        # Attempt purchase
        success = await db.spend_currency(self.user_id, self.guild_id, current_item['price'])

        if not success:
            await interaction.response.send_message("❌ Purchase failed. Please try again!", ephemeral=True)
            return

        # Add pack to inventory with configuration
        import json
        pack_config = json.loads(current_item['pack_config']) if isinstance(current_item['pack_config'], str) else current_item['pack_config']
        await db.add_pack(self.user_id, self.guild_id, current_item['item_name'], pack_config)

        # Update balance
        self.balance = await db.get_balance(self.user_id, self.guild_id)

        # Create success message
        pokemoncard = "<:pokemoncard:1426317656163750008>"
        success_embed = discord.Embed(
            title=f"{pokemoncard} Purchase Successful!",
            description=f"You bought a **{current_item['item_name']}**!",
            color=discord.Color.green()
        )

        success_embed.add_field(
            name="New Balance",
            value=f"{self.balance} 💰",
            inline=True
        )

        success_embed.add_field(
            name="Pack Added",
            value="Use `/pack` to open it!",
            inline=True
        )

        # Update view
        self.update_buttons()
        embed = self.create_embed()

        await interaction.response.edit_message(embed=embed, view=self)
        await interaction.followup.send(embed=success_embed, ephemeral=True)

    async def refresh_balance(self, interaction: discord.Interaction):
        """Refresh the user's balance"""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your shop!", ephemeral=True)
            return

        # Get updated balance
        self.balance = await db.get_balance(self.user_id, self.guild_id)

        # Update view
        self.update_buttons()
        embed = self.create_embed()

        await interaction.response.edit_message(embed=embed, view=self)


@bot.tree.command(name='shop', description='View the Pokemon shop')
async def shop(interaction: discord.Interaction):
    """View available items in the shop with interactive GUI"""
    # Defer IMMEDIATELY before any checks to prevent timeout
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    user_id = interaction.user.id
    guild_id = interaction.guild.id

    # Get shop items
    shop_items = await db.get_shop_items()

    if not shop_items:
        await interaction.followup.send("❌ Shop is currently empty! Check back later.")
        return

    # Get user balance
    balance = await db.get_balance(user_id, guild_id)

    # Create interactive shop view
    view = ShopView(user_id, guild_id, balance, shop_items)
    embed = view.create_embed()

    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name='buy', description='Purchase an item from the shop')
@app_commands.describe(item='The name of the item you want to buy (e.g., Basic Pack)')
async def buy(interaction: discord.Interaction, item: str):
    """Purchase an item from the shop"""
    # Defer IMMEDIATELY before any checks
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    user_id = interaction.user.id
    guild_id = interaction.guild.id

    # Get shop items
    shop_items = await db.get_shop_items()

    # Find matching item (case-insensitive)
    item_lower = item.lower()
    matching_item = None
    for shop_item in shop_items:
        if shop_item['item_name'].lower() == item_lower:
            matching_item = shop_item
            break

    if not matching_item:
        await interaction.followup.send(f"❌ Item '{item}' not found in shop! Use `/shop` to see available items.")
        return

    # Check balance
    balance = await db.get_balance(user_id, guild_id)

    if balance < matching_item['price']:
        shortage = matching_item['price'] - balance
        await interaction.followup.send(
            f"❌ Not enough Pokedollars! You need **{shortage}** more Pokedollars.\n"
            f"**Your balance:** {balance} 💰\n**Item price:** {matching_item['price']} 💰"
        )
        return

    # Attempt to spend currency
    success = await db.spend_currency(user_id, guild_id, matching_item['price'])

    if not success:
        await interaction.followup.send("❌ Purchase failed. Please try again!")
        return

    # Handle different item types
    if matching_item['item_type'] == 'pack':
        # Add pack to user's inventory with configuration
        import json
        pack_config = json.loads(matching_item['pack_config']) if isinstance(matching_item['pack_config'], str) else matching_item['pack_config']
        await db.add_pack(user_id, guild_id, matching_item['item_name'], pack_config)

        # Create success embed
        pokemoncard = "<:pokemoncard:1426317656163750008>"
        embed = discord.Embed(
            title=f"{pokemoncard} Purchase Successful!",
            description=f"You bought a **{matching_item['item_name']}**!",
            color=discord.Color.green()
        )

        new_balance = await db.get_balance(user_id, guild_id)

        embed.add_field(
            name="Item",
            value=matching_item['item_name'],
            inline=True
        )

        embed.add_field(
            name="Price Paid",
            value=f"{matching_item['price']} 💰",
            inline=True
        )

        embed.add_field(
            name="New Balance",
            value=f"{new_balance} 💰",
            inline=True
        )

        embed.set_footer(text="Use /pack to open your pack!")

        await interaction.followup.send(embed=embed)
    else:
        # Future item types can be handled here
        await interaction.followup.send(f"✅ Purchased {matching_item['item_name']}!")


@bot.tree.command(name='sell', description='Sell duplicate Pokemon for Pokedollars')
async def sell(interaction: discord.Interaction):
    """Sell duplicate Pokemon for currency"""
    # Defer IMMEDIATELY before any checks (ephemeral for privacy)
    await interaction.response.defer(ephemeral=True)

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

    user_id = interaction.user.id
    guild_id = interaction.guild.id

    # Get duplicate Pokemon
    duplicates = await db.get_duplicate_pokemon(user_id, guild_id)

    if not duplicates:
        await interaction.followup.send("❌ You don't have any duplicate Pokemon to sell! Catch more Pokemon first.")
        return

    # Create embed showing duplicates
    embed = discord.Embed(
        title="💰 Sell Duplicate Pokemon",
        description="Select a Pokemon to sell one copy at a time, or click **Sell All Duplicates** to sell all extras of every species!\n\n**Note:** You cannot sell your last copy of any Pokemon!",
        color=discord.Color.gold()
    )

    # Show top duplicates with sell values
    duplicate_list = []
    for dup in duplicates[:10]:
        sell_price = db.calculate_sell_price(dup['pokemon_id'])
        duplicate_list.append(f"#{dup['pokemon_id']:03d} **{dup['pokemon_name']}** - x{dup['count']} ({sell_price}💰 each)")

    embed.add_field(
        name="Your Duplicates",
        value='\n'.join(duplicate_list) if duplicate_list else "No duplicates",
        inline=False
    )

    # Get all catches for user to allow selection
    all_catches = await db.get_user_pokemon_for_trade(user_id, guild_id)

    if not all_catches:
        await interaction.followup.send("❌ No Pokemon available to sell!")
        return

    # Create dropdown with duplicates only (max 25 options)
    options = []
    duplicate_names = {d['pokemon_name'] for d in duplicates}
    seen_names = set()

    for catch in all_catches:
        if catch['pokemon_name'] in duplicate_names and catch['pokemon_name'] not in seen_names:
            seen_names.add(catch['pokemon_name'])
            label = f"#{catch['pokemon_id']:03d} {catch['pokemon_name']}"
            sell_price = db.calculate_sell_price(catch['pokemon_id'])
            description = f"Sell for {sell_price}💰"
            options.append(discord.SelectOption(label=label, value=catch['pokemon_name'], description=description))

            if len(options) >= 25:
                break

    if not options:
        await interaction.followup.send("❌ No duplicate Pokemon available to sell!")
        return

    # Create select menu
    select = Select(
        placeholder="Select a Pokemon to sell...",
        options=options,
        custom_id="sell_select"
    )

    async def sell_callback(select_interaction: discord.Interaction):
        """Handle selling one Pokemon"""
        if select_interaction.user.id != user_id:
            await select_interaction.response.send_message("❌ This is not your sale menu!", ephemeral=True)
            return

        selected_name = select.values[0]

        # Find a duplicate catch to sell (not the first one caught, and not shinies)
        user_catches = await db.get_user_pokemon_for_trade(user_id, guild_id)
        catches_of_type = [c for c in user_catches if c['pokemon_name'] == selected_name]

        # Filter out shinies when looking for duplicates
        non_shiny_catches = [c for c in catches_of_type if not c.get('is_shiny', False)]

        if len(non_shiny_catches) < 2:
            if any(c.get('is_shiny', False) for c in catches_of_type):
                await select_interaction.response.send_message("❌ Cannot sell! You only have shiny copies of this Pokemon, which are protected from selling.", ephemeral=True)
            else:
                await select_interaction.response.send_message("❌ You can't sell your last copy of this Pokemon!", ephemeral=True)
            return

        # Sell the most recent non-shiny catch (last in list)
        catch_to_sell = non_shiny_catches[-1]

        # Attempt to sell
        sale_price = await db.sell_pokemon(user_id, guild_id, catch_to_sell['id'])

        if sale_price is None:
            await select_interaction.response.send_message("❌ Sale failed! Please try again.", ephemeral=True)
            return

        # Get new balance
        new_balance = await db.get_balance(user_id, guild_id)

        # Update quest progress for selling Pokemon and earning Pokedollars
        sell_quest_result = await db.update_quest_progress(user_id, guild_id, 'sell_pokemon')
        earn_quest_result = await db.update_quest_progress(user_id, guild_id, 'earn_pokedollars', increment=sale_price)

        # Combine quest results and award currency
        total_quest_currency = 0
        if sell_quest_result and sell_quest_result.get('total_currency', 0) > 0:
            total_quest_currency += sell_quest_result['total_currency']
        if earn_quest_result and earn_quest_result.get('total_currency', 0) > 0:
            total_quest_currency += earn_quest_result['total_currency']

        # Award quest currency if any
        if total_quest_currency > 0:
            await db.add_currency(user_id, guild_id, total_quest_currency)

        # Create success embed
        success_embed = discord.Embed(
            title="✅ Pokemon Sold!",
            description=f"You sold **{selected_name}** for **₽{sale_price}**!",
            color=discord.Color.green()
        )

        success_embed.add_field(
            name="New Balance",
            value=f"₽{new_balance:,}",
            inline=False
        )

        # Add quest completion notification if any
        if total_quest_currency > 0:
            quest_text = []
            if sell_quest_result and sell_quest_result.get('completed_quests'):
                for q in sell_quest_result['completed_quests']:
                    quest_text.append(f"✅ {q['description']} (+₽{q['reward']})")
            if earn_quest_result and earn_quest_result.get('completed_quests'):
                for q in earn_quest_result['completed_quests']:
                    quest_text.append(f"✅ {q['description']} (+₽{q['reward']})")

            if quest_text:
                success_embed.add_field(
                    name="🎯 Quests Completed!",
                    value='\n'.join(quest_text),
                    inline=False
                )

        await select_interaction.response.send_message(embed=success_embed, ephemeral=True)

    async def sell_all_dupes_callback(button_interaction: discord.Interaction):
        """Handle selling ALL duplicates of ALL Pokemon species"""
        if button_interaction.user.id != user_id:
            await button_interaction.response.send_message("❌ This is not your sale menu!", ephemeral=True)
            return

        # Defer response since this might take a while
        await button_interaction.response.defer(ephemeral=True)

        # Get all user's Pokemon
        user_catches = await db.get_user_pokemon_for_trade(user_id, guild_id)

        # Group by species name
        species_dict = {}
        for catch in user_catches:
            name = catch['pokemon_name']
            if name not in species_dict:
                species_dict[name] = []
            species_dict[name].append(catch)

        # Sell all duplicates (keeping first of each species and all shinies)
        total_earned = 0
        total_sold = 0
        species_sold = {}  # Track how many of each species sold
        shinies_protected = 0  # Track how many shinies were protected

        for species_name, catches in species_dict.items():
            if len(catches) > 1:
                # Separate shinies from non-shinies
                non_shiny_catches = [c for c in catches if not c.get('is_shiny', False)]
                shiny_catches = [c for c in catches if c.get('is_shiny', False)]

                # Count protected shinies
                shinies_protected += len(shiny_catches)

                # Only sell non-shiny duplicates (keep at least one non-shiny if it exists)
                if len(non_shiny_catches) > 1:
                    # Sell all non-shiny duplicates except the first one
                    for catch in non_shiny_catches[1:]:
                        sale_price = await db.sell_pokemon(user_id, guild_id, catch['id'])
                        if sale_price is not None:
                            total_earned += sale_price
                            total_sold += 1
                            species_sold[species_name] = species_sold.get(species_name, 0) + 1

        if total_sold == 0:
            if shinies_protected > 0:
                await button_interaction.followup.send(f"❌ No duplicates to sell! All your duplicate Pokemon are shiny ({shinies_protected} protected) or you only have one of each.", ephemeral=True)
            else:
                await button_interaction.followup.send("❌ No duplicates to sell! You only have one of each Pokemon.", ephemeral=True)
            return

        # Get new balance
        new_balance = await db.get_balance(user_id, guild_id)

        # Update quest progress for selling Pokemon and earning Pokedollars
        sell_quest_result = None
        for _ in range(total_sold):
            result = await db.update_quest_progress(user_id, guild_id, 'sell_pokemon')
            if result:
                if not sell_quest_result:
                    sell_quest_result = result
                else:
                    sell_quest_result['total_currency'] += result.get('total_currency', 0)
                    if result.get('completed_quests'):
                        sell_quest_result['completed_quests'].extend(result['completed_quests'])

        earn_quest_result = await db.update_quest_progress(user_id, guild_id, 'earn_pokedollars', increment=total_earned)

        # Combine quest results and award currency
        total_quest_currency = 0
        if sell_quest_result and sell_quest_result.get('total_currency', 0) > 0:
            total_quest_currency += sell_quest_result['total_currency']
        if earn_quest_result and earn_quest_result.get('total_currency', 0) > 0:
            total_quest_currency += earn_quest_result['total_currency']

        # Award quest currency if any
        if total_quest_currency > 0:
            await db.add_currency(user_id, guild_id, total_quest_currency)

        # Create success embed with breakdown
        success_embed = discord.Embed(
            title="✅ All Duplicates Sold!",
            description=f"You sold **{total_sold} duplicate Pokemon** for **₽{total_earned:,}**!",
            color=discord.Color.green()
        )

        # Show breakdown of what was sold (limit to top 10)
        breakdown_lines = []
        for species_name, count in sorted(species_sold.items(), key=lambda x: x[1], reverse=True)[:10]:
            breakdown_lines.append(f"• **{species_name}** x{count}")

        if len(species_sold) > 10:
            breakdown_lines.append(f"... and {len(species_sold) - 10} more species")

        success_embed.add_field(
            name="Sold Pokemon",
            value='\n'.join(breakdown_lines),
            inline=False
        )

        success_embed.add_field(
            name="New Balance",
            value=f"₽{new_balance:,}",
            inline=False
        )

        # Add shiny protection notice if any shinies were protected
        if shinies_protected > 0:
            success_embed.add_field(
                name="✨ Shiny Pokemon Protected",
                value=f"**{shinies_protected}** shiny Pokemon were kept safe and not sold!",
                inline=False
            )

        # Add quest completion notification if any
        if total_quest_currency > 0:
            quest_text = []
            if sell_quest_result and sell_quest_result.get('completed_quests'):
                # Deduplicate quest completions
                seen_quests = set()
                for q in sell_quest_result['completed_quests']:
                    quest_key = q['description']
                    if quest_key not in seen_quests:
                        seen_quests.add(quest_key)
                        quest_text.append(f"✅ {q['description']} (+₽{q['reward']})")
            if earn_quest_result and earn_quest_result.get('completed_quests'):
                for q in earn_quest_result['completed_quests']:
                    quest_text.append(f"✅ {q['description']} (+₽{q['reward']})")

            if quest_text:
                success_embed.add_field(
                    name="🎯 Quests Completed!",
                    value='\n'.join(quest_text),
                    inline=False
                )

        await button_interaction.followup.send(embed=success_embed, ephemeral=True)

    select.callback = sell_callback

    # Create "Sell All Dupes" button
    sell_all_button = Button(
        label="Sell All Duplicates",
        style=discord.ButtonStyle.danger,
        emoji="💰",
        custom_id="sell_all_dupes"
    )
    sell_all_button.callback = sell_all_dupes_callback

    # Create view with select and button
    view = View(timeout=180)
    view.add_item(select)
    view.add_item(sell_all_button)

    await interaction.followup.send(embed=embed, view=view)


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
        name="🎯 Catching Pokemon",
        value="Type `ball` when a Pokemon spawns to catch it!\n• 15% chance for a trainer battle\n• Win to claim the Pokemon!",
        inline=False
    )

    embed.add_field(
        name="📊 Progress & Stats",
        value="**/quests** - View daily quests (earn Pokedollars!)\n**/stats [pokemon]** - View detailed stats for your Pokemon\n**/pokedex [@user]** - View collected Pokemon\n**/count** - See how many of each Pokemon you have\n**/shinies** - View your shiny Pokemon collection ✨",
        inline=False
    )

    embed.add_field(
        name="⚔️ Battles",
        value="**/battle @user** - PvP battle with another player\n**/trainer** - Battle trainers for XP (3 per hour)\n**/gym** - Challenge Kanto Gym Leaders\n**/badges** - View your gym badge collection\n• Wild trainer battles: 15% chance when catching Pokemon",
        inline=False
    )

    embed.add_field(
        name="📦 Packs & Items",
        value="**/pack** - Open Pokemon packs (select or open all)\n**/shop** - View available packs & items\n**/buy [item]** - Purchase from shop\n**/balance** - Check Pokedollars",
        inline=False
    )

    embed.add_field(
        name="🔄 Trading",
        value="**/trade @user** - Trade Pokemon with others\n**/sell** - Sell duplicate Pokemon for Pokedollars",
        inline=False
    )

    embed.add_field(
        name="📚 Info & Lore",
        value="**/wiki [pokemon]** - View Pokemon lore & Pokedex entries\n**/leaderboard** - Server rankings\n**/shinyleaderboard** - Top shiny collectors ✨",
        inline=False
    )

    embed.set_footer(text="💡 Tip: Catch Pokemon to earn Pokedollars! Challenge gyms for badges!")

    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name='adminhelp', description='View admin commands (Admin only)')
@app_commands.checks.has_permissions(administrator=True)
async def adminhelp_command(interaction: discord.Interaction):
    """Show admin commands - only visible to administrators"""
    # Defer immediately to prevent timeout
    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="🔧 Mon Bot Admin Commands",
        description="Administrator-only commands for server management",
        color=discord.Color.red()
    )

    embed.add_field(
        name="⚙️ Spawn Configuration",
        value="**/setup #channel** - Add a channel for Pokemon spawns\n**/clear** - Remove all spawn channels from the server",
        inline=False
    )

    embed.add_field(
        name="🧪 Testing & Debug",
        value="**/spawn** - Force spawn a Pokemon in the current channel (for testing)",
        inline=False
    )

    embed.add_field(
        name="📝 Notes",
        value="• Multiple spawn channels can be configured\n• Pokemon spawn randomly every 3-10 minutes\n• Use `/setup` to enable spawns in specific channels",
        inline=False
    )

    embed.set_footer(text="⚠️ These commands require Administrator permission")

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
