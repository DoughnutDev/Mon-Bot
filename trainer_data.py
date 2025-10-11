"""
Trainer data for random trainer encounters

Trainers have themed teams based on Pokemon types or trainer classes
"""

import random

# Trainer class definitions with themed teams
TRAINERS = [
    # Bug Catchers (early game trainers)
    {
        'name': 'Bug Catcher Liam',
        'class': 'Bug Catcher',
        'sprite': '🐛',
        'pokemon_ids': [11, 13, 14],  # Metapod, Weedle, Kakuna
        'level_range': (8, 12),
        'reward_money': 150
    },
    {
        'name': 'Bug Catcher Wade',
        'class': 'Bug Catcher',
        'sprite': '🐛',
        'pokemon_ids': [10, 13, 48],  # Caterpie, Weedle, Venonat
        'level_range': (10, 14),
        'reward_money': 180
    },

    # Youngsters (basic trainers)
    {
        'name': 'Youngster Ben',
        'class': 'Youngster',
        'sprite': '👦',
        'pokemon_ids': [19, 21],  # Rattata, Spearow
        'level_range': (12, 16),
        'reward_money': 200
    },
    {
        'name': 'Youngster Joey',
        'class': 'Youngster',
        'sprite': '👦',
        'pokemon_ids': [19, 19],  # Top percentage Rattatas!
        'level_range': (14, 18),
        'reward_money': 220
    },

    # Lasses (basic female trainers)
    {
        'name': 'Lass Iris',
        'class': 'Lass',
        'sprite': '👧',
        'pokemon_ids': [35, 39],  # Clefairy, Jigglypuff
        'level_range': (13, 17),
        'reward_money': 210
    },
    {
        'name': 'Lass Dana',
        'class': 'Lass',
        'sprite': '👧',
        'pokemon_ids': [16, 20, 52],  # Pidgey, Raticate, Meowth
        'level_range': (15, 19),
        'reward_money': 240
    },

    # Hikers (rock/ground types)
    {
        'name': 'Hiker Marcos',
        'class': 'Hiker',
        'sprite': '🥾',
        'pokemon_ids': [74, 95],  # Geodude, Onix
        'level_range': (16, 20),
        'reward_money': 280
    },
    {
        'name': 'Hiker Franklin',
        'class': 'Hiker',
        'sprite': '🥾',
        'pokemon_ids': [74, 74, 75],  # Geodude x2, Graveler
        'level_range': (18, 22),
        'reward_money': 320
    },

    # Picnickers (grass/cute Pokemon)
    {
        'name': 'Picnicker Kelsey',
        'class': 'Picnicker',
        'sprite': '🧺',
        'pokemon_ids': [43, 69],  # Oddish, Bellsprout
        'level_range': (14, 18),
        'reward_money': 230
    },
    {
        'name': 'Picnicker Gina',
        'class': 'Picnicker',
        'sprite': '🧺',
        'pokemon_ids': [43, 46, 69],  # Oddish, Paras, Bellsprout
        'level_range': (17, 21),
        'reward_money': 270
    },

    # Campers (outdoor trainers)
    {
        'name': 'Camper Ricky',
        'class': 'Camper',
        'sprite': '🏕️',
        'pokemon_ids': [27, 104],  # Sandshrew, Cubone
        'level_range': (15, 19),
        'reward_money': 250
    },
    {
        'name': 'Camper Ethan',
        'class': 'Camper',
        'sprite': '🏕️',
        'pokemon_ids': [58, 77],  # Growlithe, Ponyta
        'level_range': (18, 22),
        'reward_money': 290
    },

    # Swimmers (water types)
    {
        'name': 'Swimmer Diana',
        'class': 'Swimmer',
        'sprite': '🏊',
        'pokemon_ids': [72, 116],  # Tentacool, Horsea
        'level_range': (17, 21),
        'reward_money': 260
    },
    {
        'name': 'Swimmer Jack',
        'class': 'Swimmer',
        'sprite': '🏊',
        'pokemon_ids': [54, 60, 118],  # Psyduck, Poliwag, Goldeen
        'level_range': (19, 23),
        'reward_money': 300
    },

    # Fishermen (water types)
    {
        'name': 'Fisherman Wade',
        'class': 'Fisherman',
        'sprite': '🎣',
        'pokemon_ids': [129, 129, 129],  # Magikarp spam
        'level_range': (10, 14),
        'reward_money': 160
    },
    {
        'name': 'Fisherman Ned',
        'class': 'Fisherman',
        'sprite': '🎣',
        'pokemon_ids': [98, 120],  # Krabby, Staryu
        'level_range': (18, 22),
        'reward_money': 290
    },

    # Engineers (electric/steel types)
    {
        'name': 'Engineer Baily',
        'class': 'Engineer',
        'sprite': '⚙️',
        'pokemon_ids': [81, 100],  # Magnemite, Voltorb
        'level_range': (16, 20),
        'reward_money': 270
    },
    {
        'name': 'Engineer Bernie',
        'class': 'Engineer',
        'sprite': '⚙️',
        'pokemon_ids': [81, 81, 82],  # Magnemite x2, Magneton
        'level_range': (20, 24),
        'reward_money': 340
    },

    # Psychics (psychic types)
    {
        'name': 'Psychic Johan',
        'class': 'Psychic',
        'sprite': '🔮',
        'pokemon_ids': [63, 96],  # Abra, Drowzee
        'level_range': (17, 21),
        'reward_money': 280
    },
    {
        'name': 'Psychic Dario',
        'class': 'Psychic',
        'sprite': '🔮',
        'pokemon_ids': [64, 97],  # Kadabra, Hypno
        'level_range': (22, 26),
        'reward_money': 370
    },

    # Channelers (ghost/psychic types)
    {
        'name': 'Channeler Hope',
        'class': 'Channeler',
        'sprite': '👻',
        'pokemon_ids': [92, 93],  # Gastly, Haunter
        'level_range': (18, 22),
        'reward_money': 300
    },

    # Beauties (elegant Pokemon)
    {
        'name': 'Beauty Bridget',
        'class': 'Beauty',
        'sprite': '💄',
        'pokemon_ids': [35, 39, 40],  # Clefairy, Jigglypuff, Wigglytuff
        'level_range': (19, 23),
        'reward_money': 310
    },
    {
        'name': 'Beauty Olivia',
        'class': 'Beauty',
        'sprite': '💄',
        'pokemon_ids': [44, 70],  # Gloom, Weepinbell
        'level_range': (21, 25),
        'reward_money': 350
    },

    # Bikers (poison types)
    {
        'name': 'Biker Jared',
        'class': 'Biker',
        'sprite': '🏍️',
        'pokemon_ids': [88, 109],  # Grimer, Koffing
        'level_range': (19, 23),
        'reward_money': 320
    },
    {
        'name': 'Biker Malik',
        'class': 'Biker',
        'sprite': '🏍️',
        'pokemon_ids': [89, 110],  # Muk, Weezing
        'level_range': (23, 27),
        'reward_money': 390
    },

    # Cooltrainers (mixed strong teams)
    {
        'name': 'Cooltrainer Mary',
        'class': 'Cooltrainer',
        'sprite': '⭐',
        'pokemon_ids': [26, 28, 59],  # Raichu, Sandslash, Arcanine
        'level_range': (24, 28),
        'reward_money': 420
    },
    {
        'name': 'Cooltrainer Paul',
        'class': 'Cooltrainer',
        'sprite': '⭐',
        'pokemon_ids': [55, 62, 71],  # Golduck, Poliwrath, Victreebel
        'level_range': (25, 29),
        'reward_money': 450
    },
]


def get_random_trainer():
    """Get a random trainer from the list"""
    return random.choice(TRAINERS).copy()


def get_trainer_team(trainer, user_level_avg=15):
    """
    Generate a trainer's Pokemon team based on their data

    Args:
        trainer: Trainer dictionary
        user_level_avg: Average level of user's Pokemon (for scaling difficulty)

    Returns:
        List of Pokemon dictionaries with IDs, names, and levels
    """
    # Adjust level range based on user's average level
    min_level, max_level = trainer['level_range']

    # Scale trainer levels to be slightly below user's average
    # This makes them challenging but not impossible
    level_adjustment = max(0, user_level_avg - 15)
    min_level = min(50, min_level + level_adjustment)
    max_level = min(50, max_level + level_adjustment)

    team = []
    for pokemon_id in trainer['pokemon_ids']:
        level = random.randint(min_level, max_level)
        team.append({
            'pokemon_id': pokemon_id,
            'level': level
        })

    return team
