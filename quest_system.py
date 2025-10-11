# Daily Quest System
import random
from datetime import date
from typing import Dict, List, Optional

# Quest type definitions with targets and rewards
QUEST_TYPES = {
    # General catching quests
    'catch_pokemon': {
        'variants': [
            {'target': 3, 'reward': 30, 'description': 'Catch 3 Pokemon'},
            {'target': 5, 'reward': 50, 'description': 'Catch 5 Pokemon'},
            {'target': 10, 'reward': 100, 'description': 'Catch 10 Pokemon'},
            {'target': 15, 'reward': 150, 'description': 'Catch 15 Pokemon'},
        ]
    },

    # Type-specific catching quests
    'catch_fire': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Fire-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Fire-type Pokemon'},
        ]
    },
    'catch_water': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Water-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Water-type Pokemon'},
        ]
    },
    'catch_grass': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Grass-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Grass-type Pokemon'},
        ]
    },
    'catch_electric': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Electric-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Electric-type Pokemon'},
        ]
    },
    'catch_psychic': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Psychic-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Psychic-type Pokemon'},
        ]
    },
    'catch_dragon': {
        'variants': [
            {'target': 1, 'reward': 80, 'description': 'Catch a Dragon-type Pokemon'},
            {'target': 2, 'reward': 150, 'description': 'Catch 2 Dragon-type Pokemon'},
        ]
    },
    'catch_ghost': {
        'variants': [
            {'target': 1, 'reward': 50, 'description': 'Catch a Ghost-type Pokemon'},
            {'target': 2, 'reward': 90, 'description': 'Catch 2 Ghost-type Pokemon'},
        ]
    },

    # Unique Pokemon quests
    'catch_unique': {
        'variants': [
            {'target': 3, 'reward': 60, 'description': 'Catch 3 different Pokemon species'},
            {'target': 5, 'reward': 100, 'description': 'Catch 5 different Pokemon species'},
        ]
    },

    # Legendary quests
    'catch_legendary': {
        'variants': [
            {'target': 1, 'reward': 200, 'description': 'Catch a legendary Pokemon'},
        ]
    },

    # Battle quests
    'win_battles': {
        'variants': [
            {'target': 1, 'reward': 50, 'description': 'Win 1 battle'},
            {'target': 2, 'reward': 100, 'description': 'Win 2 battles'},
            {'target': 3, 'reward': 150, 'description': 'Win 3 battles'},
            {'target': 5, 'reward': 250, 'description': 'Win 5 battles'},
        ]
    },

    # Pack quests
    'open_packs': {
        'variants': [
            {'target': 1, 'reward': 25, 'description': 'Open 1 pack'},
            {'target': 2, 'reward': 50, 'description': 'Open 2 packs'},
            {'target': 3, 'reward': 75, 'description': 'Open 3 packs'},
        ]
    },

    # Trading quests
    'complete_trade': {
        'variants': [
            {'target': 1, 'reward': 75, 'description': 'Complete 1 trade'},
            {'target': 2, 'reward': 150, 'description': 'Complete 2 trades'},
        ]
    },

    # Economy quests
    'earn_pokedollars': {
        'variants': [
            {'target': 100, 'reward': 50, 'description': 'Earn ₽100 Pokedollars'},
            {'target': 250, 'reward': 100, 'description': 'Earn ₽250 Pokedollars'},
            {'target': 500, 'reward': 150, 'description': 'Earn ₽500 Pokedollars'},
        ]
    },
    'sell_pokemon': {
        'variants': [
            {'target': 3, 'reward': 40, 'description': 'Sell 3 Pokemon'},
            {'target': 5, 'reward': 70, 'description': 'Sell 5 Pokemon'},
            {'target': 10, 'reward': 120, 'description': 'Sell 10 Pokemon'},
        ]
    },

    # Collection quests
    'catch_starter': {
        'variants': [
            {'target': 1, 'reward': 60, 'description': 'Catch a starter Pokemon'},
        ]
    },
}


def generate_daily_quests() -> List[Dict]:
    """Generate 3 random daily quests"""
    all_quests = []

    # Flatten all quest variants
    for quest_type, data in QUEST_TYPES.items():
        for variant in data['variants']:
            all_quests.append({
                'type': quest_type,
                'target': variant['target'],
                'reward': variant['reward'],
                'description': variant['description']
            })

    # Select 3 random quests (make sure we have enough variety)
    if len(all_quests) >= 3:
        selected = random.sample(all_quests, 3)
    else:
        selected = all_quests + [random.choice(all_quests) for _ in range(3 - len(all_quests))]

    return selected
