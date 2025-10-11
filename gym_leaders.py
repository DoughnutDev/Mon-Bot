# Gym Leader System
# Gen 1 Gym Leaders with preset teams

GYM_LEADERS = {
    'brock': {
        'name': 'Brock',
        'title': 'The Rock-Solid Pokemon Trainer',
        'type': 'Rock',
        'badge': '🪨 Boulder Badge',
        'badge_emoji': '🪨',
        'location': 'Pewter City',
        'pokemon': [
            {
                'name': 'Geodude',
                'id': 74,
                'level': 12,
                'types': ['rock', 'ground']
            },
            {
                'name': 'Onix',
                'id': 95,
                'level': 14,
                'types': ['rock', 'ground']
            }
        ],
        'rewards': {
            'pokedollars': 500,
            'xp': 200,
            'pack': 'Basic Pack'
        },
        'difficulty': 1
    },
    'misty': {
        'name': 'Misty',
        'title': 'The Tomboyish Mermaid',
        'type': 'Water',
        'badge': '💧 Cascade Badge',
        'badge_emoji': '💧',
        'location': 'Cerulean City',
        'pokemon': [
            {
                'name': 'Staryu',
                'id': 120,
                'level': 18,
                'types': ['water']
            },
            {
                'name': 'Starmie',
                'id': 121,
                'level': 21,
                'types': ['water', 'psychic']
            }
        ],
        'rewards': {
            'pokedollars': 750,
            'xp': 250,
            'pack': 'Basic Pack'
        },
        'difficulty': 2
    },
    'lt_surge': {
        'name': 'Lt. Surge',
        'title': 'The Lightning American',
        'type': 'Electric',
        'badge': '⚡ Thunder Badge',
        'badge_emoji': '⚡',
        'location': 'Vermilion City',
        'pokemon': [
            {
                'name': 'Voltorb',
                'id': 100,
                'level': 21,
                'types': ['electric']
            },
            {
                'name': 'Pikachu',
                'id': 25,
                'level': 18,
                'types': ['electric']
            },
            {
                'name': 'Raichu',
                'id': 26,
                'level': 24,
                'types': ['electric']
            }
        ],
        'rewards': {
            'pokedollars': 1000,
            'xp': 300,
            'pack': 'Booster Pack'
        },
        'difficulty': 3
    },
    'erika': {
        'name': 'Erika',
        'title': 'The Nature Loving Princess',
        'type': 'Grass',
        'badge': '🌸 Rainbow Badge',
        'badge_emoji': '🌸',
        'location': 'Celadon City',
        'pokemon': [
            {
                'name': 'Victreebel',
                'id': 71,
                'level': 29,
                'types': ['grass', 'poison']
            },
            {
                'name': 'Tangela',
                'id': 114,
                'level': 24,
                'types': ['grass']
            },
            {
                'name': 'Vileplume',
                'id': 45,
                'level': 29,
                'types': ['grass', 'poison']
            }
        ],
        'rewards': {
            'pokedollars': 1250,
            'xp': 350,
            'pack': 'Booster Pack'
        },
        'difficulty': 4
    },
    'koga': {
        'name': 'Koga',
        'title': 'The Poisonous Ninja Master',
        'type': 'Poison',
        'badge': '🍃 Soul Badge',
        'badge_emoji': '🍃',
        'location': 'Fuchsia City',
        'pokemon': [
            {
                'name': 'Koffing',
                'id': 109,
                'level': 37,
                'types': ['poison']
            },
            {
                'name': 'Muk',
                'id': 89,
                'level': 39,
                'types': ['poison']
            },
            {
                'name': 'Koffing',
                'id': 109,
                'level': 37,
                'types': ['poison']
            },
            {
                'name': 'Weezing',
                'id': 110,
                'level': 43,
                'types': ['poison']
            }
        ],
        'rewards': {
            'pokedollars': 1500,
            'xp': 400,
            'pack': 'Premium Pack'
        },
        'difficulty': 5
    },
    'sabrina': {
        'name': 'Sabrina',
        'title': 'The Master of Psychic Pokemon',
        'type': 'Psychic',
        'badge': '🔮 Marsh Badge',
        'badge_emoji': '🔮',
        'location': 'Saffron City',
        'pokemon': [
            {
                'name': 'Kadabra',
                'id': 64,
                'level': 38,
                'types': ['psychic']
            },
            {
                'name': 'Mr. Mime',
                'id': 122,
                'level': 37,
                'types': ['psychic', 'fairy']
            },
            {
                'name': 'Venomoth',
                'id': 49,
                'level': 38,
                'types': ['bug', 'poison']
            },
            {
                'name': 'Alakazam',
                'id': 65,
                'level': 43,
                'types': ['psychic']
            }
        ],
        'rewards': {
            'pokedollars': 1750,
            'xp': 450,
            'pack': 'Premium Pack'
        },
        'difficulty': 6
    },
    'blaine': {
        'name': 'Blaine',
        'title': 'The Hotheaded Quiz Master',
        'type': 'Fire',
        'badge': '🔥 Volcano Badge',
        'badge_emoji': '🔥',
        'location': 'Cinnabar Island',
        'pokemon': [
            {
                'name': 'Growlithe',
                'id': 58,
                'level': 42,
                'types': ['fire']
            },
            {
                'name': 'Ponyta',
                'id': 77,
                'level': 40,
                'types': ['fire']
            },
            {
                'name': 'Rapidash',
                'id': 78,
                'level': 42,
                'types': ['fire']
            },
            {
                'name': 'Arcanine',
                'id': 59,
                'level': 47,
                'types': ['fire']
            }
        ],
        'rewards': {
            'pokedollars': 2000,
            'xp': 500,
            'pack': 'Elite Trainer Pack'
        },
        'difficulty': 7
    },
    'giovanni': {
        'name': 'Giovanni',
        'title': 'The Self-Proclaimed Strongest Trainer',
        'type': 'Ground',
        'badge': '🌍 Earth Badge',
        'badge_emoji': '🌍',
        'location': 'Viridian City',
        'pokemon': [
            {
                'name': 'Rhyhorn',
                'id': 111,
                'level': 45,
                'types': ['ground', 'rock']
            },
            {
                'name': 'Dugtrio',
                'id': 51,
                'level': 42,
                'types': ['ground']
            },
            {
                'name': 'Nidoqueen',
                'id': 31,
                'level': 44,
                'types': ['poison', 'ground']
            },
            {
                'name': 'Nidoking',
                'id': 34,
                'level': 45,
                'types': ['poison', 'ground']
            },
            {
                'name': 'Rhydon',
                'id': 112,
                'level': 50,
                'types': ['ground', 'rock']
            }
        ],
        'rewards': {
            'pokedollars': 2500,
            'xp': 600,
            'pack': 'Elite Trainer Pack'
        },
        'difficulty': 8
    }
}

# Gym order for display purposes (but can be challenged in any order)
GYM_ORDER = ['brock', 'misty', 'lt_surge', 'erika', 'koga', 'sabrina', 'blaine', 'giovanni']


def get_gym_leader(gym_key: str):
    """Get gym leader data by key"""
    return GYM_LEADERS.get(gym_key.lower())


def get_all_gym_leaders():
    """Get all gym leaders in order"""
    return [(key, GYM_LEADERS[key]) for key in GYM_ORDER]


def get_gym_count():
    """Get total number of gyms"""
    return len(GYM_LEADERS)
