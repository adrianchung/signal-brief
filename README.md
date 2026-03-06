# signal-brief

Fetches filtered Hacker News stories, analyzes them with Claude or Gemini, and delivers a curated digest via Slack, Ntfy, and/or SMS.

## Setup

```bash
pyenv install 3.11.9   # if not already installed
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in at least one LLM key (GEMINI_API_KEY or ANTHROPIC_API_KEY) + at least one delivery channel
```

## Usage

Run once with Gemini (default):
```bash
python main.py --now
```

Run once with Claude:
```bash
python main.py --now --provider claude
```

Start scheduler with Gemini (default):
```bash
python main.py
```

Start scheduler with Claude:
```bash
python main.py --provider claude
```

## Docker

Build the image:
```bash
docker build -t signal-brief .
```

Run once (one-shot):
```bash
docker run --env-file .env signal-brief python main.py --now
docker run --env-file .env signal-brief python main.py --now --provider claude
docker run --env-file .env signal-brief python main.py --dry-run
```

Run scheduler (continuous, fires at `SCHEDULE_TIMES`):
```bash
docker compose up -d
```

## Configuration (`.env`)

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | One of these two is required | Google Gemini API key (default provider) |
| `ANTHROPIC_API_KEY` | One of these two is required | Anthropic Claude API key |
| `MIN_SCORE` | No (default: 150) | Minimum HN point threshold |
| `KEYWORDS` | No | Comma-separated keywords to filter stories |
| `SCHEDULE_TIMES` | No (default: 08:00,17:00) | Comma-separated HH:MM times to run |
| `SLACK_WEBHOOK_URL` | Optional | Slack incoming webhook URL |
| `NTFY_TOPIC` | Optional | Ntfy topic name |
| `NTFY_BASE_URL` | Optional (default: https://ntfy.sh) | Ntfy server base URL |
| `NTFY_PRIORITY` | No (default: 3) | Ntfy message priority (1=min 2=low 3=default 4=high 5=urgent) |
| `TWILIO_ACCOUNT_SID` | Optional | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | Optional | Twilio auth token |
| `TWILIO_FROM_NUMBER` | Optional | Twilio sender number |
| `TWILIO_TO_NUMBER` | Optional | SMS recipient number |

All delivery channels are opt-in — only channels with credentials configured will fire.

## Testing

Run unit tests (e2e tests are excluded by default):
```bash
pytest tests/
```

### E2E smoke tests

E2E tests validate the full pipeline with real credentials and Slack delivery. They are skipped when credentials are not present.

**Required credentials** (set in `.env` or export in shell):

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` or `ANTHROPIC_API_KEY` | At least one LLM key for analysis |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook to receive the test digest |

**Run locally:**
```bash
# Ensure .env has the credentials above, then:
pytest -m e2e -v
```

**Run via GitHub Actions:**
1. Go to **Actions** → **E2E smoke test**
2. Click **Run workflow**
3. Choose a provider (`gemini` or `claude`)

The workflow reads `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, and `SLACK_WEBHOOK_URL` from repository secrets.

### Adding secrets for CI

In your GitHub repo, go to **Settings → Secrets and variables → Actions** and add:
- `GEMINI_API_KEY` — your Google Gemini API key
- `ANTHROPIC_API_KEY` — your Anthropic API key
- `SLACK_WEBHOOK_URL` — a Slack incoming webhook URL (create one at [Slack API → Incoming Webhooks](https://api.slack.com/messaging/webhooks))

## Extending

**Add a new source:** create `src/sources/<name>.py` exporting `fetch_stories(keywords, min_score, hours_back) -> list[dict]` and call it in `pipeline.py`.

**Add a new delivery channel:** create `src/delivery/<name>.py` implementing `send(brief: str) -> None`, add credentials to `config.py`, and register it in `src/delivery/__init__.py`.
