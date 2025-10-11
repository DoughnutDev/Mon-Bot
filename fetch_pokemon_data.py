"""
Fetch Pokemon data from PokeAPI and store locally
Run this script once to generate pokemon_data.json

Pokemon data sourced from PokeAPI (https://pokeapi.co)
PokeAPI is licensed under BSD 3-Clause License
"""

import aiohttp
import asyncio
import json
from typing import Dict, List

# Gen 1 Pokemon IDs (1-151)
GEN1_POKEMON = list(range(1, 152))

async def fetch_pokemon_data(session: aiohttp.ClientSession, pokemon_id: int) -> Dict:
    """Fetch complete Pokemon data from PokeAPI"""
    try:
        async with session.get(f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}') as resp:
            if resp.status != 200:
                print(f"Failed to fetch Pokemon {pokemon_id}: {resp.status}")
                return None

            data = await resp.json()

            # Extract only what we need
            pokemon_data = {
                'id': data['id'],
                'name': data['name'],
                'types': [t['type']['name'] for t in data['types']],
                'stats': {stat['stat']['name']: stat['base_stat'] for stat in data['stats']},
                'sprites': {
                    'front_default': data['sprites']['front_default'],
                    'front_shiny': data['sprites']['front_shiny']
                },
                'moves': []
            }

            # Get level-up moves only (for battles)
            level_up_moves = []
            for move_data in data['moves']:
                for version_detail in move_data['version_group_details']:
                    if version_detail['move_learn_method']['name'] == 'level-up':
                        level_up_moves.append({
                            'name': move_data['move']['name'],
                            'url': move_data['move']['url'],
                            'learn_level': version_detail['level_learned_at']
                        })
                        break

            # Fetch move details (in batches to avoid overwhelming the API)
            for move in level_up_moves[:30]:  # Limit to 30 moves per Pokemon
                try:
                    async with session.get(move['url']) as move_resp:
                        if move_resp.status == 200:
                            move_details = await move_resp.json()
                            pokemon_data['moves'].append({
                                'name': move_details['name'],
                                'power': move_details['power'],
                                'accuracy': move_details['accuracy'],
                                'pp': move_details['pp'],
                                'type': move_details['type']['name'],
                                'damage_class': move_details['damage_class']['name'],
                                'learn_level': move['learn_level']
                            })
                    # Small delay to be nice to the API
                    await asyncio.sleep(0.1)
                except Exception as e:
                    print(f"Failed to fetch move {move['name']}: {e}")
                    continue

            print(f"[OK] Fetched {data['name'].title()} ({pokemon_id}/151) with {len(pokemon_data['moves'])} moves")
            return pokemon_data

    except Exception as e:
        print(f"Error fetching Pokemon {pokemon_id}: {e}")
        return None


async def main():
    """Fetch all Gen 1 Pokemon data"""
    print("Fetching Gen 1 Pokemon data from PokeAPI...")
    print("This will take a few minutes...\n")

    all_pokemon = {}

    async with aiohttp.ClientSession() as session:
        # Fetch Pokemon one by one to avoid rate limiting
        for pokemon_id in GEN1_POKEMON:
            pokemon_data = await fetch_pokemon_data(session, pokemon_id)
            if pokemon_data:
                all_pokemon[str(pokemon_id)] = pokemon_data

            # Delay between Pokemon to be nice to the API
            await asyncio.sleep(0.5)

    # Save to JSON file
    output_file = 'pokemon_data.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_pokemon, f, indent=2)

    print(f"\n[SUCCESS] Saved {len(all_pokemon)} Pokemon to {output_file}")
    print(f"File size: {len(json.dumps(all_pokemon)) / 1024:.2f} KB")


if __name__ == '__main__':
    asyncio.run(main())
