# Mon Bot

A Discord bot that spawns random Pokemon for users to catch! Type `ball` in chat when a Pokemon appears to catch it.

## Features

- Random Pokemon spawning in designated channels
- Catch Pokemon by typing `ball` in chat
- Multi-server support - each Discord server has independent configuration
- Admin `/setup` command to configure spawn channels per server
- Track your caught Pokemon with `/pokedex`
- See your collection statistics with `/count`
- PostgreSQL database for persistent storage
- Pokemon data fetched from [PokeAPI](https://pokeapi.co/)

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- A Discord Bot Token ([Get one here](https://discord.com/developers/applications))
- PostgreSQL database (local or hosted on Render/Heroku/etc.)
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
   DATABASE_URL=postgresql://username:password@host:port/database
   ```

   **PostgreSQL Database URL Format:**
   - Local: `postgresql://username:password@localhost:5432/monbot`
   - Render: Available in the Render dashboard after creating a PostgreSQL instance
   - The bot will automatically create the necessary tables on first startup

5. **Run the bot**
   ```bash
   python bot.py
   ```

6. **Configure spawn channels in Discord**

   Once the bot is running and added to your server:
   - Use the `/setup #channel` command (Admin only)
   - This tells the bot where to spawn Pokemon in your server
   - You can run `/setup` multiple times to add multiple spawn channels

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

### Admin Commands
- **`/setup #channel`** - Configure which channel(s) Pokemon spawn in (Administrator only)

### User Commands
- **`ball`** - Catch a spawned Pokemon (type in chat when Pokemon appears, no slash needed)
- **`/pokedex [@user]`** - View your Pokedex or another user's
- **`/count`** - See how many of each Pokemon you've caught
- **`/help`** - Display bot commands

## Configuration

### Environment Variables

- **DISCORD_TOKEN** - Your Discord bot token (required)
- **DATABASE_URL** - PostgreSQL connection string (required)
  - Format: `postgresql://username:password@host:port/database`
  - Example: `postgresql://user:pass@localhost:5432/monbot`

### In-Discord Configuration

After the bot is running, server administrators can configure spawn channels:
- Use `/setup #channel` to add a spawn channel to your server
- Pokemon will randomly spawn in configured channels every 6-7 minutes on average
- Each Discord server has independent configuration

## Deploying to Render.com

### Step 1: Create PostgreSQL Database

1. Go to [Render.com](https://render.com/) and sign in
2. Click "New +" and select "PostgreSQL"
3. Configure your database:
   - **Name:** `monbot-db` (or any name you prefer)
   - **Region:** Choose closest to you
   - **PostgreSQL Version:** 15 or higher
   - **Plan:** Free (90 days free, then $7/month)
4. Click "Create Database"
5. Once created, copy the **Internal Database URL** from the database dashboard

### Step 2: Deploy the Bot

1. Push your code to GitHub (make sure `.env` is in `.gitignore`!)
2. In Render, click "New +" and select "Background Worker"
3. Connect your GitHub repository
4. Configure the service:
   - **Name:** `mon-bot` (or any name)
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
5. Add environment variables:
   - `DISCORD_TOKEN` - Your Discord bot token
   - `DATABASE_URL` - Paste the Internal Database URL from Step 1
6. Click "Create Background Worker"
7. The bot will deploy automatically!

### Step 3: Configure in Discord

1. Invite the bot to your Discord server using the OAuth URL from Discord Developer Portal
2. In your Discord server, run `/setup #channel` to configure where Pokemon should spawn
3. Done! Pokemon will start spawning automatically

## Database Storage

All data is stored in a PostgreSQL database:

### Tables
- **guilds** - Stores server configurations (spawn channels, settings)
- **catches** - Records all Pokemon catches with user and server information

### Features
- Automatic table creation on first startup
- Connection pooling for performance
- Per-server data isolation - each Discord server's data is independent
- Persistent storage - data survives bot restarts

**Note:** Make sure your DATABASE_URL is correctly configured. The bot will print an error if it cannot connect to the database.

## Troubleshooting

**Bot doesn't respond:**
- Make sure Message Content Intent is enabled in Discord Developer Portal
- Check that the bot has permission to send messages in the channel
- Verify slash commands are synced (check bot console for "Synced X slash command(s)")

**Pokemon don't spawn:**
- Make sure you've run `/setup #channel` command in your Discord server
- Check that the bot has permission to send messages and embeds in that channel
- Check the bot console for error messages
- Spawn chance is 15% per minute (average 6-7 minutes between spawns)

**Database connection errors:**
- Verify your `DATABASE_URL` is correctly formatted
- Check that your PostgreSQL server is running and accessible
- For Render: Make sure you're using the Internal Database URL (not External)
- Check the bot console for specific database error messages

**Import errors:**
- Make sure you've installed all requirements: `pip install -r requirements.txt`
- Verify Python version is 3.8 or higher

## License

Feel free to use and modify this bot for your own Discord server!

## Credits

- Created by **DoughnutDev**
- Built with **Claude Code** by Anthropic
- Pokemon data from [PokeAPI](https://pokeapi.co/)
- Built with [discord.py](https://github.com/Rapptz/discord.py)
