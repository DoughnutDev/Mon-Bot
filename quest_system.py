# Daily Quest System
import random
from datetime import date
from typing import Dict, List, Optional

# Quest type definitions with targets and rewards
QUEST_TYPES = {
    'catch_pokemon': {
        'variants': [
            {'target': 3, 'reward': 30, 'description': 'Catch 3 Pokemon'},
            {'target': 5, 'reward': 50, 'description': 'Catch 5 Pokemon'},
            {'target': 10, 'reward': 100, 'description': 'Catch 10 Pokemon'},
        ]
    },
    'win_battles': {
        'variants': [
            {'target': 1, 'reward': 50, 'description': 'Win 1 battle'},
            {'target': 2, 'reward': 100, 'description': 'Win 2 battles'},
            {'target': 3, 'reward': 150, 'description': 'Win 3 battles'},
        ]
    },
    'open_packs': {
        'variants': [
            {'target': 1, 'reward': 25, 'description': 'Open 1 pack'},
        ]
    },
    'complete_trade': {
        'variants': [
            {'target': 1, 'reward': 75, 'description': 'Complete 1 trade'},
        ]
    },
    'catch_legendary': {
        'variants': [
            {'target': 1, 'reward': 200, 'description': 'Catch a legendary Pokemon'},
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
