# Gym Leader System
# Gen 1 Gym Leaders with preset teams

GYM_LEADERS = {
    'brock': {
        'name': 'Brock',
        'title': 'The Rock-Solid Pokemon Trainer',
        'type': 'Rock',
        'badge': '🪨 Boulder Badge',
        'badge_emoji': '🪨',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/1.png',
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
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/2.png',
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
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/3.png',
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
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/4.png',
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
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/5.png',
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
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/6.png',
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
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/7.png',
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
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/8.png',
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

# Gen 2 Johto Gym Leaders
GYM_LEADERS_JOHTO = {
    'falkner': {
        'name': 'Falkner',
        'title': 'The Elegant Master of Flying Pokemon',
        'type': 'Flying',
        'badge': '🪶 Zephyr Badge',
        'badge_emoji': '🪶',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/9.png',
        'location': 'Violet City',
        'pokemon': [
            {'name': 'Pidgey', 'id': 16, 'level': 7, 'types': ['normal', 'flying']},
            {'name': 'Pidgeotto', 'id': 17, 'level': 9, 'types': ['normal', 'flying']}
        ],
        'rewards': {'pokedollars': 500, 'pack': 'Basic Pack'},
        'difficulty': 1
    },
    'bugsy': {
        'name': 'Bugsy',
        'title': 'The Walking Bug Pokemon Encyclopedia',
        'type': 'Bug',
        'badge': '🪲 Hive Badge',
        'badge_emoji': '🪲',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/10.png',
        'location': 'Azalea Town',
        'pokemon': [
            {'name': 'Metapod', 'id': 11, 'level': 14, 'types': ['bug']},
            {'name': 'Kakuna', 'id': 14, 'level': 14, 'types': ['bug', 'poison']},
            {'name': 'Scyther', 'id': 123, 'level': 16, 'types': ['bug', 'flying']}
        ],
        'rewards': {'pokedollars': 750, 'pack': 'Basic Pack'},
        'difficulty': 2
    },
    'whitney': {
        'name': 'Whitney',
        'title': 'The Incredibly Pretty Girl',
        'type': 'Normal',
        'badge': '🥛 Plain Badge',
        'badge_emoji': '🥛',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/11.png',
        'location': 'Goldenrod City',
        'pokemon': [
            {'name': 'Clefairy', 'id': 35, 'level': 18, 'types': ['fairy']},
            {'name': 'Miltank', 'id': 241, 'level': 20, 'types': ['normal']}
        ],
        'rewards': {'pokedollars': 1000, 'pack': 'Booster Pack'},
        'difficulty': 3
    },
    'morty': {
        'name': 'Morty',
        'title': 'The Mystic Seer of the Future',
        'type': 'Ghost',
        'badge': '👻 Fog Badge',
        'badge_emoji': '👻',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/12.png',
        'location': 'Ecruteak City',
        'pokemon': [
            {'name': 'Gastly', 'id': 92, 'level': 21, 'types': ['ghost', 'poison']},
            {'name': 'Haunter', 'id': 93, 'level': 21, 'types': ['ghost', 'poison']},
            {'name': 'Gengar', 'id': 94, 'level': 25, 'types': ['ghost', 'poison']},
            {'name': 'Haunter', 'id': 93, 'level': 23, 'types': ['ghost', 'poison']}
        ],
        'rewards': {'pokedollars': 1250, 'pack': 'Booster Pack'},
        'difficulty': 4
    },
    'chuck': {
        'name': 'Chuck',
        'title': 'His Roaring Fists Do the Talking',
        'type': 'Fighting',
        'badge': '👊 Storm Badge',
        'badge_emoji': '👊',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/13.png',
        'location': 'Cianwood City',
        'pokemon': [
            {'name': 'Primeape', 'id': 57, 'level': 27, 'types': ['fighting']},
            {'name': 'Poliwrath', 'id': 62, 'level': 30, 'types': ['water', 'fighting']}
        ],
        'rewards': {'pokedollars': 1500, 'pack': 'Premium Pack'},
        'difficulty': 5
    },
    'jasmine': {
        'name': 'Jasmine',
        'title': 'The Steel-Clad Defense Girl',
        'type': 'Steel',
        'badge': '⚙️ Mineral Badge',
        'badge_emoji': '⚙️',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/14.png',
        'location': 'Olivine City',
        'pokemon': [
            {'name': 'Magnemite', 'id': 81, 'level': 30, 'types': ['electric', 'steel']},
            {'name': 'Magnemite', 'id': 81, 'level': 30, 'types': ['electric', 'steel']},
            {'name': 'Steelix', 'id': 208, 'level': 35, 'types': ['steel', 'ground']}
        ],
        'rewards': {'pokedollars': 1750, 'pack': 'Premium Pack'},
        'difficulty': 6
    },
    'pryce': {
        'name': 'Pryce',
        'title': 'The Teacher of Winter\'s Harshness',
        'type': 'Ice',
        'badge': '❄️ Glacier Badge',
        'badge_emoji': '❄️',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/15.png',
        'location': 'Mahogany Town',
        'pokemon': [
            {'name': 'Seel', 'id': 86, 'level': 27, 'types': ['water']},
            {'name': 'Dewgong', 'id': 87, 'level': 29, 'types': ['water', 'ice']},
            {'name': 'Piloswine', 'id': 221, 'level': 31, 'types': ['ice', 'ground']}
        ],
        'rewards': {'pokedollars': 2000, 'pack': 'Elite Trainer Pack'},
        'difficulty': 7
    },
    'clair': {
        'name': 'Clair',
        'title': 'The Blessed User of Dragon Pokemon',
        'type': 'Dragon',
        'badge': '🐉 Rising Badge',
        'badge_emoji': '🐉',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/16.png',
        'location': 'Blackthorn City',
        'pokemon': [
            {'name': 'Dragonair', 'id': 148, 'level': 37, 'types': ['dragon']},
            {'name': 'Dragonair', 'id': 148, 'level': 37, 'types': ['dragon']},
            {'name': 'Dragonair', 'id': 148, 'level': 37, 'types': ['dragon']},
            {'name': 'Kingdra', 'id': 230, 'level': 40, 'types': ['water', 'dragon']}
        ],
        'rewards': {'pokedollars': 2500, 'pack': 'Elite Trainer Pack'},
        'difficulty': 8
    }
}

GYM_ORDER_JOHTO = ['falkner', 'bugsy', 'whitney', 'morty', 'chuck', 'jasmine', 'pryce', 'clair']

# Gen 3 Hoenn Gym Leaders
GYM_LEADERS_HOENN = {
    'roxanne': {
        'name': 'Roxanne',
        'title': 'The Rock-Loving Honor Student',
        'type': 'Rock',
        'badge': '🗿 Stone Badge',
        'badge_emoji': '🗿',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/17.png',
        'location': 'Rustboro City',
        'pokemon': [
            {'name': 'Geodude', 'id': 74, 'level': 12, 'types': ['rock', 'ground']},
            {'name': 'Geodude', 'id': 74, 'level': 12, 'types': ['rock', 'ground']},
            {'name': 'Nosepass', 'id': 299, 'level': 15, 'types': ['rock']}
        ],
        'rewards': {'pokedollars': 500, 'pack': 'Basic Pack'},
        'difficulty': 1
    },
    'brawly': {
        'name': 'Brawly',
        'title': 'A Big Wave in Fighting',
        'type': 'Fighting',
        'badge': '🥊 Knuckle Badge',
        'badge_emoji': '🥊',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/18.png',
        'location': 'Dewford Town',
        'pokemon': [
            {'name': 'Machop', 'id': 66, 'level': 16, 'types': ['fighting']},
            {'name': 'Meditite', 'id': 307, 'level': 16, 'types': ['fighting', 'psychic']},
            {'name': 'Makuhita', 'id': 296, 'level': 19, 'types': ['fighting']}
        ],
        'rewards': {'pokedollars': 750, 'pack': 'Basic Pack'},
        'difficulty': 2
    },
    'wattson': {
        'name': 'Wattson',
        'title': 'The Cheerfully Electrifying Man',
        'type': 'Electric',
        'badge': '⚡ Dynamo Badge',
        'badge_emoji': '⚡',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/19.png',
        'location': 'Mauville City',
        'pokemon': [
            {'name': 'Voltorb', 'id': 100, 'level': 20, 'types': ['electric']},
            {'name': 'Electrike', 'id': 309, 'level': 20, 'types': ['electric']},
            {'name': 'Magneton', 'id': 82, 'level': 22, 'types': ['electric', 'steel']},
            {'name': 'Manectric', 'id': 310, 'level': 24, 'types': ['electric']}
        ],
        'rewards': {'pokedollars': 1000, 'pack': 'Booster Pack'},
        'difficulty': 3
    },
    'flannery': {
        'name': 'Flannery',
        'title': 'One With a Fiery Passion That Burns',
        'type': 'Fire',
        'badge': '🔥 Heat Badge',
        'badge_emoji': '🔥',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/20.png',
        'location': 'Lavaridge Town',
        'pokemon': [
            {'name': 'Numel', 'id': 322, 'level': 24, 'types': ['fire', 'ground']},
            {'name': 'Slugma', 'id': 218, 'level': 24, 'types': ['fire']},
            {'name': 'Camerupt', 'id': 323, 'level': 26, 'types': ['fire', 'ground']},
            {'name': 'Torkoal', 'id': 324, 'level': 29, 'types': ['fire']}
        ],
        'rewards': {'pokedollars': 1250, 'pack': 'Booster Pack'},
        'difficulty': 4
    },
    'norman': {
        'name': 'Norman',
        'title': 'A Man in Pursuit of Power',
        'type': 'Normal',
        'badge': '⚖️ Balance Badge',
        'badge_emoji': '⚖️',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/21.png',
        'location': 'Petalburg City',
        'pokemon': [
            {'name': 'Spinda', 'id': 327, 'level': 27, 'types': ['normal']},
            {'name': 'Vigoroth', 'id': 288, 'level': 27, 'types': ['normal']},
            {'name': 'Linoone', 'id': 264, 'level': 29, 'types': ['normal']},
            {'name': 'Slaking', 'id': 289, 'level': 31, 'types': ['normal']}
        ],
        'rewards': {'pokedollars': 1500, 'pack': 'Premium Pack'},
        'difficulty': 5
    },
    'winona': {
        'name': 'Winona',
        'title': 'The Bird Pokemon User Taking Flight into the World',
        'type': 'Flying',
        'badge': '🪽 Feather Badge',
        'badge_emoji': '🪽',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/22.png',
        'location': 'Fortree City',
        'pokemon': [
            {'name': 'Swablu', 'id': 333, 'level': 29, 'types': ['normal', 'flying']},
            {'name': 'Tropius', 'id': 357, 'level': 29, 'types': ['grass', 'flying']},
            {'name': 'Pelipper', 'id': 279, 'level': 30, 'types': ['water', 'flying']},
            {'name': 'Skarmory', 'id': 227, 'level': 31, 'types': ['steel', 'flying']},
            {'name': 'Altaria', 'id': 334, 'level': 33, 'types': ['dragon', 'flying']}
        ],
        'rewards': {'pokedollars': 1750, 'pack': 'Premium Pack'},
        'difficulty': 6
    },
    'tate_liza': {
        'name': 'Tate & Liza',
        'title': 'The Mystic Combination',
        'type': 'Psychic',
        'badge': '🧠 Mind Badge',
        'badge_emoji': '🧠',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/23.png',
        'location': 'Mossdeep City',
        'pokemon': [
            {'name': 'Claydol', 'id': 344, 'level': 41, 'types': ['ground', 'psychic']},
            {'name': 'Xatu', 'id': 178, 'level': 41, 'types': ['psychic', 'flying']},
            {'name': 'Lunatone', 'id': 337, 'level': 42, 'types': ['rock', 'psychic']},
            {'name': 'Solrock', 'id': 338, 'level': 42, 'types': ['rock', 'psychic']}
        ],
        'rewards': {'pokedollars': 2000, 'pack': 'Elite Trainer Pack'},
        'difficulty': 7
    },
    'wallace': {
        'name': 'Wallace',
        'title': 'Artist and Water Pokemon Master',
        'type': 'Water',
        'badge': '💧 Rain Badge',
        'badge_emoji': '💧',
        'badge_icon': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/badges/24.png',
        'location': 'Sootopolis City',
        'pokemon': [
            {'name': 'Luvdisc', 'id': 370, 'level': 40, 'types': ['water']},
            {'name': 'Whiscash', 'id': 340, 'level': 40, 'types': ['water', 'ground']},
            {'name': 'Sealeo', 'id': 364, 'level': 40, 'types': ['ice', 'water']},
            {'name': 'Seaking', 'id': 119, 'level': 42, 'types': ['water']},
            {'name': 'Milotic', 'id': 350, 'level': 43, 'types': ['water']}
        ],
        'rewards': {'pokedollars': 2500, 'pack': 'Elite Trainer Pack'},
        'difficulty': 8
    }
}

GYM_ORDER_HOENN = ['roxanne', 'brawly', 'wattson', 'flannery', 'norman', 'winona', 'tate_liza', 'wallace']


def get_gym_leader(gym_key: str):
    """Get gym leader data by key from any region"""
    key = gym_key.lower()
    if key in GYM_LEADERS:
        return GYM_LEADERS[key]
    if key in GYM_LEADERS_JOHTO:
        return GYM_LEADERS_JOHTO[key]
    return GYM_LEADERS_HOENN.get(key)


def get_all_gym_leaders():
    """Get all Kanto gym leaders in order"""
    return [(key, GYM_LEADERS[key]) for key in GYM_ORDER]


def get_all_gym_leaders_johto():
    """Get all Johto gym leaders in order"""
    return [(key, GYM_LEADERS_JOHTO[key]) for key in GYM_ORDER_JOHTO]


def get_all_gym_leaders_hoenn():
    """Get all Hoenn gym leaders in order"""
    return [(key, GYM_LEADERS_HOENN[key]) for key in GYM_ORDER_HOENN]


def get_gym_count():
    """Get total number of gyms across all regions"""
    return len(GYM_LEADERS) + len(GYM_LEADERS_JOHTO) + len(GYM_LEADERS_HOENN)
