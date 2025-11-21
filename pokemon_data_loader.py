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
    """Get Pokemon sprite URL - using official artwork for better quality"""
    base_url = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork"

    if shiny:
        return f"{base_url}/shiny/{pokemon_id}.png"
    return f"{base_url}/{pokemon_id}.png"


def get_pokemon_moves(pokemon_id: int, num_moves: int = 4, max_level: int = 100) -> List[Dict]:
    """
    Get random, varied moves for a Pokemon with weighted selection.
    Ensures Pokemon always have at least 1 attacking move, but allows for
    diverse movesets (all attacks, mixed, status-heavy, etc.)
    """
    pokemon = get_pokemon(pokemon_id)
    if not pokemon:
        # Pokemon data not found - this shouldn't happen if pokemon_data.json exists
        # But if it does, use type-appropriate defaults
        pokemon_types = ['normal']  # Default type
        return [
            {'name': 'Tackle', 'power': 40, 'accuracy': 100, 'type': pokemon_types[0], 'damage_class': 'physical'},
            {'name': 'Scratch', 'power': 40, 'accuracy': 100, 'type': pokemon_types[0], 'damage_class': 'physical'},
            {'name': 'Growl', 'power': 0, 'accuracy': 100, 'type': pokemon_types[0], 'damage_class': 'status'},
            {'name': 'Tail Whip', 'power': 0, 'accuracy': 100, 'type': pokemon_types[0], 'damage_class': 'status'}
        ]

    all_moves = pokemon.get('moves', [])
    
    # If no moves in data, use type-appropriate defaults
    if not all_moves:
        # No moves in data - try to use type-appropriate moves
        pokemon_types = pokemon.get('types', ['normal'])
        primary_type = pokemon_types[0] if pokemon_types else 'normal'
        
        # Use type-appropriate default moves instead of always normal
        type_defaults = {
            'fire': [{'name': 'Ember', 'power': 40, 'accuracy': 100, 'type': 'fire', 'damage_class': 'special'}],
            'water': [{'name': 'Water Gun', 'power': 40, 'accuracy': 100, 'type': 'water', 'damage_class': 'special'}],
            'grass': [{'name': 'Vine Whip', 'power': 45, 'accuracy': 100, 'type': 'grass', 'damage_class': 'physical'}],
            'electric': [{'name': 'Thunder Shock', 'power': 40, 'accuracy': 100, 'type': 'electric', 'damage_class': 'special'}],
            'psychic': [{'name': 'Confusion', 'power': 50, 'accuracy': 100, 'type': 'psychic', 'damage_class': 'special'}],
        }
        
        defaults = type_defaults.get(primary_type, [
            {'name': 'Tackle', 'power': 40, 'accuracy': 100, 'type': primary_type, 'damage_class': 'physical'}
        ])
        
        # Fill remaining slots
        while len(defaults) < num_moves:
            defaults.append({
                'name': 'Scratch',
                'power': 40,
                'accuracy': 100,
                'type': primary_type,
                'damage_class': 'physical'
            })
        
        return [{
            'name': m['name'].replace('-', ' ').title(),
            'power': m.get('power', 40),
            'accuracy': m.get('accuracy', 100),
            'type': m.get('type', primary_type),
            'damage_class': m.get('damage_class', 'physical')
        } for m in defaults[:num_moves]]

    # Filter moves by level (but be VERY lenient - prioritize having moves over level restrictions)
    # Strategy: Only apply level filtering if it leaves us with a good selection
    # Otherwise, ignore level restrictions to ensure variety
    
    # For very low levels (1-5), be extra lenient - most Pokemon learn moves later
    if max_level <= 5:
        # At low levels, ignore level restrictions entirely to ensure variety
        available_moves = all_moves
    else:
        # Try level filtering first
        level_filtered = [m for m in all_moves if m.get('learn_level', 0) <= max_level]
        
        # Use level-filtered moves only if:
        # 1. We have at least 6 moves after filtering, OR
        # 2. We have at least 60% of original moves after filtering
        if len(level_filtered) >= 6 or (len(all_moves) > 0 and len(level_filtered) >= len(all_moves) * 0.6):
            available_moves = level_filtered
        else:
            # Level filtering is too restrictive - use all moves regardless of level
            # This ensures Pokemon always have varied movesets
            available_moves = all_moves
    
    # If still no moves after all filtering, something is wrong with the data
    # But try to use type-appropriate defaults as last resort
    if not available_moves:
        pokemon_types = pokemon.get('types', ['normal'])
        primary_type = pokemon_types[0] if pokemon_types else 'normal'
        pokemon_name = pokemon.get('name', 'Unknown')
        
        # Log warning (only in debug mode - you can enable this if needed)
        # print(f"[WARNING] No moves found for {pokemon_name} (ID: {pokemon_id}), using defaults")
        
        return [
            {'name': 'Tackle', 'power': 40, 'accuracy': 100, 'type': primary_type, 'damage_class': 'physical'},
            {'name': 'Scratch', 'power': 40, 'accuracy': 100, 'type': primary_type, 'damage_class': 'physical'},
            {'name': 'Growl', 'power': 0, 'accuracy': 100, 'type': primary_type, 'damage_class': 'status'},
            {'name': 'Tail Whip', 'power': 0, 'accuracy': 100, 'type': primary_type, 'damage_class': 'status'}
        ]

    # Categorize moves - be more lenient with categorization
    attacking_moves = []
    status_moves = []
    
    for m in available_moves:
        # Get damage_class - handle None, empty string, or missing
        damage_class_raw = m.get('damage_class')
        if damage_class_raw:
            damage_class = str(damage_class_raw).lower().strip()
        else:
            damage_class = ''
        
        # Get power - handle None, 0, or missing
        power_raw = m.get('power')
        if power_raw is not None:
            try:
                power = int(power_raw)
            except (ValueError, TypeError):
                power = 0
        else:
            power = 0
        
        # Attacking moves: physical/special with power > 0
        if damage_class in ['physical', 'special'] and power > 0:
            attacking_moves.append(m)
        # Status moves: explicitly status OR power is 0
        elif damage_class == 'status' or power == 0:
            status_moves.append(m)
        # If damage_class is missing/empty but has power, treat as attack
        elif (not damage_class or damage_class == 'none') and power > 0:
            attacking_moves.append(m)
        # Otherwise, default to status
        else:
            status_moves.append(m)
    
    # Safety check: if we have moves but categorization failed, try harder
    if available_moves and not attacking_moves and not status_moves:
        # Something went wrong - just use all moves as-is
        attacking_moves = [m for m in available_moves if m.get('power', 0) > 0]
        status_moves = [m for m in available_moves if m not in attacking_moves]

    # Separate status moves into buffs and debuffs
    debuff_keywords = ['lower', 'reduce', 'poison', 'paralyze', 'burn', 'freeze', 'confuse', 'sleep', 'stun', 'disable']
    buff_keywords = ['raise', 'increase', 'sharpen', 'harden', 'defense', 'agility', 'swords', 'dance', 'bulk', 'calm', 'mind']

    buffs = []
    debuffs = []
    other_status = []  # Status moves that don't clearly fit buff/debuff
    
    for move in status_moves:
        move_name = move.get('name', '').lower()
        if any(keyword in move_name for keyword in buff_keywords):
            buffs.append(move)
        elif any(keyword in move_name for keyword in debuff_keywords):
            debuffs.append(move)
        else:
            other_status.append(move)

    # Ensure we have at least 1 attacking move
    selected_moves = []
    
    # Randomly decide moveset composition (weighted towards having attacks)
    # Strategy types:
    # 1. All-out attacker (3-4 attacks)
    # 2. Balanced (2-3 attacks, 1-2 status)
    # 3. Status specialist (1-2 attacks, 2-3 status)
    # 4. Mixed (varied)
    
    strategy_roll = random.random()
    
    if strategy_roll < 0.35:  # 35% chance - All-out attacker
        # 3-4 attacking moves
        num_attacks = random.choice([3, 4]) if len(attacking_moves) >= 3 else min(len(attacking_moves), num_moves)
        if num_attacks > 0:
            selected_moves.extend(random.sample(attacking_moves, min(num_attacks, len(attacking_moves))))
        # Fill remaining slots with random moves
        remaining = num_moves - len(selected_moves)
        if remaining > 0:
            all_other = buffs + debuffs + other_status
            if all_other:
                selected_moves.extend(random.sample(all_other, min(remaining, len(all_other))))
    
    elif strategy_roll < 0.70:  # 35% chance - Balanced
        # 2-3 attacks, 1-2 status
        num_attacks = random.choice([2, 3]) if len(attacking_moves) >= 2 else min(len(attacking_moves), num_moves - 1)
        if num_attacks > 0:
            selected_moves.extend(random.sample(attacking_moves, min(num_attacks, len(attacking_moves))))
        
        remaining = num_moves - len(selected_moves)
        if remaining > 0:
            status_pool = buffs + debuffs + other_status
            if status_pool:
                num_status = min(remaining, len(status_pool))
                selected_moves.extend(random.sample(status_pool, num_status))
    
    elif strategy_roll < 0.90:  # 20% chance - Status specialist
        # 1-2 attacks, 2-3 status
        num_attacks = random.choice([1, 2]) if len(attacking_moves) >= 1 else 0
        if num_attacks > 0:
            selected_moves.extend(random.sample(attacking_moves, min(num_attacks, len(attacking_moves))))
        
        remaining = num_moves - len(selected_moves)
        if remaining > 0:
            status_pool = buffs + debuffs + other_status
            if status_pool:
                num_status = min(remaining, len(status_pool))
                selected_moves.extend(random.sample(status_pool, num_status))
    
    else:  # 10% chance - Completely random
        # Just pick randomly from all moves
        all_moves_pool = attacking_moves + buffs + debuffs + other_status
        if all_moves_pool:
            # Ensure at least 1 attack
            if attacking_moves and not any(m.get('damage_class') in ['physical', 'special'] for m in selected_moves):
                selected_moves.append(random.choice(attacking_moves))
            # Fill rest randomly
            remaining = num_moves - len(selected_moves)
            if remaining > 0:
                pool = [m for m in all_moves_pool if m not in selected_moves]
                if pool:
                    selected_moves.extend(random.sample(pool, min(remaining, len(pool))))

    # Ensure we have at least 1 attacking move (critical for battle viability)
    has_attack = any(m.get('damage_class') in ['physical', 'special'] and (m.get('power') or 0) > 0 for m in selected_moves)
    if not has_attack and attacking_moves:
        # Replace a random move with an attack
        if selected_moves:
            selected_moves[random.randint(0, len(selected_moves) - 1)] = random.choice(attacking_moves)
        else:
            selected_moves.append(random.choice(attacking_moves))

    # If we still don't have enough moves, fill with defaults
    while len(selected_moves) < num_moves:
        if attacking_moves and not any(m.get('damage_class') in ['physical', 'special'] for m in selected_moves):
            selected_moves.append(random.choice(attacking_moves))
        else:
            # Add a default move
            default_move = {
                'name': 'tackle',
                'power': 40,
                'accuracy': 100,
                'type': pokemon.get('types', ['normal'])[0],
                'damage_class': 'physical'
            }
            selected_moves.append(default_move)

    # Shuffle the moveset for extra randomness
    random.shuffle(selected_moves)

    # Format moves for battle system
    formatted_moves = []
    for move in selected_moves[:num_moves]:
        formatted_moves.append({
            'name': move['name'].replace('-', ' ').title(),
            'power': move.get('power') or 0,
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


def get_pokemon_generation(pokemon_id: int) -> int:
    """Get Pokemon generation number based on ID"""
    if 1 <= pokemon_id <= 151:
        return 1
    elif 152 <= pokemon_id <= 251:
        return 2
    elif 252 <= pokemon_id <= 386:
        return 3
    elif 387 <= pokemon_id <= 493:
        return 4
    elif 494 <= pokemon_id <= 649:
        return 5
    elif 650 <= pokemon_id <= 721:
        return 6
    elif 722 <= pokemon_id <= 809:
        return 7
    elif 810 <= pokemon_id <= 905:
        return 8
    else:
        return 9


def get_generation_range(generation: int) -> tuple:
    """Get the ID range for a specific generation"""
    ranges = {
        1: (1, 151),
        2: (152, 251),
        3: (252, 386),
        4: (387, 493),
        5: (494, 649),
        6: (650, 721),
        7: (722, 809),
        8: (810, 905),
        9: (906, 1025)
    }
    return ranges.get(generation, (1, 151))


def has_local_data() -> bool:
    """Check if local Pokemon data is loaded"""
    return len(POKEMON_DATA) > 0


# Load data when module is imported
load_pokemon_data()
