# Mon Bot

A fully-featured Pokemon Discord bot with catching, battling, trading, quests, and more! Catch Pokemon that spawn in your server, train them through battles, complete daily quests, and challenge gym leaders.

## Features

### 🎯 Core Gameplay
- **Random Pokemon Spawning** - Pokemon appear in designated channels with smart spawn timing
- **Type `ball` to Catch** - First person to type it catches the Pokemon
- **Wild Trainer Encounters** - 15% chance a trainer challenges you when catching (battle to claim the Pokemon!)
- **Gen 1 Pokemon** - All 151 original Pokemon including legendaries

### ⚔️ Battle System
- **PvP Battles** (`/battle`) - Challenge other players with your Pokemon
- **Trainer Battles** (`/trainer`) - Train your Pokemon against NPCs (3 per hour, earn XP)
- **Gym Leaders** (`/gym`) - Challenge all 8 Kanto Gym Leaders and earn badges
- **Type Effectiveness** - Full Pokemon type chart with STAB bonuses
- **Level System** - Pokemon gain XP and level up through battles (100 XP per level)
- **Turn-Based Combat** - Strategic battles with moves, critical hits, and damage calculation

### 📊 Progress & Collection
- **Daily Quests** (`/quests`) - Complete 3 daily quests to earn Pokedollars
- **Pokedex** (`/pokedex`) - View your collection and progress
- **Pokemon Stats** (`/stats`) - Detailed stats including level, XP, win/loss record
- **Badge Collection** (`/badges`) - Track your 8 gym badges
- **Leaderboards** (`/leaderboard`) - Compete with other trainers in your server

### 💰 Economy System
- **Pokedollars Currency** - Earn from catching, quests, and battles
- **Shop** (`/shop`) - Buy Pokemon packs with different rarities and odds
- **Packs** (`/pack`) - Open packs to get multiple Pokemon at once
- **Trading** (`/trade`) - Trade Pokemon with other players
- **Selling** (`/sell`) - Sell duplicate Pokemon for Pokedollars

### 📚 Additional Features
- **Pokemon Wiki** (`/wiki`) - View lore, Pokedex entries, and Pokemon information
- **Multi-Server Support** - Each Discord server has independent data
- **Admin Controls** - Setup spawn channels, force spawns, clear channels

## Quick Start

1. **[Setup Instructions](SETUP.md)** - Complete installation and deployment guide
2. **Invite the bot to your Discord server**
3. **Run `/setup #channel`** to configure where Pokemon spawn
4. **Start catching!** Type `ball` when a Pokemon appears
5. **Complete quests** and **battle trainers** to level up your Pokemon

## Commands

### 🎯 Catching & Collection
- **`ball`** - Catch a spawned Pokemon (type in chat)
- **`/pokedex [@user]`** - View your Pokedex or another user's collection
- **`/count`** - See how many of each Pokemon you've caught
- **`/stats [pokemon]`** - View detailed stats for your Pokemon

### ⚔️ Battles
- **`/battle @user`** - Challenge another player to a PvP battle
- **`/trainer`** - Battle trainers for XP (3 battles per hour cooldown)
- **`/gym`** - Challenge Kanto Gym Leaders and earn badges
- **`/badges`** - View your gym badge collection

### 📦 Packs & Economy
- **`/pack`** - Open Pokemon packs from your inventory
- **`/shop`** - View available packs and items for purchase
- **`/buy [item]`** - Purchase items from the shop
- **`/balance`** - Check your Pokedollar balance
- **`/sell`** - Sell duplicate Pokemon for Pokedollars

### 🔄 Trading & Social
- **`/trade @user`** - Trade Pokemon with another player
- **`/quests`** - View daily quests and progress (earn Pokedollars!)
- **`/leaderboard`** - View server rankings
- **`/wiki [pokemon]`** - View Pokemon lore and Pokedex entries

### 🔧 Admin Commands
- **`/setup #channel`** - Configure spawn channels (Administrator)
- **`/clear`** - Clear all spawn channels (Administrator)
- **`/spawn`** - Force spawn a Pokemon immediately (Administrator)
- **`/adminhelp`** - View admin commands (Administrator)

### ℹ️ Help
- **`/help`** - Display all bot commands

## Game Mechanics

### Catching Pokemon
1. Pokemon spawn randomly in configured channels (3-10 minute intervals)
2. Type `ball` to catch - first person gets it
3. 15% chance a wild trainer appears and challenges you
4. Win the trainer battle to claim the Pokemon
5. Earn Pokedollars for each catch (5-15, more for legendaries)

### Battle System
- **Species-Based Levels** - All your Charizards share the same level
- **100 XP per Level** - No level cap
- **Battle Rewards:**
  - PvP Win: 75 XP
  - Trainer Battle Win: 50 XP
  - Trainer Battle Loss: 10 XP
  - Gym Victory: 100 XP
- **Type Effectiveness** - Super effective (2x), not very effective (0.5x), immune (0x)
- **STAB Bonus** - 1.5x damage when move type matches Pokemon type

### Daily Quests
- 3 new quests every day at midnight
- Quest types: catching, battles, trading, packs, economy, badges
- Rewards: 20-250 Pokedollars depending on difficulty
- Complete all 3 for bonus notification

### Gym Leaders
- Challenge all 8 Kanto Gym Leaders in order
- Each gym has a type specialty (Brock = Rock, Misty = Water, etc.)
- Earn badges to prove your skill
- Re-challenge after beating all 8 gyms

### Shop Packs
- **Basic Pack** (₽100) - 3-5 Pokemon, 0.01% shiny chance
- **Booster Pack** (₽250) - 5-8 Pokemon, better odds
- **Premium Pack** (₽500) - 8-12 Pokemon, guaranteed rare
- **Elite Trainer Pack** (₽1000) - 12-18 Pokemon, 3 guaranteed rares
- **Master Collection** (₽2500) - 20-25 Pokemon, guaranteed shiny or legendaries

## Technology Stack

- **Discord.py** - Discord bot framework with slash commands and UI components
- **PostgreSQL** - Persistent database storage (asyncpg)
- **PokeAPI** - Pokemon data, stats, types, moves, and sprites
- **Python 3.8+** - Core programming language

## Database Schema

The bot uses PostgreSQL with the following main tables:
- `guilds` - Server configurations and spawn channels
- `catches` - All Pokemon catches with timestamps
- `pokemon_species_stats` - Pokemon levels, XP, and battle records
- `battle_history` - PvP and trainer battle logs
- `daily_quests` - User quest progress and completion
- `user_currency` - Pokedollar balances and transaction history
- `user_packs` - Pack inventory
- `shop_items` - Available items and pack configurations
- `gym_badges` - Badge collection tracking
- `trainer_cooldowns` - Trainer battle cooldowns (3 per hour)

## Deployment

This bot is designed to be easily deployed on:
- **Render.com** (recommended - free tier available)
- **Heroku**
- **Railway**
- **VPS/Self-hosted**

See the [Setup Guide](SETUP.md) for detailed deployment instructions.

## Contributing

Feel free to fork this project and submit pull requests! The bot is actively developed with new features added regularly.

## License

Feel free to use and modify this bot for your own Discord server!

## Credits

- Created by **[DoughnutDev](https://github.com/DoughnutDev)**
- Built with **[Claude Code](https://claude.com/claude-code)** by Anthropic
- Pokemon data from [PokeAPI](https://pokeapi.co/)
- Built with [discord.py](https://github.com/Rapptz/discord.py)

---

**Questions or issues?** Check the [Setup Guide](SETUP.md) or open an issue on GitHub!
