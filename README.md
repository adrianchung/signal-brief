# signal-brief

Fetches stories from Hacker News and AI industry RSS feeds, analyzes them with Claude or Gemini, and delivers a curated digest via Slack, Ntfy, SMS, and/or Email.

## Setup

```bash
pyenv install 3.11.9   # if not already installed
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in at least one LLM key + one delivery channel
```

## Usage

```bash
# Run once (Gemini default, falls back to Claude on failure)
python main.py --now

# Run once with a specific provider
python main.py --now --provider claude

# Dry-run: fetch + analyze, skip delivery
python main.py --now --dry-run
python main.py --now --dry-run --provider claude

# Re-show all stories, bypassing cross-run deduplication
python main.py --now --ignore-seen

# Run a named schedule profile manually
python main.py --now --profile morning

# View recent run history
python main.py --history        # last 10 runs
python main.py --history 20     # last 20 runs

# Start the scheduler (fires at SCHEDULE_TIMES)
python main.py
```

## Triggering via GitHub Actions

Trigger a live run (with delivery) directly from the terminal:

```bash
# Default provider (Gemini)
./scripts/run-digest.sh

# Specific provider
./scripts/run-digest.sh claude
./scripts/run-digest.sh gemini
```

The script triggers the `digest.yml` workflow, waits for it to start, then streams the live status. Requires `gh` (GitHub CLI) to be installed and authenticated.

You can also trigger it from the GitHub UI: **Actions → Run digest → Run workflow**.

## Docker

```bash
# Build
docker build -t signal-brief .

# Run once
docker run --env-file .env signal-brief python main.py --now

# Run scheduler (continuous)
docker compose up -d
```

## Configuration (`.env`)

### LLM providers

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini key — default provider |
| `ANTHROPIC_API_KEY` | Anthropic Claude key |
| `FALLBACK_PROVIDER` | Provider to try if the primary fails (e.g. `claude`) |

At least one key is required. Select provider with `--provider gemini\|claude`.

### Content & filtering

| Variable | Default | Description |
|---|---|---|
| `KEYWORDS` | `kubernetes,MCP,AI agents,...` | Comma-separated HN search keywords |
| `MIN_SCORE` | `10` | Minimum HN point threshold |
| `ENABLE_AI_TRACKER` | `false` | Pull from AI industry RSS feeds |
| `ENABLE_STOCKS` | `false` | Include significant daily stock movers |
| `STOCK_TICKERS` | `NVDA,MSFT,GOOGL,AAPL,META` | Tickers to watch |
| `STOCK_MOVE_THRESHOLD` | `3.0` | % daily move required to surface a ticker |
| `AI_TRACKER_HOURS_BACK` | `24` | Hours back to scan RSS feeds |
| `INCLUDE_HN_DISCUSSION` | `false` | Add HN thread link alongside article URL |

### Schedule

| Variable | Default | Description |
|---|---|---|
| `SCHEDULE_TIMES` | `08:00,17:00` | Comma-separated run times (HH:MM) |

Named profiles replace `SCHEDULE_TIMES` when defined:

```env
SCHEDULE_MORNING=08:00
SCHEDULE_MORNING_KEYWORDS=LLM,AI agents,Claude,agentic
SCHEDULE_MORNING_STYLE=concise morning briefing for a technical lead

SCHEDULE_EVENING=17:00
SCHEDULE_EVENING_KEYWORDS=kubernetes,GKE,open source AI,MCP
SCHEDULE_EVENING_STYLE=end-of-day infrastructure and tooling roundup
```

Run a profile manually: `python main.py --now --profile morning`

### Delivery channels

All channels are opt-in — only those with credentials configured will fire.

| Variable | Description |
|---|---|
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL |
| `NTFY_TOPIC` | Ntfy topic name |
| `NTFY_BASE_URL` | Ntfy server (default: `https://ntfy.sh`) |
| `NTFY_PRIORITY` | 1=min 2=low 3=default 4=high 5=urgent |
| `TWILIO_ACCOUNT_SID` | Twilio account SID (SMS) |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `TWILIO_FROM_NUMBER` | Sender number |
| `TWILIO_TO_NUMBER` | Recipient number |
| `EMAIL_TO` | Recipient address |
| `EMAIL_FROM` | Sender address |
| `SENDGRID_API_KEY` | SendGrid transport (preferred) |
| `SMTP_HOST` | SMTP transport host (alternative to SendGrid) |
| `SMTP_PORT` | SMTP port (default: `587`) |
| `SMTP_USER` | SMTP username |
| `SMTP_PASS` | SMTP password / app password |

### Deduplication & history

| Variable | Default | Description |
|---|---|---|
| `DEDUP_WINDOW_DAYS` | `7` | Days before a seen story can resurface |
| `SEEN_STORIES_PATH` | `data/seen_stories.json` | Seen-story ID cache |
| `HISTORY_PATH` | `data/runs.jsonl` | Run history log |
| `HISTORY_RETENTION_DAYS` | `30` | Days to keep run records |

## Testing

```bash
# Unit tests (default — no network, no quota)
pytest tests/

# Dry-run smoke test (real LLM, no delivery)
python main.py --now --dry-run
python main.py --now --dry-run --provider claude
```

### E2E smoke tests

Require real credentials. Skipped automatically when credentials are absent.

```bash
# Full pipeline E2E — sends real Slack message, consumes LLM quota
pytest -m e2e -v

# Slack webhook only — 2 messages, no LLM calls
pytest -m e2e -k "TestSlackWebhookSmoke" -v
```

Run via GitHub Actions: **Actions → E2E smoke test → Run workflow**

### GitHub secrets

Add these in **Settings → Secrets and variables → Actions**:

| Secret | Purpose |
|---|---|
| `GEMINI_API_KEY` | Gemini API key |
| `ANTHROPIC_API_KEY` | Claude API key |
| `FALLBACK_PROVIDER` | `claude` (recommended — auto-fallback on Gemini errors) |
| `SLACK_WEBHOOK_URL` | Slack webhook for delivery + E2E tests |
| `NTFY_TOPIC` | Ntfy topic for delivery |
| `ENABLE_AI_TRACKER` | `true` to enable RSS feed source |

## Extending

**Add a source:** create `src/sources/<name>.py` with a class implementing `fetch(self) -> list[dict]`, register it in `src/sources/__init__.py`.

**Add a delivery channel:** create `src/delivery/<name>.py` implementing `send(brief: str) -> None`, add credentials to `config.py`, register in `src/delivery/__init__.py`.
