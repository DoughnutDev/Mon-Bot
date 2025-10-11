# Daily Quest System
import random
from datetime import date
from typing import Dict, List, Optional

# Quest type definitions with targets and rewards
QUEST_TYPES = {
    # ===== CATCHING QUESTS =====
    # General catching quests
    'catch_pokemon': {
        'variants': [
            {'target': 3, 'reward': 30, 'description': 'Catch 3 Pokemon'},
            {'target': 5, 'reward': 50, 'description': 'Catch 5 Pokemon'},
            {'target': 8, 'reward': 80, 'description': 'Catch 8 Pokemon'},
            {'target': 10, 'reward': 100, 'description': 'Catch 10 Pokemon'},
            {'target': 15, 'reward': 150, 'description': 'Catch 15 Pokemon'},
        ]
    },

    # Type-specific catching quests
    'catch_fire': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Fire-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Fire-type Pokemon'},
            {'target': 5, 'reward': 90, 'description': 'Catch 5 Fire-type Pokemon'},
        ]
    },
    'catch_water': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Water-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Water-type Pokemon'},
            {'target': 5, 'reward': 90, 'description': 'Catch 5 Water-type Pokemon'},
        ]
    },
    'catch_grass': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Grass-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Grass-type Pokemon'},
            {'target': 5, 'reward': 90, 'description': 'Catch 5 Grass-type Pokemon'},
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
    'catch_fighting': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Fighting-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Fighting-type Pokemon'},
        ]
    },
    'catch_rock': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Rock-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Rock-type Pokemon'},
        ]
    },
    'catch_ground': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Ground-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Ground-type Pokemon'},
        ]
    },
    'catch_flying': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Flying-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Flying-type Pokemon'},
        ]
    },
    'catch_bug': {
        'variants': [
            {'target': 2, 'reward': 35, 'description': 'Catch 2 Bug-type Pokemon'},
            {'target': 3, 'reward': 50, 'description': 'Catch 3 Bug-type Pokemon'},
        ]
    },
    'catch_poison': {
        'variants': [
            {'target': 2, 'reward': 40, 'description': 'Catch 2 Poison-type Pokemon'},
            {'target': 3, 'reward': 60, 'description': 'Catch 3 Poison-type Pokemon'},
        ]
    },
    'catch_normal': {
        'variants': [
            {'target': 3, 'reward': 40, 'description': 'Catch 3 Normal-type Pokemon'},
            {'target': 5, 'reward': 70, 'description': 'Catch 5 Normal-type Pokemon'},
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
    'catch_ice': {
        'variants': [
            {'target': 1, 'reward': 50, 'description': 'Catch an Ice-type Pokemon'},
            {'target': 2, 'reward': 90, 'description': 'Catch 2 Ice-type Pokemon'},
        ]
    },

    # Unique/Variety Pokemon quests
    'catch_unique': {
        'variants': [
            {'target': 3, 'reward': 60, 'description': 'Catch 3 different Pokemon species'},
            {'target': 5, 'reward': 100, 'description': 'Catch 5 different Pokemon species'},
            {'target': 8, 'reward': 140, 'description': 'Catch 8 different Pokemon species'},
        ]
    },

    # Special Pokemon quests
    'catch_legendary': {
        'variants': [
            {'target': 1, 'reward': 200, 'description': 'Catch a legendary Pokemon'},
        ]
    },
    'catch_starter': {
        'variants': [
            {'target': 1, 'reward': 60, 'description': 'Catch a starter Pokemon (Bulbasaur, Charmander, Squirtle)'},
        ]
    },
    'catch_evolved': {
        'variants': [
            {'target': 2, 'reward': 70, 'description': 'Catch 2 evolved Pokemon'},
            {'target': 3, 'reward': 100, 'description': 'Catch 3 evolved Pokemon'},
        ]
    },

    # ===== BATTLE QUESTS =====
    # General battles
    'win_battles': {
        'variants': [
            {'target': 1, 'reward': 50, 'description': 'Win 1 battle'},
            {'target': 2, 'reward': 100, 'description': 'Win 2 battles'},
            {'target': 3, 'reward': 150, 'description': 'Win 3 battles'},
            {'target': 5, 'reward': 250, 'description': 'Win 5 battles'},
        ]
    },

    # Trainer battles
    'defeat_trainers': {
        'variants': [
            {'target': 1, 'reward': 70, 'description': 'Defeat 1 wild trainer'},
            {'target': 2, 'reward': 120, 'description': 'Defeat 2 wild trainers'},
            {'target': 3, 'reward': 180, 'description': 'Defeat 3 wild trainers'},
        ]
    },

    # Gym battles
    'challenge_gyms': {
        'variants': [
            {'target': 1, 'reward': 100, 'description': 'Challenge a gym leader'},
            {'target': 2, 'reward': 180, 'description': 'Challenge 2 gym leaders'},
        ]
    },
    'defeat_gym_leader': {
        'variants': [
            {'target': 1, 'reward': 150, 'description': 'Defeat a gym leader'},
        ]
    },

    # PvP battles
    'pvp_battles': {
        'variants': [
            {'target': 1, 'reward': 80, 'description': 'Battle another player'},
            {'target': 2, 'reward': 140, 'description': 'Battle other players 2 times'},
        ]
    },

    # Badge quests
    'earn_badge': {
        'variants': [
            {'target': 1, 'reward': 150, 'description': 'Earn a new gym badge'},
        ]
    },

    # ===== PACK QUESTS =====
    'open_packs': {
        'variants': [
            {'target': 1, 'reward': 25, 'description': 'Open 1 pack'},
            {'target': 2, 'reward': 50, 'description': 'Open 2 packs'},
            {'target': 3, 'reward': 75, 'description': 'Open 3 packs'},
            {'target': 5, 'reward': 120, 'description': 'Open 5 packs'},
        ]
    },
    'bulk_open_packs': {
        'variants': [
            {'target': 3, 'reward': 100, 'description': 'Use "Open All Packs" with 3+ packs'},
        ]
    },

    # ===== TRADING QUESTS =====
    'complete_trade': {
        'variants': [
            {'target': 1, 'reward': 75, 'description': 'Complete 1 trade'},
            {'target': 2, 'reward': 150, 'description': 'Complete 2 trades'},
            {'target': 3, 'reward': 200, 'description': 'Complete 3 trades'},
        ]
    },

    # ===== ECONOMY QUESTS =====
    'earn_pokedollars': {
        'variants': [
            {'target': 100, 'reward': 50, 'description': 'Earn ₽100 Pokedollars'},
            {'target': 250, 'reward': 100, 'description': 'Earn ₽250 Pokedollars'},
            {'target': 500, 'reward': 150, 'description': 'Earn ₽500 Pokedollars'},
            {'target': 1000, 'reward': 250, 'description': 'Earn ₽1000 Pokedollars'},
        ]
    },
    'spend_pokedollars': {
        'variants': [
            {'target': 200, 'reward': 60, 'description': 'Spend ₽200 Pokedollars'},
            {'target': 500, 'reward': 120, 'description': 'Spend ₽500 Pokedollars'},
        ]
    },
    'sell_pokemon': {
        'variants': [
            {'target': 3, 'reward': 40, 'description': 'Sell 3 Pokemon'},
            {'target': 5, 'reward': 70, 'description': 'Sell 5 Pokemon'},
            {'target': 10, 'reward': 120, 'description': 'Sell 10 Pokemon'},
        ]
    },
    'buy_from_shop': {
        'variants': [
            {'target': 1, 'reward': 50, 'description': 'Buy 1 item from the shop'},
            {'target': 2, 'reward': 90, 'description': 'Buy 2 items from the shop'},
        ]
    },

    # ===== COLLECTION/PROGRESS QUESTS =====
    'level_up_pokemon': {
        'variants': [
            {'target': 1, 'reward': 60, 'description': 'Level up a Pokemon'},
            {'target': 2, 'reward': 100, 'description': 'Level up 2 Pokemon'},
        ]
    },
    'gain_xp': {
        'variants': [
            {'target': 50, 'reward': 50, 'description': 'Gain 50 battlepass XP'},
            {'target': 100, 'reward': 90, 'description': 'Gain 100 battlepass XP'},
        ]
    },
    'view_stats': {
        'variants': [
            {'target': 3, 'reward': 30, 'description': 'Check /stats for 3 different Pokemon'},
        ]
    },

    # ===== EXPLORATION QUESTS =====
    'check_pokedex': {
        'variants': [
            {'target': 1, 'reward': 20, 'description': 'Check your /pokedex'},
        ]
    },
    'read_wiki': {
        'variants': [
            {'target': 2, 'reward': 30, 'description': 'Read /wiki entries for 2 Pokemon'},
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
