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
        pokemon_id = random.randint(1, 151)  # Gen 1 Pokemon only

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


async def fetch_pokemon_moves(session, pokemon_id: int, num_moves: int = 4):
    """Fetch Pokemon's moves from PokeAPI"""
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


def create_catch_embed(pokemon, user, time_taken, is_shiny=False, currency_reward=0):
    """Create an embed for a successful catch"""
    types_str = ', '.join(pokemon['types']).title()

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
    description = f"{shiny_text}**Type:** {types_str}\n**Pokedex #:** {pokemon['id']}\n**Caught in:** {time_str}"
    if currency_reward > 0:
        description += f"\n💰 **Earned:** {currency_reward} Pokedollars"

    embed = discord.Embed(
        title=f"{pokeball} {user.display_name} caught {pokemon['name']}!",
        description=description,
        color=discord.Color.gold() if not is_shiny else discord.Color.purple()
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
            # Remove spawn immediately to prevent race condition (first come first serve)
            spawn_data = active_spawns.pop(channel_id)
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

            # Award Pokedollars for catching (5-15 based on rarity)
            legendary_ids = [144, 145, 146, 150, 151]
            if pokemon['id'] in legendary_ids:
                currency_reward = 50  # Legendary = 50 Pokedollars
            else:
                currency_reward = random.randint(5, 15)  # Regular = 5-15 Pokedollars

            new_balance = await db.add_currency(user_id, guild_id, currency_reward)

            # Add XP to battlepass (10 XP per catch)
            xp_result = await db.add_xp(user_id, guild_id, xp_amount=10)

            # Update quest progress for catching Pokemon
            quest_result = await db.update_quest_progress(user_id, guild_id, 'catch_pokemon')

            # Check if caught Pokemon is legendary (IDs 144-151)
            legendary_ids = [144, 145, 146, 150, 151]
            if pokemon['id'] in legendary_ids:
                legendary_quest_result = await db.update_quest_progress(user_id, guild_id, 'catch_legendary')
                if legendary_quest_result and legendary_quest_result.get('completed_quests'):
                    # Merge quest results
                    if not quest_result:
                        quest_result = legendary_quest_result
                    else:
                        quest_result['total_xp'] += legendary_quest_result['total_xp']
                        quest_result['completed_quests'].extend(legendary_quest_result['completed_quests'])

            # Award quest XP to battlepass if quests were completed
            if quest_result and quest_result.get('total_xp', 0) > 0:
                quest_xp_result = await db.add_xp(user_id, guild_id, xp_amount=quest_result['total_xp'])
                # Update xp_result if quest XP caused level up
                if quest_xp_result and quest_xp_result.get('leveled_up'):
                    if not xp_result or not xp_result.get('leveled_up'):
                        xp_result = quest_xp_result

            # Send catch confirmation with time and currency reward
            embed = create_catch_embed(pokemon, message.author, time_taken, currency_reward=currency_reward)
            await message.channel.send(embed=embed)

            # If user leveled up, send level up message
            if xp_result and xp_result['leveled_up']:
                level_embed = create_level_up_embed(
                    message.author,
                    xp_result['new_level'],
                    xp_result['rewards']
                )
                await message.channel.send(embed=level_embed)

            # If quests were completed, notify user
            if quest_result and quest_result.get('completed_quests'):
                quest_xp = quest_result['total_xp']
                quest_count = len(quest_result['completed_quests'])
                quest_embed = discord.Embed(
                    title="✅ Daily Quest Complete!",
                    description=f"You completed {quest_count} quest(s) and earned **{quest_xp} XP**!",
                    color=discord.Color.green()
                )
                await message.channel.send(embed=quest_embed)


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

    def calculate_damage(self, move: dict, attacker_stats: dict, defender_stats: dict, defender_types: list) -> int:
        """Calculate damage from a move"""
        # Check accuracy
        if random.randint(1, 100) > move['accuracy']:
            return 0  # Miss!

        # Base damage from move power
        if move['damage_class'] == 'physical':
            base_damage = max(1, int((move['power'] * attacker_stats['attack']) / (defender_stats['defense'] * 2)))
        elif move['damage_class'] == 'special':
            # Use attack as special attack for simplicity
            base_damage = max(1, int((move['power'] * attacker_stats['attack']) / (defender_stats['defense'] * 2)))
        else:
            return 0  # Status move

        # Type effectiveness
        type_mult = pkmn.get_type_effectiveness([move['type']], defender_types)

        # Random variation (85-100%)
        random_mult = random.uniform(0.85, 1.0)

        # Critical hit (6.25% chance for 1.5x)
        crit_mult = 1.5 if random.random() < 0.0625 else 1.0

        damage = int(base_damage * type_mult * random_mult * crit_mult)
        return max(1, damage)

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
        else:
            attacker_name = self.user2_choice['pokemon_name']
            defender_name = self.user1_choice['pokemon_name']
            attacker_stats = self.p2_stats
            defender_stats = self.p1_stats
            defender_types = self.user1_choice.get('types', ['normal'])

        # Calculate damage
        damage = self.calculate_damage(move, attacker_stats, defender_stats, defender_types)

        # Build turn log
        self.battle_log.append(f"**Turn {self.turn_count}:**")
        self.battle_log.append(f"⚡ **{attacker_name}** used **{move['name']}**!")

        if damage == 0:
            self.battle_log.append(f"💨 The attack missed!")
        else:
            # Apply damage
            if attacker == 1:
                self.p2_hp -= damage
                self.p2_hp = max(0, self.p2_hp)
            else:
                self.p1_hp -= damage
                self.p1_hp = max(0, self.p1_hp)

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

            current_hp = self.p2_hp if attacker == 1 else self.p1_hp
            max_hp = self.p2_max_hp if attacker == 1 else self.p1_max_hp
            self.battle_log.append(f"💥 Dealt {damage} damage! **{defender_name}** HP: {current_hp}/{max_hp}")

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

        # Award battlepass XP
        await db.add_xp(winner_id, self.guild_id, 50)
        await db.add_xp(loser_id, self.guild_id, 10)

        # Update quest progress for winner (win_battles)
        await db.update_quest_progress(winner_id, self.guild_id, 'win_battles')

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
                user1_text = f"#{self.user1_choice['pokemon_id']:03d} {self.user1_choice['pokemon_name']}"
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
                user2_text = f"#{self.user2_choice['pokemon_id']:03d} {self.user2_choice['pokemon_name']}"
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

            embed.add_field(
                name=f"{self.user1.display_name}'s {self.user1_choice['pokemon_name']}",
                value=f"{p1_hp_bar} {self.p1_hp}/{self.p1_max_hp} HP",
                inline=False
            )

            embed.add_field(
                name=f"{self.user2.display_name}'s {self.user2_choice['pokemon_name']}",
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

    @discord.ui.select(placeholder=f"Select your Pokemon...", custom_id="battle_user1_select", min_values=1, max_values=1)
    async def user1_select(self, interaction: discord.Interaction, select: Select):
        """User 1 selects their Pokemon"""
        if interaction.user.id != self.user1.id:
            await interaction.response.send_message("This is not your battle!", ephemeral=True)
            return

        catch_id = int(select.values[0])
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

    @discord.ui.select(placeholder=f"Select your Pokemon...", custom_id="battle_user2_select", min_values=1, max_values=1)
    async def user2_select(self, interaction: discord.Interaction, select: Select):
        """User 2 selects their Pokemon"""
        if interaction.user.id != self.user2.id:
            await interaction.response.send_message("This is not your battle!", ephemeral=True)
            return

        catch_id = int(select.values[0])
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
                await db.update_quest_progress(self.user1.id, self.guild_id, 'complete_trade')
                await db.update_quest_progress(self.user2.id, self.guild_id, 'complete_trade')
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
                discord.SelectOption(label="⭐ Rarest (Caught Once)", value="rarest", description="Pokemon caught only once"),
                discord.SelectOption(label="👑 Legendaries Only", value="legendaries", description="Legendary Pokemon"),
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
        else:
            self.pokemon_list = await db.get_pokemon_with_counts(self.user_id, self.guild_id, self.sort_by)

        # Fetch levels for each Pokemon species
        for pokemon in self.pokemon_list:
            level = await db.get_species_level(
                self.user_id, self.guild_id,
                pokemon['pokemon_id'], pokemon['pokemon_name']
            )
            pokemon['level'] = level

    def create_embed(self, stats: dict):
        """Create the Pokedex embed"""
        total_pages = max(1, (len(self.pokemon_list) + self.per_page - 1) // self.per_page)

        # Get sort display name
        sort_names = {
            'most_caught': '🔢 Most Caught',
            'alphabetical': '🔤 Alphabetical',
            'pokedex_number': '📋 Pokedex Number',
            'rarest': '⭐ Rarest (x1)',
            'legendaries': '👑 Legendaries',
            'recently_caught': '📅 Recently Caught'
        }
        sort_display = sort_names.get(self.sort_by, 'Most Caught')

        embed = discord.Embed(
            title=f"{self.username}'s Pokedex",
            description=f"**Total Caught:** {stats['total']}\n**Unique Pokemon:** {stats['unique']}/151 ({stats['unique']/151*100:.1f}%)",
            color=discord.Color.blue()
        )

        # Get Pokemon for current page
        start_idx = self.current_page * self.per_page
        end_idx = start_idx + self.per_page
        page_pokemon = self.pokemon_list[start_idx:end_idx]

        if page_pokemon:
            # Create table header
            header = " #    Name          Lvl  Qty  Value\n" + "─" * 36

            # Create table rows
            pokemon_rows = [header]
            for poke in page_pokemon:
                pokedex_num = f"{poke['pokemon_id']:03d}"
                name = poke['pokemon_name'][:12].ljust(12)  # Limit name to 12 chars
                level = f"{poke.get('level', 1):<3}"
                count = f"x{poke['count']:<2}"
                sell_value = db.calculate_sell_price(poke['pokemon_id'])
                value = f"{sell_value}💰"

                row = f"{pokedex_num}  {name}  {level}  {count}  {value}"
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
    # Defer IMMEDIATELY before any checks
    await interaction.response.defer()

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


@bot.tree.command(name='battlepass', description='View your Season 1 battlepass progress')
async def battlepass(interaction: discord.Interaction):
    """View battlepass progress"""
    # Defer IMMEDIATELY before any checks
    await interaction.response.defer()

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server!", ephemeral=True)
        return

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
            description="You don't have any packs to open!\n\nBuy packs from the shop or earn them from the battlepass.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="How to get packs",
            value="• Use `/shop` to buy packs with Pokedollars\n• Use `/battlepass` to earn free packs!",
            inline=False
        )
        await interaction.followup.send(embed=embed)
        return

    # Show pack selection if user has multiple packs
    if len(user_packs) == 1:
        # Only one pack, open it directly
        pack_to_open = user_packs[0]
    else:
        # Create selection menu
        options = []
        for i, pack in enumerate(user_packs[:25]):  # Max 25 options
            import json
            config = json.loads(pack['pack_config']) if isinstance(pack['pack_config'], str) else pack['pack_config']
            label = f"{pack['pack_name']} ({config['min_pokemon']}-{config['max_pokemon']} Pokemon)"
            options.append(discord.SelectOption(label=label, value=str(pack['id']), description=f"{config['shiny_chance']*100}% shiny chance"))

        select = Select(placeholder="Select a pack to open...", options=options)

        # We'll need to handle the selection, but for simplicity, let's just open the first pack
        pack_to_open = user_packs[0]

    # Open the pack
    import json
    pack_config = json.loads(pack_to_open['pack_config']) if isinstance(pack_to_open['pack_config'], str) else pack_to_open['pack_config']

    # Use the pack (removes it from inventory)
    pack_data = await db.use_pack(user_id, guild_id, pack_to_open['id'])

    if not pack_data:
        await interaction.followup.send("Failed to open pack. Please try again!")
        return

    # Determine pack size based on config
    min_poke = pack_config['min_pokemon']
    max_poke = pack_config['max_pokemon']
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
    legendary_ids = [144, 145, 146, 150, 151]

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
                    pokemon_types=pokemon['types']
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
                            pokemon_types=pokemon['types']
                        )

    if not pokemon_list:
        await interaction.followup.send("Error opening pack. Please try again!")
        return

    # Update quest progress
    await db.update_quest_progress(user_id, guild_id, 'open_packs')

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

    # Populate dropdown options (max 25 options per dropdown)
    user1_options = []
    for pokemon in view.user1_pokemon[:25]:
        label = f"#{pokemon['pokemon_id']:03d} {pokemon['pokemon_name']}"
        user1_options.append(discord.SelectOption(label=label, value=str(pokemon['id'])))

    user2_options = []
    for pokemon in view.user2_pokemon[:25]:
        label = f"#{pokemon['pokemon_id']:03d} {pokemon['pokemon_name']}"
        user2_options.append(discord.SelectOption(label=label, value=str(pokemon['id'])))

    # Set dropdown options
    view.user1_select.options = user1_options
    view.user2_select.options = user2_options

    # Update placeholders with usernames
    view.user1_select.placeholder = f"{interaction.user.display_name}: Choose your Pokemon..."
    view.user2_select.placeholder = f"{user.display_name}: Choose your Pokemon..."

    embed = view.create_embed()
    await interaction.followup.send(embed=embed, view=view)


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

    # Populate dropdown options (max 25 options per dropdown)
    user1_options = []
    for pokemon in view.user1_pokemon[:25]:
        label = f"#{pokemon['pokemon_id']:03d} {pokemon['pokemon_name']}"
        user1_options.append(discord.SelectOption(label=label, value=str(pokemon['id'])))

    user2_options = []
    for pokemon in view.user2_pokemon[:25]:
        label = f"#{pokemon['pokemon_id']:03d} {pokemon['pokemon_name']}"
        user2_options.append(discord.SelectOption(label=label, value=str(pokemon['id'])))

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
            # Random Gen 1 Pokemon
            identifier = random.randint(1, 151)

        # Fetch Pokemon species data
        async with aiohttp.ClientSession() as session:
            species_data = await fetch_pokemon_species(session, identifier)

        if not species_data:
            await interaction.followup.send(f"❌ Could not find Pokemon: {pokemon}. Make sure it's a Gen 1 Pokemon!")
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
    """View daily quests for battlepass XP"""
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

    total_xp_earned = 0
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
                field_value += f"**Reward:** {reward} XP"

                embed.add_field(
                    name=f"{status_emoji} Quest {i}",
                    value=field_value,
                    inline=False
                )

                if completed:
                    total_xp_earned += reward
                else:
                    all_complete = False

    # Add summary
    if all_complete:
        embed.add_field(
            name="🎉 All Quests Complete!",
            value=f"You've earned **{total_xp_earned} XP** today!\nCome back tomorrow for new quests.",
            inline=False
        )
    else:
        embed.set_footer(text="Complete quests to earn battlepass XP! Quests reset daily.")

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
        description="Select Pokemon below to sell. Prices vary by rarity!\n\n**Note:** You cannot sell your last copy of a Pokemon!",
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
        """Handle Pokemon sale"""
        if select_interaction.user.id != user_id:
            await select_interaction.response.send_message("❌ This is not your sale menu!", ephemeral=True)
            return

        selected_name = select.values[0]

        # Find a duplicate catch to sell (not the first one caught)
        user_catches = await db.get_user_pokemon_for_trade(user_id, guild_id)
        catches_of_type = [c for c in user_catches if c['pokemon_name'] == selected_name]

        if len(catches_of_type) < 2:
            await select_interaction.response.send_message("❌ You can't sell your last copy of this Pokemon!", ephemeral=True)
            return

        # Sell the most recent catch (last in list)
        catch_to_sell = catches_of_type[-1]

        # Attempt to sell
        sale_price = await db.sell_pokemon(user_id, guild_id, catch_to_sell['id'])

        if sale_price is None:
            await select_interaction.response.send_message("❌ Sale failed! Please try again.", ephemeral=True)
            return

        # Get new balance
        new_balance = await db.get_balance(user_id, guild_id)

        # Create success embed
        success_embed = discord.Embed(
            title="✅ Pokemon Sold!",
            description=f"You sold **{selected_name}** for **{sale_price} Pokedollars**!",
            color=discord.Color.green()
        )

        success_embed.add_field(
            name="New Balance",
            value=f"{new_balance} 💰",
            inline=False
        )

        await select_interaction.response.send_message(embed=success_embed, ephemeral=True)

    select.callback = sell_callback

    # Create view with select
    view = View(timeout=180)
    view.add_item(select)

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
        name="/quests",
        value="View your daily quests and progress (earn XP!)",
        inline=False
    )

    embed.add_field(
        name="/pack",
        value="Open a Pokemon pack (10 random Pokemon)",
        inline=False
    )

    embed.add_field(
        name="/wiki [pokemon]",
        value="View Pokemon lore and Pokedex entries (random if no pokemon specified)",
        inline=False
    )

    embed.add_field(
        name="/leaderboard",
        value="View server leaderboards with different categories",
        inline=False
    )

    embed.add_field(
        name="/trade @user",
        value="Trade Pokemon with another user",
        inline=False
    )

    embed.add_field(
        name="/battle @user",
        value="Battle another user with your Pokemon!",
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
        name="/balance",
        value="Check your Pokedollar balance",
        inline=False
    )

    embed.add_field(
        name="/shop",
        value="View available items and packs for purchase",
        inline=False
    )

    embed.add_field(
        name="/buy [item]",
        value="Purchase an item from the shop (e.g., /buy Basic Pack)",
        inline=False
    )

    embed.add_field(
        name="/sell",
        value="Sell duplicate Pokemon for Pokedollars",
        inline=False
    )

    embed.add_field(
        name="/setup #channel",
        value="(Admin only) Configure which channel Pokemon spawn in",
        inline=False
    )

    embed.add_field(
        name="/clear",
        value="(Admin only) Clear all spawn channels",
        inline=False
    )

    embed.add_field(
        name="/spawn",
        value="(Admin only) Force spawn a Pokemon immediately for testing",
        inline=False
    )

    embed.set_footer(text="Catch Pokemon to earn XP and Pokedollars! Use /shop to buy packs.")

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
