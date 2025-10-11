# Gen 1 Pokemon Base Stats (ID: {HP, Attack, Defense, Speed})
# Simplified for basic battle system

POKEMON_BASE_STATS = {
    # Starter lines
    1: {'hp': 45, 'attack': 49, 'defense': 49, 'speed': 45},  # Bulbasaur
    2: {'hp': 60, 'attack': 62, 'defense': 63, 'speed': 60},  # Ivysaur
    3: {'hp': 80, 'attack': 82, 'defense': 83, 'speed': 80},  # Venusaur
    4: {'hp': 39, 'attack': 52, 'defense': 43, 'speed': 65},  # Charmander
    5: {'hp': 58, 'attack': 64, 'defense': 58, 'speed': 80},  # Charmeleon
    6: {'hp': 78, 'attack': 84, 'defense': 78, 'speed': 100}, # Charizard
    7: {'hp': 44, 'attack': 48, 'defense': 65, 'speed': 43},  # Squirtle
    8: {'hp': 59, 'attack': 63, 'defense': 80, 'speed': 58},  # Wartortle
    9: {'hp': 79, 'attack': 83, 'defense': 100, 'speed': 78}, # Blastoise

    # Common Pokemon
    10: {'hp': 45, 'attack': 30, 'defense': 35, 'speed': 45}, # Caterpie
    16: {'hp': 40, 'attack': 45, 'defense': 40, 'speed': 56}, # Pidgey
    19: {'hp': 30, 'attack': 56, 'defense': 35, 'speed': 72}, # Rattata
    25: {'hp': 35, 'attack': 55, 'defense': 40, 'speed': 90}, # Pikachu

    # Popular Pokemon
    133: {'hp': 55, 'attack': 55, 'defense': 50, 'speed': 55}, # Eevee
    143: {'hp': 160, 'attack': 110, 'defense': 65, 'speed': 30}, # Snorlax

    # Legendaries
    144: {'hp': 90, 'attack': 85, 'defense': 100, 'speed': 85}, # Articuno
    145: {'hp': 90, 'attack': 90, 'defense': 85, 'speed': 100}, # Zapdos
    146: {'hp': 90, 'attack': 100, 'defense': 90, 'speed': 90}, # Moltres
    150: {'hp': 106, 'attack': 110, 'defense': 90, 'speed': 130}, # Mewtwo
    151: {'hp': 100, 'attack': 100, 'defense': 100, 'speed': 100}, # Mew
}

# Fallback stats for Pokemon not in the list
DEFAULT_STATS = {'hp': 50, 'attack': 50, 'defense': 50, 'speed': 50}

# Type chart (attacker_type -> [defender_types that take 2x damage])
TYPE_ADVANTAGES = {
    'fire': ['grass', 'bug', 'ice', 'steel'],
    'water': ['fire', 'ground', 'rock'],
    'grass': ['water', 'ground', 'rock'],
    'electric': ['water', 'flying'],
    'ice': ['grass', 'ground', 'flying', 'dragon'],
    'fighting': ['normal', 'ice', 'rock', 'dark', 'steel'],
    'poison': ['grass', 'fairy'],
    'ground': ['fire', 'electric', 'poison', 'rock', 'steel'],
    'flying': ['grass', 'fighting', 'bug'],
    'psychic': ['fighting', 'poison'],
    'bug': ['grass', 'psychic', 'dark'],
    'rock': ['fire', 'ice', 'flying', 'bug'],
    'ghost': ['psychic', 'ghost'],
    'dragon': ['dragon'],
    'dark': ['psychic', 'ghost'],
    'steel': ['ice', 'rock', 'fairy'],
    'fairy': ['fighting', 'dragon', 'dark'],
    'normal': [],
}

# Type chart resistances (attacker_type -> [defender_types that take 0.5x damage])
TYPE_RESISTANCES = {
    'fire': ['fire', 'water', 'rock', 'dragon'],
    'water': ['water', 'grass', 'dragon'],
    'grass': ['fire', 'grass', 'poison', 'flying', 'bug', 'dragon', 'steel'],
    'electric': ['electric', 'grass', 'dragon'],
    'ice': ['fire', 'water', 'ice', 'steel'],
    'fighting': ['poison', 'flying', 'psychic', 'bug', 'fairy'],
    'poison': ['poison', 'ground', 'rock', 'ghost'],
    'ground': ['grass', 'bug'],
    'flying': ['electric', 'rock', 'steel'],
    'psychic': ['psychic', 'steel'],
    'bug': ['fire', 'fighting', 'poison', 'flying', 'ghost', 'steel', 'fairy'],
    'rock': ['fighting', 'ground', 'steel'],
    'ghost': ['dark'],
    'dragon': ['steel'],
    'dark': ['fighting', 'dark', 'fairy'],
    'steel': ['fire', 'water', 'electric', 'steel'],
    'fairy': ['fire', 'poison', 'steel'],
    'normal': ['rock', 'steel'],
}

# Type immunities (attacker_type -> [defender_types that take 0x damage])
TYPE_IMMUNITIES = {
    'normal': ['ghost'],
    'fighting': ['ghost'],
    'poison': ['steel'],
    'ground': ['flying'],
    'ghost': ['normal'],
    'electric': ['ground'],
    'psychic': ['dark'],
    'dragon': ['fairy'],
}


def get_pokemon_stats(pokemon_id: int) -> dict:
    """Get base stats for a Pokemon"""
    return POKEMON_BASE_STATS.get(pokemon_id, DEFAULT_STATS).copy()


def calculate_battle_stats(base_stats: dict, level: int) -> dict:
    """Calculate battle stats based on base stats and level"""
    return {
        'hp': base_stats.get('hp', 50) + (level * 2),
        'attack': base_stats.get('attack', 50) + int(level * 1.5),
        'defense': base_stats.get('defense', 50) + level,
        'speed': base_stats.get('speed', 50),
        'special-attack': base_stats.get('special-attack', base_stats.get('attack', 50)) + int(level * 1.5),
        'special-defense': base_stats.get('special-defense', base_stats.get('defense', 50)) + level
    }


def create_hp_bar(hp_percent: float) -> str:
    """Create a visual HP bar"""
    filled = int(hp_percent / 10)
    empty = 10 - filled

    if hp_percent > 50:
        return f"{'🟩' * filled}{'⬜' * empty}"
    elif hp_percent > 25:
        return f"{'🟨' * filled}{'⬜' * empty}"
    else:
        return f"{'🟥' * filled}{'⬜' * empty}"


# Stat stage multipliers (from -6 to +6)
STAT_STAGE_MULTIPLIERS = {
    -6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
    0: 1.0,
    1: 3/2, 2: 4/2, 3: 5/2, 4: 6/2, 5: 7/2, 6: 8/2
}


def get_stat_stage_multiplier(stage: int) -> float:
    """Get multiplier for a stat stage"""
    stage = max(-6, min(6, stage))  # Clamp between -6 and +6
    return STAT_STAGE_MULTIPLIERS[stage]


def apply_stat_stages(base_stat: int, stage: int) -> int:
    """Apply stat stage modifier to a base stat"""
    multiplier = get_stat_stage_multiplier(stage)
    return int(base_stat * multiplier)


# Status condition effects
STATUS_CONDITIONS = {
    'burn': {
        'name': 'Burn',
        'emoji': '🔥',
        'damage_percent': 0.0625,  # 1/16 HP per turn
        'attack_modifier': 0.5  # Halves physical attack
    },
    'paralysis': {
        'name': 'Paralysis',
        'emoji': '⚡',
        'speed_modifier': 0.25,  # Speed reduced to 25%
        'immobilize_chance': 0.25  # 25% chance to be unable to move
    },
    'sleep': {
        'name': 'Sleep',
        'emoji': '💤',
        'min_turns': 1,
        'max_turns': 3,
        'immobilized': True
    },
    'poison': {
        'name': 'Poison',
        'emoji': '☠️',
        'damage_percent': 0.125  # 1/8 HP per turn
    },
    'badly_poison': {
        'name': 'Badly Poisoned',
        'emoji': '☠️☠️',
        'damage_increases': True,  # Damage increases each turn
        'base_damage': 0.0625  # 1/16 HP base, increases by 1/16 each turn
    },
    'freeze': {
        'name': 'Freeze',
        'emoji': '❄️',
        'immobilized': True,
        'thaw_chance': 0.20  # 20% chance to thaw each turn
    }
}


def get_status_condition_effect(status: str) -> dict:
    """Get status condition effects"""
    return STATUS_CONDITIONS.get(status, None)


# Move effect types for stat changes
STAT_CHANGE_MOVES = {
    # Buff moves (raise user's stats)
    'swords dance': {'target': 'user', 'stat': 'attack', 'stages': 2},
    'nasty plot': {'target': 'user', 'stat': 'special-attack', 'stages': 2},
    'dragon dance': {'target': 'user', 'stat': 'attack', 'stages': 1, 'secondary': {'stat': 'speed', 'stages': 1}},
    'calm mind': {'target': 'user', 'stat': 'special-attack', 'stages': 1, 'secondary': {'stat': 'special-defense', 'stages': 1}},
    'bulk up': {'target': 'user', 'stat': 'attack', 'stages': 1, 'secondary': {'stat': 'defense', 'stages': 1}},
    'iron defense': {'target': 'user', 'stat': 'defense', 'stages': 2},
    'amnesia': {'target': 'user', 'stat': 'special-defense', 'stages': 2},
    'agility': {'target': 'user', 'stat': 'speed', 'stages': 2},
    'harden': {'target': 'user', 'stat': 'defense', 'stages': 1},
    'withdraw': {'target': 'user', 'stat': 'defense', 'stages': 1},
    'defense curl': {'target': 'user', 'stat': 'defense', 'stages': 1},
    'sharpen': {'target': 'user', 'stat': 'attack', 'stages': 1},
    'meditate': {'target': 'user', 'stat': 'attack', 'stages': 1},
    'double team': {'target': 'user', 'stat': 'evasion', 'stages': 1},
    'minimize': {'target': 'user', 'stat': 'evasion', 'stages': 2},

    # Debuff moves (lower opponent's stats)
    'growl': {'target': 'opponent', 'stat': 'attack', 'stages': -1},
    'leer': {'target': 'opponent', 'stat': 'defense', 'stages': -1},
    'tail whip': {'target': 'opponent', 'stat': 'defense', 'stages': -1},
    'sand attack': {'target': 'opponent', 'stat': 'accuracy', 'stages': -1},
    'smokescreen': {'target': 'opponent', 'stat': 'accuracy', 'stages': -1},
    'flash': {'target': 'opponent', 'stat': 'accuracy', 'stages': -1},
    'sweet scent': {'target': 'opponent', 'stat': 'evasion', 'stages': -2},
    'charm': {'target': 'opponent', 'stat': 'attack', 'stages': -2},
    'feather dance': {'target': 'opponent', 'stat': 'attack', 'stages': -2},
    'scary face': {'target': 'opponent', 'stat': 'speed', 'stages': -2},
    'string shot': {'target': 'opponent', 'stat': 'speed', 'stages': -2},
}


def get_move_stat_changes(move_name: str) -> dict:
    """Get stat changes for a move"""
    move_name = move_name.lower()
    return STAT_CHANGE_MOVES.get(move_name, None)


def get_type_effectiveness(attacker_types: list, defender_types: list) -> float:
    """Calculate type effectiveness multiplier"""
    multiplier = 1.0

    for atk_type in attacker_types:
        atk_type = atk_type.lower()

        for def_type in defender_types:
            def_type = def_type.lower()

            # Check immunity
            if def_type in TYPE_IMMUNITIES.get(atk_type, []):
                return 0.0

            # Check advantage
            if def_type in TYPE_ADVANTAGES.get(atk_type, []):
                multiplier *= 2.0

            # Check resistance
            elif def_type in TYPE_RESISTANCES.get(atk_type, []):
                multiplier *= 0.5

    return multiplier
