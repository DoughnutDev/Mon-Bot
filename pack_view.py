"""
Pack Selection View - UI for selecting and opening Pokemon packs
"""

import discord
from discord.ui import View, Button, Select
import json
import random
import aiohttp
import database as db
import pokemon_data_loader as poke_data


async def fetch_pokemon(session, pokemon_id=None):
    """Fetch a random or specific Pokemon from PokeAPI"""
    if pokemon_id is None:
        pokemon_id = random.randint(1, 151)  # Gen 1 only

    try:
        pokemon_data = poke_data.get_pokemon_data(pokemon_id)
        if pokemon_data:
            return {
                'id': pokemon_data['id'],
                'name': pokemon_data['name'].title(),
                'types': [t['type']['name'] for t in pokemon_data['types']]
            }
    except:
        pass

    # Fallback to API
    try:
        async with session.get(f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}') as response:
            if response.status == 200:
                data = await response.json()
                return {
                    'id': data['id'],
                    'name': data['name'].title(),
                    'types': [t['type']['name'] for t in data['types']]
                }
    except:
        pass

    return None


class PackSelectionView(View):
    """View for selecting and opening packs"""

    def __init__(self, user: discord.Member, guild_id: int, user_packs: list):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user = user
        self.guild_id = guild_id
        self.user_packs = user_packs

        # Parse all pack configs
        self.parsed_packs = []
        for pack in user_packs:
            config = None
            if isinstance(pack['pack_config'], str):
                try:
                    config = json.loads(pack['pack_config'])
                except (json.JSONDecodeError, TypeError):
                    continue
            elif isinstance(pack['pack_config'], dict):
                config = pack['pack_config']
            else:
                continue

            if config and isinstance(config, dict):
                self.parsed_packs.append({**pack, 'parsed_config': config})

        # Add dropdown for pack selection
        if self.parsed_packs:
            self.create_pack_dropdown()

    def create_inventory_embed(self):
        """Create embed showing all available packs"""
        embed = discord.Embed(
            title="📦 Your Pokemon Packs",
            description="Select a pack to open from the dropdown below, or open all packs at once!",
            color=discord.Color.blue()
        )

        # Group packs by type and count them
        pack_counts = {}
        for pack in self.parsed_packs:
            name = pack['pack_name']
            if name not in pack_counts:
                pack_counts[name] = {'count': 0, 'config': pack['parsed_config']}
            pack_counts[name]['count'] += 1

        # Show pack inventory
        inventory_text = ""
        for pack_name, data in pack_counts.items():
            config = data['config']
            count = data['count']
            min_poke = config.get('min_pokemon', 0)
            max_poke = config.get('max_pokemon', 0)
            shiny = config.get('shiny_chance', 0) * 100

            inventory_text += f"**{pack_name}** ×{count}\n"
            inventory_text += f"└ {min_poke}-{max_poke} Pokemon • {shiny}% shiny chance\n\n"

        embed.add_field(
            name="📋 Pack Inventory",
            value=inventory_text.strip() or "No packs available",
            inline=False
        )

        embed.set_footer(text=f"Total packs: {len(self.parsed_packs)}")

        return embed

    def create_pack_dropdown(self):
        """Create dropdown menu for pack selection"""
        options = []
        added_pack_ids = []

        for pack in self.parsed_packs[:25]:  # Discord limit
            # Add each unique pack
            if pack['id'] not in added_pack_ids:
                config = pack['parsed_config']
                label = f"{pack['pack_name']}"
                desc = f"{config.get('min_pokemon', 0)}-{config.get('max_pokemon', 0)} Pokemon"

                options.append(discord.SelectOption(
                    label=label[:100],
                    value=str(pack['id']),
                    description=desc[:100]
                ))
                added_pack_ids.append(pack['id'])

        if options:
            pack_select = Select(
                placeholder="Choose a pack to open...",
                options=options
            )
            pack_select.callback = self.pack_selected
            self.add_item(pack_select)

    @discord.ui.button(label="📦 Open All Packs", style=discord.ButtonStyle.success, row=1)
    async def open_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open all packs at once"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ These aren't your packs!", ephemeral=True)
            return

        await interaction.response.defer()

        # Open all packs
        all_pokemon = []
        total_shinies = 0
        total_legendaries = 0
        packs_opened = 0
        legendary_ids = [144, 145, 146, 150, 151]

        for pack in self.parsed_packs:
            pack_result = await self.open_pack(pack['id'], pack['parsed_config'])
            if pack_result:
                all_pokemon.extend(pack_result['pokemon'])
                total_shinies += sum(1 for p in pack_result['pokemon'] if p.get('is_shiny'))
                total_legendaries += sum(1 for p in pack_result['pokemon'] if p['id'] in legendary_ids)
                packs_opened += 1

        # Create summary embed
        embed = discord.Embed(
            title=f"🎉 Opened {packs_opened} Packs!",
            description=f"You received **{len(all_pokemon)} Pokemon**!",
            color=discord.Color.gold()
        )

        if total_shinies > 0:
            embed.add_field(name="✨ Shinies", value=f"**{total_shinies}** shiny Pokemon!", inline=True)

        if total_legendaries > 0:
            embed.add_field(name="👑 Legendaries", value=f"**{total_legendaries}** legendary Pokemon!", inline=True)

        # Show sample of Pokemon (first 15)
        if all_pokemon:
            sample = all_pokemon[:15]
            pokemon_list = []
            for p in sample:
                markers = ""
                if p.get('is_shiny'):
                    markers += " ✨"
                if p['id'] in legendary_ids:
                    markers += " 👑"
                pokemon_list.append(f"#{p['id']:03d} {p['name']}{markers}")

            pokemon_text = "\n".join(pokemon_list)
            if len(all_pokemon) > 15:
                pokemon_text += f"\n\n... and {len(all_pokemon) - 15} more!"

            embed.add_field(name="🎁 Pokemon Received", value=pokemon_text, inline=False)

        # Update quest progress
        await db.update_quest_progress(self.user.id, self.guild_id, 'open_packs')

        self.clear_items()
        await interaction.followup.send(embed=embed, view=self)

    async def pack_selected(self, interaction: discord.Interaction):
        """Handle pack selection from dropdown"""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ These aren't your packs!", ephemeral=True)
            return

        await interaction.response.defer()

        # Get selected pack ID
        pack_id = int(interaction.data['values'][0])

        # Find the pack config
        pack = next((p for p in self.parsed_packs if p['id'] == pack_id), None)
        if not pack:
            await interaction.followup.send("❌ Pack not found!", ephemeral=True)
            return

        # Open the pack
        result = await self.open_pack(pack_id, pack['parsed_config'])

        if not result:
            await interaction.followup.send("❌ Failed to open pack!", ephemeral=True)
            return

        # Create result embed
        is_mega = result.get('is_mega', False)
        has_shiny = any(p.get('is_shiny') for p in result['pokemon'])
        legendary_ids = [144, 145, 146, 150, 151]
        legendary_count = sum(1 for p in result['pokemon'] if p['id'] in legendary_ids)

        title = "🎉 MEGA PACK! 🎉" if is_mega else f"📦 {pack['pack_name']} Opened!"
        if has_shiny:
            title = "✨ SHINY PACK! ✨"

        # Color based on pack type
        colors = {
            'Basic Pack': discord.Color.light_grey(),
            'Booster Pack': discord.Color.green(),
            'Premium Pack': discord.Color.blue(),
            'Elite Trainer Pack': discord.Color.purple(),
            'Master Collection': discord.Color.gold()
        }
        color = colors.get(pack['pack_name'], discord.Color.gold())
        if has_shiny:
            color = discord.Color.purple()

        embed = discord.Embed(
            title=title,
            description=f"You got **{len(result['pokemon'])}** Pokemon!",
            color=color
        )

        # List Pokemon
        pokemon_list = []
        for p in result['pokemon']:
            markers = ""
            if p.get('is_shiny'):
                markers += " ✨"
            if p['id'] in legendary_ids:
                markers += " 👑"
            pokemon_list.append(f"#{p['id']:03d} {p['name']}{markers}")

        # Display in columns if needed
        if len(pokemon_list) <= 10:
            embed.add_field(name="Pokemon Caught", value='\n'.join(pokemon_list), inline=False)
        else:
            mid = len(pokemon_list) // 2
            embed.add_field(name=f"Pokemon (1-{mid})", value='\n'.join(pokemon_list[:mid]), inline=True)
            embed.add_field(name=f"Pokemon ({mid+1}-{len(pokemon_list)})", value='\n'.join(pokemon_list[mid:]), inline=True)

        # Show special pulls
        if has_shiny or legendary_count > 0:
            special = []
            if has_shiny:
                special.append("✨ **SHINY POKEMON!**")
            if legendary_count > 0:
                special.append(f"👑 **{legendary_count} Legendary Pokemon!**")
            embed.add_field(name="🌟 Special Pulls", value='\n'.join(special), inline=False)

        # Update quest
        await db.update_quest_progress(self.user.id, self.guild_id, 'open_packs')

        # Show remaining packs
        remaining = await db.get_pack_count(self.user.id, self.guild_id)
        pack_word = 'pack' if remaining == 1 else 'packs'
        embed.set_footer(text=f"Remaining packs: {remaining} {pack_word}")

        await interaction.followup.send(embed=embed)

    async def open_pack(self, pack_id: int, config: dict):
        """Open a single pack and return the result"""
        # Use the pack (removes it from inventory)
        pack_data = await db.use_pack(self.user.id, self.guild_id, pack_id)

        if not pack_data:
            return None

        # Determine pack size
        min_poke = config.get('min_pokemon', 3)
        max_poke = config.get('max_pokemon', 5)
        mega_chance = config.get('mega_pack_chance', 0)
        mega_size = config.get('mega_pack_size', 0)

        # Check for mega pack
        is_mega = False
        if mega_chance > 0 and random.random() < mega_chance:
            pack_size = mega_size
            is_mega = True
        else:
            pack_size = random.randint(min_poke, max_poke)

        # Generate Pokemon
        pokemon_list = []
        legendary_count = 0
        legendary_ids = [144, 145, 146, 150, 151]

        async with aiohttp.ClientSession() as session:
            for _ in range(pack_size):
                # Check for forced legendary
                force_legendary = False
                if config.get('guaranteed_rare') and legendary_count < config.get('guaranteed_rare_count', 1):
                    if random.random() < config.get('legendary_chance', 0.1) * 2:
                        force_legendary = True

                if force_legendary:
                    pokemon_id = random.choice(legendary_ids)
                    pokemon = await fetch_pokemon(session, pokemon_id)
                else:
                    pokemon = await fetch_pokemon(session)

                if pokemon:
                    # Shiny check
                    pokemon['is_shiny'] = random.random() < config.get('shiny_chance', 0.01)

                    if pokemon['id'] in legendary_ids:
                        legendary_count += 1

                    pokemon_list.append(pokemon)

                    # Add to user's collection
                    await db.add_catch(
                        user_id=self.user.id,
                        guild_id=self.guild_id,
                        pokemon_name=pokemon['name'],
                        pokemon_id=pokemon['id'],
                        pokemon_types=pokemon['types']
                    )

        return {
            'pokemon': pokemon_list,
            'is_mega': is_mega
        }
