"""
Pokemon data loader - uses local JSON file instead of PokeAPI calls

Pokemon data sourced from PokeAPI (https://pokeapi.co)
PokeAPI is licensed under BSD 3-Clause License
"""

import json
import random
from typing import Dict, List, Optional

# Load Pokemon data once at module import
POKEMON_DATA: Dict = {}

def load_pokemon_data():
    """Load Pokemon data from local JSON file"""
    global POKEMON_DATA
    try:
        with open('pokemon_data.json', 'r', encoding='utf-8') as f:
            POKEMON_DATA = json.load(f)
        print(f"[OK] Loaded {len(POKEMON_DATA)} Pokemon from local data")
    except FileNotFoundError:
        print("[WARNING] pokemon_data.json not found. Run: python fetch_pokemon_data.py")
        POKEMON_DATA = {}
    except Exception as e:
        print(f"[ERROR] Error loading Pokemon data: {e}")
        POKEMON_DATA = {}


def get_pokemon(pokemon_id: int) -> Optional[Dict]:
    """Get Pokemon data by ID from local storage"""
    return POKEMON_DATA.get(str(pokemon_id))


def get_pokemon_types(pokemon_id: int) -> List[str]:
    """Get Pokemon types"""
    pokemon = get_pokemon(pokemon_id)
    if pokemon:
        return pokemon.get('types', ['normal'])
    return ['normal']


def get_pokemon_stats(pokemon_id: int) -> Dict:
    """Get Pokemon base stats"""
    pokemon = get_pokemon(pokemon_id)
    if pokemon:
        return pokemon.get('stats', {})
    return {}


def get_pokemon_sprite(pokemon_id: int, shiny: bool = False) -> Optional[str]:
    """Get Pokemon sprite URL"""
    pokemon = get_pokemon(pokemon_id)
    if pokemon:
        sprites = pokemon.get('sprites', {})
        return sprites.get('front_shiny' if shiny else 'front_default')
    return None


def get_pokemon_moves(pokemon_id: int, num_moves: int = 4, max_level: int = 100) -> List[Dict]:
    """Get random moves for a Pokemon that can be learned at or below max_level"""
    pokemon = get_pokemon(pokemon_id)
    if not pokemon:
        # Fallback to Tackle if no data
        return [{
            'name': 'Tackle',
            'power': 40,
            'accuracy': 100,
            'type': 'normal',
            'damage_class': 'physical'
        }]

    all_moves = pokemon.get('moves', [])

    # Filter moves by level (only include moves learnable at or below max_level)
    available_moves = [m for m in all_moves if m.get('learn_level', 1) <= max_level]

    if not available_moves:
        # If no moves available, use all moves
        available_moves = all_moves

    if not available_moves:
        # Ultimate fallback
        return [{
            'name': 'Tackle',
            'power': 40,
            'accuracy': 100,
            'type': 'normal',
            'damage_class': 'physical'
        }]

    # Pick random moves
    if len(available_moves) > num_moves:
        selected_moves = random.sample(available_moves, num_moves)
    else:
        selected_moves = available_moves

    # Format moves for battle system
    formatted_moves = []
    for move in selected_moves:
        formatted_moves.append({
            'name': move['name'].replace('-', ' ').title(),
            'power': move.get('power') or 40,
            'accuracy': move.get('accuracy') or 100,
            'type': move.get('type', 'normal'),
            'damage_class': move.get('damage_class', 'physical')
        })

    return formatted_moves


def get_pokemon_name(pokemon_id: int) -> str:
    """Get Pokemon name"""
    pokemon = get_pokemon(pokemon_id)
    if pokemon:
        return pokemon.get('name', 'Unknown').title()
    return 'Unknown'


def has_local_data() -> bool:
    """Check if local Pokemon data is loaded"""
    return len(POKEMON_DATA) > 0


# Load data when module is imported
load_pokemon_data()
