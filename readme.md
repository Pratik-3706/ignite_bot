# Ignite Bot

Discord AI bot built for the Ignite Club. Runs on low-spec hardware (tested on 512 MB RAM / 1 GB disk) using `discord.py`, OpenAI-compatible endpoint (`z-ai/glm-5.3-flash` on `aicredits.in`), and Tavily web search.

---

## Features

- **Multi-User Context Memory**: Uses unique Discord User IDs and display names to track conversations in channels and threads. The bot doesn't mix up who said what, even with multiple people talking at once.
- **Asynchronous Background Tools**: Tool calls (web search, PDF generation) execute in background tasks without blocking the bot's heartbeat or gateway connection.
- **Multimodal Vision**: Send an image attachment, URL, or reply to an image—the bot processes it with visual context.
- **Event Planning**: Club admins can schedule, view, and manage club events stored persistently in SQLite.
- **Permission System**: Only server administrators (or designated admin roles/IDs) can configure bot memory and plan events.
- **Silent Replies**: When mentioned or replied to, the bot responds without pinging you back (`mention_author=False`).
- **Low Memory Footprint**: Idles around ~40-60 MB RAM. Generates and cleans up temporary media on the fly so it stays within a 1 GB disk cap.

---

## Triggers

1. **Prefix Commands**: `!ng <command>` (e.g. `!ng help`, `!ng ask <question>`, `!ng event`)
2. **Slash Commands**: `/ask`, `/search`, `/events`, `/pdf`
3. **Direct Interactions**: Mention `@Ignite Bot` or reply directly to any message sent by the bot.

---

## Commands

### General Members
| Command | Description |
|---|---|
| `!ng ask <prompt>` / `/ask` | Chat with the AI using channel history & memory |
| `!ng search <query>` / `/search` | Run a live web search via Tavily |
| `!ng pdf <title> \| <content>` / `/pdf` | Generate and download a PDF document |
| `!ng event` / `/events` | List all upcoming Ignite club events |
| `!ng help` | Show help menu |

### Admin Only
| Command | Description |
|---|---|
| `!ng event add <title> <date_time> [details]` | Add a new club event |
| `!ng event remove <event_id>` | Remove a scheduled event |
| `!ng setclub <key> <value>` | Save persistent server/club knowledge |
| `!ng clear` | Clear conversation memory for current channel |
| `!ng status` | Show RAM, disk usage, latency, and DB stats |

---

## Setup & Installation

### 1. Clone & create virtual environment
```bash
git clone <repo-url>
cd ignite_bot

# Linux
python3 -m venv venv
source venv/bin/activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your credentials:
```env
DISCORD_TOKEN=your_discord_bot_token_here
AICREDITS_API_KEY=your_aicredits_api_key_here
AICREDITS_BASE_URL=https://aicredits.in/v1
AI_MODEL=z-ai/glm-5.3-flash
TAVILY_API_KEY=tvly-your_tavily_api_key_here
BOT_PREFIX=!ng
ADMIN_ROLE_NAME=Admin
ADMIN_USER_IDS=123456789012345678
```

### 4. Run the bot

**Development / Local:**
```bash
python bot.py
```

**Production on Linux (single console / systemd / tmux):**

Using `tmux` or `screen`:
```bash
tmux new -s ignite
source venv/bin/activate
python bot.py
# Press Ctrl+B then D to detach
```

Or run it as a systemd service (`/etc/systemd/system/ignite-bot.service`):
```ini
[Unit]
Description=Ignite Club Discord Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/ignite_bot
ExecStart=/path/to/ignite_bot/venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ignite-bot
sudo systemctl start ignite-bot
```

---

## Notes on Low-Spec Deployment (512MB RAM)

- SQLite database (`src/utils/memory/memory.db`) runs in WAL mode with low memory consumption.
- Generated PDFs and downloaded temporary media are deleted immediately after sending. A background task also purges files older than 15 minutes.
- `.env` and SQLite database files are excluded from Git via `.gitignore`.