# Mon Bot

A Discord bot that spawns random Pokemon for users to catch! Type `ball` in chat when a Pokemon appears to catch it.

## Features

- Random Pokemon spawning in designated channels
- Catch Pokemon by typing `ball` in chat
- Track your caught Pokemon with `!pokedex`
- See your collection statistics with `!count`
- Pokemon data fetched from [PokeAPI](https://pokeapi.co/)

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- A Discord Bot Token ([Get one here](https://discord.com/developers/applications))
- Git (optional, for cloning)

### Installation

1. **Clone or download this repository**
   ```bash
   git clone <your-repo-url>
   cd Mon-Bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create your `.env` file**
   ```bash
   cp .env.example .env
   ```

4. **Configure your bot**

   Edit the `.env` file with your settings:

   ```env
   DISCORD_TOKEN=your_actual_bot_token_here
   SPAWN_CHANNELS=123456789012345678,987654321098765432
   SPAWN_INTERVAL_MIN=180
   SPAWN_INTERVAL_MAX=600
   ```

   **Getting Channel IDs:**
   - Enable Developer Mode in Discord (Settings > Advanced > Developer Mode)
   - Right-click on a channel and select "Copy ID"
   - Paste the ID into `SPAWN_CHANNELS` (comma-separated for multiple channels)

5. **Run the bot**
   ```bash
   python bot.py
   ```

## Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and name it "Mon Bot"
3. Go to the "Bot" section
4. Click "Add Bot"
5. Under "Privileged Gateway Intents", enable:
   - Message Content Intent
   - Server Members Intent
6. Copy your bot token and paste it into your `.env` file
7. Go to OAuth2 > URL Generator
8. Select scopes: `bot`
9. Select permissions:
   - Send Messages
   - Embed Links
   - Read Message History
   - Use External Emojis
10. Copy the generated URL and open it to invite the bot to your server

## Commands

- **`ball`** - Catch a spawned Pokemon (type in chat, no slash needed)
- **`/pokedex [@user]`** - View your Pokedex or another user's
- **`/count`** - See how many of each Pokemon you've caught
- **`/help`** - Display bot commands

## Configuration

### Environment Variables

- **DISCORD_TOKEN** - Your Discord bot token (required)
- **SPAWN_CHANNELS** - Comma-separated list of channel IDs where Pokemon will spawn
- **SPAWN_INTERVAL_MIN** - Minimum time in seconds between spawns (default: 180 = 3 minutes)
- **SPAWN_INTERVAL_MAX** - Maximum time in seconds between spawns (default: 600 = 10 minutes)

## Deploying to Render.com

1. Push your code to GitHub (make sure `.env` is in `.gitignore`!)
2. Go to [Render.com](https://render.com/)
3. Create a new "Background Worker"
4. Connect your GitHub repository
5. Set the following:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
6. Add environment variables in Render dashboard:
   - `DISCORD_TOKEN`
   - `SPAWN_CHANNELS`
   - `SPAWN_INTERVAL_MIN`
   - `SPAWN_INTERVAL_MAX`
7. Deploy!

## File Storage

Caught Pokemon are stored in `user_data.json` in the bot directory. This file is automatically created when the first Pokemon is caught.

**Note:** On Render.com, this file will reset when the bot restarts. For persistent storage, consider:
- Using Render's Disk storage feature
- Implementing a database (PostgreSQL, MongoDB, etc.)

## Troubleshooting

**Bot doesn't respond:**
- Make sure Message Content Intent is enabled in Discord Developer Portal
- Check that the bot has permission to send messages in the channel

**Pokemon don't spawn:**
- Verify `SPAWN_CHANNELS` contains valid channel IDs
- Make sure the bot has access to those channels
- Check the bot console for error messages

**Import errors:**
- Make sure you've installed all requirements: `pip install -r requirements.txt`

## License

Feel free to use and modify this bot for your own Discord server!

## Credits

- Created by **DoughnutDev**
- Built with **Claude Code** by Anthropic
- Pokemon data from [PokeAPI](https://pokeapi.co/)
- Built with [discord.py](https://github.com/Rapptz/discord.py)
