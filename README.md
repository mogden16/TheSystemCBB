# NCAAM Discord Picks Logger

A production-lean MVP that logs NCAA men’s college basketball spread picks from a single Discord channel into SQLite, supports corrections, and calculates performance stats.

## File Tree

```
.
├── .env.example
├── README.md
├── ncaam_picks_bot
│   ├── __init__.py
│   ├── bot.py
│   ├── cli.py
│   ├── config.py
│   ├── db.py
│   └── parser.py
├── requirements.txt
└── tests
    └── test_parser.py
```

## Setup (Windows)

1) **Create a virtual environment**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2) **Install dependencies**

```powershell
pip install -r requirements.txt
```

3) **Create a Discord bot + add to server**

- Go to the [Discord Developer Portal](https://discord.com/developers/applications).
- Create a new application, add a bot, and copy the bot token.
- Under *Bot* settings, enable **Message Content Intent**.
- Use *OAuth2 → URL Generator* with `bot` scope and `Read Message History`, `View Channels` permissions to add the bot to your server.
- Copy the numeric channel ID (enable Developer Mode in Discord and right-click the channel).

4) **Configure environment variables**

Create a `.env` file using `.env.example` as a template:

```ini
DISCORD_TOKEN=your_bot_token_here
CHANNEL_ID=123456789012345678
ALLOWED_AUTHOR_IDS=111111111111111111,222222222222222222
DB_PATH=picks.db
```

5) **Run the bot**

```powershell
python -m ncaam_picks_bot.cli run-bot
```

6) **Use CLI commands**

```powershell
python -m ncaam_picks_bot.cli list-pending
python -m ncaam_picks_bot.cli grade --pick-id 1 --result win --odds -110 --risk 1.0
python -m ncaam_picks_bot.cli stats --from 2024-01-01 --to 2024-01-31
```

## Example Outputs

### list-pending (after Example A)

```
Pending picks:
#1 Alabama 7.5 at Florida
#2 Maryland 13.5 over Purdue
#3 Northern Kentucky 5.5 at Oakland
#4 Nebraska -2.5 over Illinois
#5 Wofford 1.5 over East Tennessee
```

### stats (after grading)

```
Overall: total=5 wins=3 losses=2 pushes=0 win%=60.0 net_units=0.73 roi=0.15 risk=5.00
2024-01-12: total=5 wins=3 losses=2 pushes=0 win%=60.0 net_units=0.73 roi=0.15 risk=5.00
```
