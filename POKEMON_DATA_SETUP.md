# Pokemon Data Setup (Optional Performance Boost)

## What This Does
Pre-fetches all Gen 1 Pokemon data locally instead of calling PokeAPI every time. This makes battles **instant** instead of having 1-2 second delays.

## Benefits
- ⚡ **10x faster battles** - No network delays
- 📶 **No rate limits** - PokeAPI won't throttle you
- 🌐 **Works offline** - No internet needed for Pokemon data
- 🔋 **Reduces server load** - Both yours and PokeAPI's

## How to Set Up

### Step 1: Run the Fetch Script
```bash
python utils/fetch_pokemon_data.py
```

This will:
- Download all 151 Gen 1 Pokemon from PokeAPI
- Fetch their moves, stats, types, and sprites
- Save everything to `pokemon_data.json` (~500KB)
- Take about 3-5 minutes

### Step 2: Commit the Data File
```bash
git add pokemon_data.json
git commit -m "Add local Pokemon data for performance"
git push
```

### Step 3: Deploy!
Your bot will automatically use the local data when available. If the file isn't found, it falls back to PokeAPI calls (no breaking changes).

## File Structure
```
Mon-Bot/
├── utils/
│   └── fetch_pokemon_data.py   # Run once to generate data
├── pokemon_data_loader.py      # Module that loads the data
├── pokemon_data.json           # The actual data (generated)
└── bot.py                      # Uses local data automatically
```

## When to Re-Run
Only if:
- PokeAPI updates their data (rare)
- You want to add more Pokemon
- The JSON file gets corrupted

**Note:** Run the script from the project root directory so it saves `pokemon_data.json` in the correct location.

## Legal Notice
Pokemon data sourced from [PokeAPI](https://pokeapi.co)
PokeAPI is licensed under BSD 3-Clause License
This usage is explicitly encouraged by PokeAPI to reduce server load.

## Testing
Before:
```
/battle @user
[2 second delay while fetching Pokemon data...]
Battle starts!
```

After:
```
/battle @user
[instant]
Battle starts!
```

---

**Note:** This is completely optional! The bot works fine without it, just a bit slower.
