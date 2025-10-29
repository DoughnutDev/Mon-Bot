"""
Fetch Gen 2 Pokemon data from PokeAPI and append to pokemon_data.json
Pokemon IDs: 152-251 (Chikorita to Celebi)

This script fetches data from PokeAPI and updates the existing pokemon_data.json file.
"""

import json
import asyncio
import aiohttp
from typing import Dict, List


async def fetch_pokemon_data(session: aiohttp.ClientSession, pokemon_id: int) -> Dict:
    """Fetch Pokemon data from PokeAPI"""
    url = f'https://pokeapi.co/api/v2/pokemon/{pokemon_id}'

    try:
        async with session.get(url) as response:
            if response.status != 200:
                print(f"Failed to fetch Pokemon {pokemon_id}: {response.status}")
                return None

            data = await response.json()

            # Extract relevant data
            pokemon_data = {
                'id': data['id'],
                'name': data['name'],
                'types': [t['type']['name'] for t in data['types']],
                'stats': {},
                'sprites': {
                    'front_default': data['sprites']['front_default'],
                    'front_shiny': data['sprites']['front_shiny']
                },
                'moves': []
            }

            # Extract stats
            for stat in data['stats']:
                stat_name = stat['stat']['name']
                pokemon_data['stats'][stat_name] = stat['base_stat']

            # Extract moves (only ones learned by level-up)
            for move_data in data['moves']:
                move_name = move_data['move']['name']

                # Find level-up learn method
                for version_detail in move_data['version_group_details']:
                    if version_detail['move_learn_method']['name'] == 'level-up':
                        learn_level = version_detail['level_learned_at']

                        # Fetch move details
                        move_url = move_data['move']['url']
                        async with session.get(move_url) as move_response:
                            if move_response.status == 200:
                                move_info = await move_response.json()

                                pokemon_data['moves'].append({
                                    'name': move_name,
                                    'power': move_info.get('power'),
                                    'accuracy': move_info.get('accuracy'),
                                    'pp': move_info.get('pp'),
                                    'type': move_info['type']['name'],
                                    'damage_class': move_info['damage_class']['name'],
                                    'learn_level': learn_level
                                })

                        break  # Only need one level-up entry

            print(f"[OK] Fetched {pokemon_data['name'].title()} (#{pokemon_id})")
            return pokemon_data

    except Exception as e:
        print(f"Error fetching Pokemon {pokemon_id}: {e}")
        return None


async def main():
    """Main function to fetch all Gen 2 Pokemon"""
    print("Fetching Gen 2 Pokemon data from PokeAPI...")
    print("This may take a few minutes...\n")

    # Load existing data
    try:
        with open('pokemon_data.json', 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
        print(f"Loaded {len(existing_data)} existing Pokemon\n")
    except FileNotFoundError:
        print("No existing pokemon_data.json found, creating new file\n")
        existing_data = {}

    # Fetch Gen 2 Pokemon (152-251)
    async with aiohttp.ClientSession() as session:
        tasks = []
        for pokemon_id in range(152, 252):  # 152 to 251 inclusive
            tasks.append(fetch_pokemon_data(session, pokemon_id))

            # Add small delay every 10 requests to avoid rate limiting
            if len(tasks) % 10 == 0:
                results = await asyncio.gather(*tasks)
                tasks = []

                # Add successful results to existing data
                for result in results:
                    if result:
                        existing_data[str(result['id'])] = result

                await asyncio.sleep(1)  # Rate limiting

        # Process remaining tasks
        if tasks:
            results = await asyncio.gather(*tasks)
            for result in results:
                if result:
                    existing_data[str(result['id'])] = result

    # Save updated data
    with open('pokemon_data.json', 'w', encoding='utf-8') as f:
        json.dump(existing_data, f, indent=2)

    print(f"\n[SUCCESS] Successfully saved {len(existing_data)} Pokemon to pokemon_data.json")
    print(f"   Gen 1: 1-151")
    print(f"   Gen 2: 152-251")


if __name__ == '__main__':
    asyncio.run(main())
