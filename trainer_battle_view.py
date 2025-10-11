"""
Trainer Battle View - handles wild trainer encounters
"""

import discord
from discord.ui import View, Button, Select
import random
import pokemon_data_loader as poke_data
import pokemon_stats as pkmn
import database as db


class TrainerBattleView(View):
    """View for trainer battles - simpler than gym battles, 1 user Pokemon vs trainer team"""

    def __init__(self, user: discord.Member, guild_id: int, trainer: dict, trainer_team: list, wild_pokemon: dict, user_pokemon: list, time_taken: float):
        super().__init__(timeout=600)
        self.user = user
        self.guild_id = guild_id
        self.trainer = trainer
        self.trainer_team = trainer_team  # List of {'pokemon_id': int, 'level': int}
        self.wild_pokemon = wild_pokemon  # The Pokemon being fought over
        self.user_pokemon = user_pokemon
        self.time_taken = time_taken

        # Battle state
        self.user_choice = None  # Selected Pokemon
        self.trainer_pokemon_index = 0  # Current trainer Pokemon
        self.battle_started = False
        self.battle_message = None
        self.selection_message = None  # Track the initial selection message

        # HP tracking
        self.user_current_hp = 0
        self.user_max_hp = 0
        self.trainer_current_hp = 0
        self.trainer_max_hp = 0

        # Turn tracking
        self.turn_count = 0
        self.battle_log = []

        # Stat stages
        self.user_stat_stages = {
            'attack': 0, 'defense': 0, 'special-attack': 0,
            'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
        }
        self.trainer_stat_stages = {
            'attack': 0, 'defense': 0, 'special-attack': 0,
            'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
        }

        # Status conditions
        self.user_status = None
        self.user_status_turns = 0
        self.trainer_status = None
        self.trainer_status_turns = 0

        # Pagination for Pokemon selection
        self.current_page = 0
        self.pokemon_per_page = 25

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

        # Create dropdown
        self.pokemon_select = Select(
            placeholder=f"Choose 1 Pokemon to battle {self.trainer['name']}...",
            min_values=1,
            max_values=1
        )

        for pokemon in page_pokemon:
            level = pokemon.get('level', 1)
            types = poke_data.get_pokemon_types(pokemon['pokemon_id'])
            types_str = '/'.join([t.title() for t in types]) if types else 'Unknown'

            self.pokemon_select.add_option(
                label=f"{pokemon['pokemon_name']} (Lv.{level})",
                value=str(pokemon['id']),
                description=f"#{pokemon['pokemon_id']} - {types_str}"
            )

        self.pokemon_select.callback = self.pokemon_selected
        self.add_item(self.pokemon_select)

        # Add pagination buttons if needed
        if self.total_pages > 1:
            prev_button = Button(
                label="◀ Previous",
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page == 0),
                custom_id="prev_page"
            )
            prev_button.callback = self.previous_page
            self.add_item(prev_button)

            next_button = Button(
                label="Next ▶",
                style=discord.ButtonStyle.secondary,
                disabled=(self.current_page >= self.total_pages - 1),
                custom_id="next_page"
            )
            next_button.callback = self.next_page
            self.add_item(next_button)

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
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • {len(self.unique_pokemon)} total Pokemon")
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
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • {len(self.unique_pokemon)} total Pokemon")
        await interaction.response.edit_message(embed=embed, view=self)

    def create_selection_embed(self):
        """Create embed for Pokemon selection"""
        embed = discord.Embed(
            title=f"⚔️ Trainer Battle: {self.trainer['name']} vs. {self.user.display_name}",
            description=f"Select your Pokemon to battle {self.trainer['name']}!",
            color=discord.Color.red()
        )

        # Show trainer's team
        team_text = "\n".join([
            f"• **{poke_data.get_pokemon_name(p['pokemon_id'])}** (Lv.{p['level']})"
            for p in self.trainer_team
        ])
        embed.add_field(
            name=f"{self.trainer['sprite']} {self.trainer['class']}'s Team",
            value=team_text,
            inline=False
        )

        # Show prize
        embed.add_field(
            name="🏆 Win Rewards",
            value=f"• **{self.wild_pokemon['name']}** (wild Pokemon)\n• **₽{self.trainer['reward_money']}** Pokedollars\n• Battle XP",
            inline=False
        )

        return embed

    async def pokemon_selected(self, interaction: discord.Interaction):
        """Handle Pokemon selection and start battle"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
            return

        await interaction.response.defer()

        # Get selected Pokemon
        selected_id = int(self.pokemon_select.values[0])
        selected_pokemon = next((p for p in self.user_pokemon if p['id'] == selected_id), None)

        if not selected_pokemon:
            await interaction.followup.send("❌ Pokemon not found!", ephemeral=True)
            return

        # Get Pokemon level
        species_level = await db.get_species_level(
            self.user.id, self.guild_id,
            selected_pokemon['pokemon_id'], selected_pokemon['pokemon_name']
        )

        # Get Pokemon data
        base_stats = poke_data.get_pokemon_stats(selected_pokemon['pokemon_id'])
        user_stats = pkmn.calculate_battle_stats(base_stats, species_level)
        types = poke_data.get_pokemon_types(selected_pokemon['pokemon_id'])
        moves = poke_data.get_pokemon_moves(selected_pokemon['pokemon_id'], num_moves=4, max_level=species_level)

        self.user_choice = {
            'id': selected_pokemon['id'],
            'pokemon_name': selected_pokemon['pokemon_name'],
            'pokemon_id': selected_pokemon['pokemon_id'],
            'types': types,
            'moves': moves,
            'level': species_level,
            'stats': user_stats,
            'sprite': poke_data.get_pokemon_sprite(selected_pokemon['pokemon_id'])
        }

        self.user_max_hp = user_stats['hp']
        self.user_current_hp = user_stats['hp']

        # Load trainer's first Pokemon
        await self.load_trainer_pokemon(0)

        # Start battle
        self.battle_started = True
        self.turn_count = 0
        self.battle_log = [f"⚔️ **{self.trainer['name']} challenges you to a battle!**"]

        # Store the selection message and disable the dropdown
        self.selection_message = interaction.message
        self.pokemon_select.disabled = True
        await self.selection_message.edit(view=self)

        # Create battle UI
        self.clear_items()
        await self.create_battle_buttons()

        embed = self.create_battle_embed()
        self.battle_message = await interaction.followup.send(embed=embed, view=self)

    async def load_trainer_pokemon(self, index):
        """Load a trainer's Pokemon by index"""
        trainer_poke = self.trainer_team[index]

        # Get Pokemon data
        base_stats = poke_data.get_pokemon_stats(trainer_poke['pokemon_id'])
        trainer_stats = pkmn.calculate_battle_stats(base_stats, trainer_poke['level'])
        types = poke_data.get_pokemon_types(trainer_poke['pokemon_id'])
        moves = poke_data.get_pokemon_moves(trainer_poke['pokemon_id'], num_moves=4, max_level=trainer_poke['level'])

        self.trainer_current_pokemon = {
            'pokemon_id': trainer_poke['pokemon_id'],
            'pokemon_name': poke_data.get_pokemon_name(trainer_poke['pokemon_id']),
            'level': trainer_poke['level'],
            'types': types,
            'moves': moves,
            'stats': trainer_stats,
            'sprite': poke_data.get_pokemon_sprite(trainer_poke['pokemon_id'])
        }

        self.trainer_max_hp = trainer_stats['hp']
        self.trainer_current_hp = trainer_stats['hp']

        # Reset stat stages
        self.trainer_stat_stages = {
            'attack': 0, 'defense': 0, 'special-attack': 0,
            'special-defense': 0, 'speed': 0, 'accuracy': 0, 'evasion': 0
        }
        self.trainer_status = None
        self.trainer_status_turns = 0

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

            move_button = Button(
                label=f"{move['name']} ({move['type']})",
                style=button_style,
                custom_id=f"move_{i}",
                row=i // 2
            )
            move_button.callback = self.create_move_callback(i)
            self.add_item(move_button)

        # Add flee button in last row
        flee_button = Button(
            label="🏃 Flee",
            style=discord.ButtonStyle.secondary,
            custom_id="flee",
            row=2
        )
        flee_button.callback = self.flee_battle
        self.add_item(flee_button)

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

        user_move = self.user_choice['moves'][user_move_index]

        # Determine turn order based on speed
        user_speed = self.user_choice['stats']['speed']
        trainer_speed = self.trainer_current_pokemon['stats']['speed']

        user_goes_first = user_speed >= trainer_speed

        # Execute moves in order
        if user_goes_first:
            await self.user_attacks(user_move)
            if self.trainer_current_hp > 0:  # Trainer still alive
                await self.trainer_attacks()
        else:
            await self.trainer_attacks()
            if self.user_current_hp > 0:  # User still alive
                await self.user_attacks(user_move)

        # Check for battle end
        if self.user_current_hp <= 0:
            await self.handle_defeat(interaction)
            return

        if self.trainer_current_hp <= 0:
            # Trainer Pokemon fainted - check if they have more
            if self.trainer_pokemon_index < len(self.trainer_team) - 1:
                self.trainer_pokemon_index += 1
                await self.load_trainer_pokemon(self.trainer_pokemon_index)
                self.battle_log.append(f"**{self.trainer['name']}** sent out **{self.trainer_current_pokemon['pokemon_name']}**!")
            else:
                # User won!
                await self.handle_victory(interaction)
                return

        # Update UI
        self.clear_items()
        await self.create_battle_buttons()
        embed = self.create_battle_embed()

        if self.battle_message:
            await self.battle_message.edit(embed=embed, view=self)

    async def user_attacks(self, move: dict):
        """User's Pokemon attacks"""
        # Calculate damage
        damage, is_crit, hit = await self.calculate_damage(
            move,
            self.user_choice,
            self.trainer_current_pokemon,
            self.user_stat_stages,
            self.user_status,
            self.trainer_stat_stages
        )

        if hit:
            self.trainer_current_hp = max(0, self.trainer_current_hp - damage)
            crit_text = " **Critical hit!**" if is_crit else ""
            self.battle_log.append(f"**{self.user_choice['pokemon_name']}** used **{move['name']}**! Dealt {damage} damage!{crit_text}")

            if self.trainer_current_hp <= 0:
                self.battle_log.append(f"**{self.trainer_current_pokemon['pokemon_name']}** fainted!")
        else:
            self.battle_log.append(f"**{self.user_choice['pokemon_name']}** used **{move['name']}**... but it missed!")

    async def trainer_attacks(self):
        """Trainer's Pokemon attacks"""
        # Trainer picks random move
        move = random.choice(self.trainer_current_pokemon['moves'])

        # Calculate damage
        damage, is_crit, hit = await self.calculate_damage(
            move,
            self.trainer_current_pokemon,
            self.user_choice,
            self.trainer_stat_stages,
            self.trainer_status,
            self.user_stat_stages
        )

        if hit:
            self.user_current_hp = max(0, self.user_current_hp - damage)
            crit_text = " **Critical hit!**" if is_crit else ""
            self.battle_log.append(f"**{self.trainer_current_pokemon['pokemon_name']}** used **{move['name']}**! Dealt {damage} damage!{crit_text}")

            if self.user_current_hp <= 0:
                self.battle_log.append(f"**{self.user_choice['pokemon_name']}** fainted!")
        else:
            self.battle_log.append(f"**{self.trainer_current_pokemon['pokemon_name']}** used **{move['name']}**... but it missed!")

    async def calculate_damage(self, move: dict, attacker: dict, defender: dict, attacker_stat_stages: dict, attacker_status: str, defender_stat_stages: dict) -> tuple:
        """Calculate damage from a move. Returns (damage, is_crit, hit_success)"""
        # Check accuracy
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

        # Calculate base damage
        power = move.get('power', 50)
        attacker_level = attacker['level']

        # Use attack/defense or special-attack/special-defense based on move type
        if move['damage_class'] == 'physical':
            attack = attacker['stats']['attack']
            defense = defender['stats']['defense']
            attack_stage = attacker_stat_stages.get('attack', 0)
            defense_stage = defender_stat_stages.get('defense', 0)
        else:  # special
            attack = attacker['stats'].get('special-attack', attacker['stats'].get('special_attack', 50))
            defense = defender['stats'].get('special-defense', defender['stats'].get('special_defense', 50))
            attack_stage = attacker_stat_stages.get('special-attack', 0)
            defense_stage = defender_stat_stages.get('special-defense', 0)

        # Apply stat stage multipliers
        attack_multiplier = pkmn.get_stat_stage_multiplier(attack_stage)
        defense_multiplier = pkmn.get_stat_stage_multiplier(defense_stage)

        attack = int(attack * attack_multiplier)
        defense = int(defense * defense_multiplier)

        # Damage formula (simplified Pokemon formula)
        damage = ((2 * attacker_level / 5 + 2) * power * attack / defense / 50) + 2

        # Apply critical hit
        if is_crit:
            damage *= 1.5

        # Random factor (0.85 to 1.0)
        damage *= random.uniform(0.85, 1.0)

        # Type effectiveness
        move_type = move.get('type', 'normal')
        defender_types = defender['types']
        effectiveness = pkmn.get_type_effectiveness(move_type, defender_types)
        damage *= effectiveness

        # STAB (Same Type Attack Bonus)
        if move_type in attacker['types']:
            damage *= 1.5

        damage = int(max(1, damage))

        return damage, is_crit, True

    def create_battle_embed(self):
        """Create battle embed"""
        embed = discord.Embed(
            title=f"⚔️ Trainer Battle: {self.trainer['name']} vs. {self.user.display_name}",
            description=f"**{self.user.display_name}** vs **{self.trainer['name']}**",
            color=discord.Color.orange()
        )

        # Add battle GIF
        embed.set_image(url="https://media4.giphy.com/media/v1.Y2lkPTZjMDliOTUyNTQwbzMxOWEzYjAwdDZsb24wMXN5Z3pwZXl5NHNxNm10M3NkZHFhbCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/G9qfCvxlwGAaQ/200.gif")

        # User's Pokemon
        user_hp_percent = (self.user_current_hp / self.user_max_hp) * 100
        user_hp_bar = pkmn.create_hp_bar(user_hp_percent)

        embed.add_field(
            name=f"Your {self.user_choice['pokemon_name']} (Lv.{self.user_choice['level']})",
            value=f"{user_hp_bar}\nHP: {self.user_current_hp}/{self.user_max_hp}",
            inline=True
        )

        # Trainer's Pokemon
        trainer_hp_percent = (self.trainer_current_hp / self.trainer_max_hp) * 100
        trainer_hp_bar = pkmn.create_hp_bar(trainer_hp_percent)

        # Show trainer's remaining Pokemon count
        remaining = len(self.trainer_team) - self.trainer_pokemon_index
        remaining_text = f" ({remaining}/{len(self.trainer_team)} remaining)" if len(self.trainer_team) > 1 else ""

        embed.add_field(
            name=f"{self.trainer['sprite']} {self.trainer_current_pokemon['pokemon_name']} (Lv.{self.trainer_current_pokemon['level']}){remaining_text}",
            value=f"{trainer_hp_bar}\nHP: {self.trainer_current_hp}/{self.trainer_max_hp}",
            inline=True
        )

        # Battle log
        log_text = "\n".join(self.battle_log[-5:])  # Last 5 actions
        if log_text:
            embed.add_field(name="📝 Battle Log", value=log_text, inline=False)

        embed.set_footer(text=f"Turn {self.turn_count}")

        return embed

    async def handle_victory(self, interaction: discord.Interaction):
        """Handle battle victory"""
        # Award wild Pokemon
        await db.add_catch(
            user_id=self.user.id,
            guild_id=self.guild_id,
            pokemon_name=self.wild_pokemon['name'],
            pokemon_id=self.wild_pokemon['id'],
            pokemon_types=self.wild_pokemon['types']
        )

        # Award money
        await db.add_currency(self.user.id, self.guild_id, self.trainer['reward_money'])

        # Award XP
        xp_gained = 50  # Fixed XP for trainer battles
        xp_result = await db.add_species_xp(
            self.user.id, self.guild_id,
            self.user_choice['pokemon_id'], self.user_choice['pokemon_name'],
            xp_gained, is_win=True
        )

        # Clear battle state from bot module
        import bot
        if self.user.id in bot.active_trainer_battles:
            del bot.active_trainer_battles[self.user.id]

        # Create victory embed
        embed = discord.Embed(
            title="🎉 Victory!",
            description=f"You defeated **{self.trainer['name']}**!",
            color=discord.Color.green()
        )

        embed.add_field(
            name="🏆 Rewards",
            value=f"• Caught **{self.wild_pokemon['name']}**!\n• Earned **₽{self.trainer['reward_money']}** Pokedollars!\n• **{self.user_choice['pokemon_name']}** gained **{xp_gained} XP**!",
            inline=False
        )

        if xp_result and xp_result.get('leveled_up'):
            embed.add_field(
                name="⬆️ Level Up!",
                value=f"**{self.user_choice['pokemon_name']}** leveled up to **Lv.{xp_result['new_level']}**!",
                inline=False
            )

        self.clear_items()
        if self.battle_message:
            await self.battle_message.edit(embed=embed, view=self)
        else:
            await interaction.followup.send(embed=embed)

    async def handle_defeat(self, interaction: discord.Interaction):
        """Handle battle defeat"""
        # Clear battle state from bot module
        import bot
        if self.user.id in bot.active_trainer_battles:
            del bot.active_trainer_battles[self.user.id]

        # Create defeat embed
        embed = discord.Embed(
            title="💔 Defeated...",
            description=f"You were defeated by **{self.trainer['name']}**!",
            color=discord.Color.red()
        )

        embed.add_field(
            name="",
            value=f"**{self.wild_pokemon['name']}** got away... Better luck next time!",
            inline=False
        )

        self.clear_items()
        if self.battle_message:
            await self.battle_message.edit(embed=embed, view=self)
        else:
            await interaction.followup.send(embed=embed)

    async def flee_battle(self, interaction: discord.Interaction):
        """Handle fleeing from battle"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your battle!", ephemeral=True)
            return

        await interaction.response.defer()

        # Clear battle state from bot module
        import bot
        if self.user.id in bot.active_trainer_battles:
            del bot.active_trainer_battles[self.user.id]

        # Create flee embed
        embed = discord.Embed(
            title="🏃 Fled from Battle!",
            description=f"You ran away from **{self.trainer['name']}**!",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="",
            value=f"**{self.wild_pokemon['name']}** escaped into the wild...",
            inline=False
        )

        self.clear_items()
        if self.battle_message:
            await self.battle_message.edit(embed=embed, view=self)
        else:
            await interaction.followup.send(embed=embed)
