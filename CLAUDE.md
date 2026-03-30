# CLAUDE.md — signal-brief

Instructions for Claude Code working on this project. Follow all rules below without asking for confirmation.

---

## Local Setup (not committed)

Create `.claude/settings.json` in the project root to skip permission prompts:
```json
{
  "permissions": {
    "defaultMode": "bypassPermissions"
  }
}
```
This file is gitignored — set it up on each machine you work from.

---

## Workflow Rules

- **Always run `pytest tests/` before committing.** Fix any failures before pushing. Do not commit with failing tests.
- **Push to GitHub after completing any task** unless the user explicitly says otherwise.
- **Close the relevant GitHub issue** in the commit message using `closes #N` when a task maps to an issue.
- **Do not ask for permission** for routine actions: running tests, committing, pushing, creating issues.

---

## Environment Setup

```bash
pyenv install 3.11.9       # Python version pinned via .python-version
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # fill in at least one LLM key + one delivery channel
```

Run once:
```bash
python main.py --now                    # Gemini (default)
python main.py --now --provider claude  # Claude
python main.py --now --dry-run          # dry run (no delivery, no dedup write)
python main.py --history                # print run history
```

Run scheduler:
```bash
python main.py                    # Gemini (default)
python main.py --provider claude
```

Run tests:
```bash
pytest tests/
```

---

## CLI Flags

| Flag | Description |
|---|---|
| `--now` | Run once immediately instead of scheduling |
| `--provider gemini\|claude` | LLM provider (default: gemini) |
| `--dry-run` | Analyze but skip delivery and dedup write |
| `--ignore-seen` | Skip cross-run dedup filter for this run |
| `--profile NAME` | Use a named profile (overrides global keywords/style) |
| `--history` | Print run history table and exit |

---

## Project Structure

```
main.py                      # Entry point — argparse, Settings init, run_pipeline or start
src/config.py                # Pydantic-settings Settings class
src/pipeline.py              # fetch → merge → dedup → rank → analyze → deliver → log
src/scheduler.py             # APScheduler BlockingScheduler with CronTrigger
src/profiles.py              # Named schedule profile discovery from env vars
src/dedup.py                 # SeenStoryTracker — JSON-backed cross-run dedup with window
src/ranking.py               # rank_stories() — keyword relevance + HN score tiebreaker
src/history.py               # RunLogger — appends to .jsonl, prunes by retention days
src/alerting.py              # send_error_alert() — error notifications via delivery channel

src/sources/__init__.py      # Source Protocol + get_sources(config, keywords)
src/sources/hackernews.py    # HN Algolia API fetcher
src/sources/ai_tracker.py    # ~14 curated AI industry RSS feeds (opt-in)
src/sources/blog_feeds.py    # User-configured RSS blog feeds
src/sources/stocks.py        # yfinance daily movers (opt-in)

src/analysis/__init__.py     # Analyzer Protocol + get_analyzer(config, provider)
src/analysis/claude.py       # ClaudeAnalyzer (claude-sonnet-4-6) + shared PROMPT_TEMPLATE
src/analysis/gemini.py       # GeminiAnalyzer (gemini-3-flash-preview, model fallback chain)

src/delivery/__init__.py     # Deliverer Protocol + get_deliverers(config)
src/delivery/slack.py        # Slack incoming webhook (MD → mrkdwn)
src/delivery/ntfy.py         # Ntfy push (extract clickable actions from URLs)
src/delivery/sms.py          # Twilio SMS (strip MD, 1600 char limit)
src/delivery/email.py        # SendGrid REST or SMTP, HTML + plain-text MIME

tests/                       # pytest test suite (unit + e2e)
scripts/run-digest.sh        # Trigger GitHub Actions digest workflow via gh CLI
Dockerfile                   # Python 3.11 slim, runs python main.py
docker-compose.yml           # Single service, env_file: .env, restart: unless-stopped
```

---

## Architecture Conventions

- **All delivery channels are opt-in** — a channel only activates if its credentials are set in `.env`.
- **Per-deliverer try/except in pipeline** — one delivery failure must not block the others.
- **Analyzer, Deliverer, and Source are Protocols** — new implementations just need to match the interface; register in `get_analyzer` / `get_deliverers` / `get_sources`.
- **New source module signature:** `fetch()` method on a class matching `Source` Protocol — add to `get_sources()` in `src/sources/__init__.py`.
- **New delivery module signature:** `send(brief: str) -> None` — add credentials to `config.py`, register in `src/delivery/__init__.py`.
- **HN fetcher deduplicates by `objectID`** across multi-keyword queries.
- **Keywords and schedule_times** are stored as CSV strings in config; use `.keyword_list` and `.schedule_time_list` properties.
- **Story objectID normalization**: HN → raw HN ID; RSS → `"ai_" + SHA1(id|link|title)[:16]`; stocks → `"stock_" + SHA1(ticker+date)[:16]`.
- **Provider retry logic**: primary retries up to 2× with 10s delay on transient errors (503, 429, rate-limit); fallback provider (if configured) is tried once after primary exhaustion.
- **Named profiles**: if any `SCHEDULE_<NAME>` env vars exist they override `SCHEDULE_TIMES`; each profile has `name`, `time`, `keywords`, `style`. See `src/profiles.py`.
- **Gemini model fallback chain**: tries `gemini-3-flash-preview` → `gemini-2.5-pro` → `gemini-2.5-flash` in order on model-level errors. Configurable via `GEMINI_MODELS`.
- **Dry-run mode**: pipeline runs through analysis but skips delivery and does not write seen-stories.
- **Shared prompt template**: `PROMPT_TEMPLATE` in `src/analysis/claude.py`; both `ClaudeAnalyzer` and `GeminiAnalyzer` import it.
- **Run history**: every non-dry-run writes a record to `data/runs.jsonl`; `RunLogger` prunes records older than `HISTORY_RETENTION_DAYS` on each write.

---

## Story Schema (normalized across all sources)

```python
{
    "objectID":    str,   # unique ID (see normalization rules above)
    "title":       str,
    "url":         str,
    "hn_url":      str,   # HN discussion link (HN stories only)
    "score":       int,   # HN points or synthetic score
    "author":      str,
    "created_at":  str,   # "YYYY-MM-DD HH:MM UTC"
    "num_comments": int,  # HN comments or HN mention count (stocks)
    "source":      str,   # "hn" | "ai_tracker" | "stocks" | "blog_feeds"
    "feed":        str,   # feed name for non-HN sources
}
```

---

## Config / Environment Variables

### LLM (at least one required)
```
GEMINI_API_KEY              Google Gemini API key
ANTHROPIC_API_KEY           Anthropic Claude API key
FALLBACK_PROVIDER           Fallback on primary failure (gemini|claude)
GEMINI_MODELS               CSV fallback chain (default: gemini-3-flash-preview,gemini-2.5-pro,gemini-2.5-flash)
```

### Content & Filtering
```
KEYWORDS                    CSV search keywords (default: kubernetes,MCP,AI agents,...)
MIN_SCORE                   Minimum HN points to include (default: 10)
INCLUDE_HN_DISCUSSION       Add HN discussion link in digest (default: false)
```

### Schedule
```
SCHEDULE_TIMES              CSV of HH:MM times (default: 08:00,17:00)
SCHEDULE_<NAME>             HH:MM — defines a named profile (overrides SCHEDULE_TIMES)
SCHEDULE_<NAME>_KEYWORDS    CSV keywords for this profile
SCHEDULE_<NAME>_STYLE       Style hint for LLM prompt
```

### Delivery Channels (all opt-in)
```
SLACK_WEBHOOK_URL           Slack incoming webhook
NTFY_TOPIC                  Ntfy topic name
NTFY_BASE_URL               Ntfy server (default: https://ntfy.sh)
NTFY_PRIORITY               Priority 1-5 (default: 3)
TWILIO_ACCOUNT_SID          Twilio account SID
TWILIO_AUTH_TOKEN           Twilio auth token
TWILIO_FROM_NUMBER          SMS sender
TWILIO_TO_NUMBER            SMS recipient
EMAIL_TO                    Email recipient
EMAIL_FROM                  Email sender address
SENDGRID_API_KEY            SendGrid API key (preferred email transport)
SMTP_HOST                   SMTP server
SMTP_PORT                   SMTP port (default: 587)
SMTP_USER                   SMTP username
SMTP_PASS                   SMTP password/app password
ALERT_CHANNEL               Error alert channel (ntfy|slack|sms; default: first available)
```

### Additional Sources
```
ENABLE_AI_TRACKER           Enable AI industry RSS feeds (default: false)
AI_TRACKER_HOURS_BACK       Hours to look back in RSS (default: 24)
AI_TRACKER_EXTRA_FEEDS      CSV of "Name=url" for extra AI feeds
ENABLE_STOCKS               Enable stock market movers (default: false)
STOCK_TICKERS               CSV tickers (default: NVDA,MSFT,GOOGL,AAPL,META)
STOCK_MOVE_THRESHOLD        % daily move to surface (default: 3.0)
BLOG_FEEDS                  CSV of "Name=url" blog RSS feeds
BLOG_FEEDS_HOURS_BACK       Hours to look back in blogs (default: 12)
```

### Persistence
```
DEDUP_WINDOW_DAYS           Days before a story can resurface (default: 7)
SEEN_STORIES_PATH           Path to seen-stories JSON (default: data/seen_stories.json)
HISTORY_PATH                Path to run history JSONL (default: data/runs.jsonl)
HISTORY_RETENTION_DAYS      Days to keep run records (default: 30)
```

---

## Testing Conventions

- Tests live in `tests/`, one file per source module (e.g. `test_config.py`, `test_pipeline.py`).
- Use `unittest.mock.patch` / `MagicMock` for all HTTP and external API calls — never make real network calls in tests.
- Pass `_env_file=None` when constructing `Settings` in tests to prevent loading real `.env` credentials.
- Every new module must have a corresponding test file before the PR is merged.
- Test naming: `test_<what_it_does>` in classes grouped by `class Test<ComponentName>`.
- E2E tests are marked `@pytest.mark.e2e` and skipped automatically when credentials are absent.
- Use autouse fixtures to prevent filesystem I/O (SeenStoryTracker, RunLogger) in unit tests.

---

## LLM Providers

| Provider | Default | Key env var | Model |
|---|---|---|---|
| Gemini | Yes | `GEMINI_API_KEY` | `gemini-3-flash-preview` (with fallback chain) |
| Claude | No | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |

At least one key must be set. Selected via `--provider gemini|claude` (default: `gemini`).

---

## GitHub Issues

All planned features are tracked as GitHub issues at https://github.com/adrianchung/signal-brief/issues.
When implementing a feature, reference the issue number in commits and close it on completion.

Current open issues:
- #1 — Well-formatted markdown summaries
- #3 — Extended configurable content sources (HN, stocks + sentiment, AI tracker)
- #4 — Run logging / history persistence
- #5 — Error alerting on failed runs
- #6 — Cross-run story deduplication (depends on #4)
- #7 — Story relevance ranking before summarization
- #9 — Per-schedule digest configuration
- #10 — Docker / containerization
- #11 — Dry-run mode (`--dry-run` flag)

Closed: #2 (linkable source URLs), #8 (email delivery channel)
