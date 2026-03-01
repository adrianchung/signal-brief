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

## Project Structure

```
main.py                    # Entry point — argparse, Settings init, run_pipeline or start
src/config.py              # Pydantic-settings Settings class
src/pipeline.py            # fetch → analyze → deliver orchestration
src/scheduler.py           # APScheduler BlockingScheduler with CronTrigger
src/sources/hackernews.py  # HN Algolia API fetcher
src/analysis/__init__.py   # Analyzer Protocol + get_analyzer(config, provider)
src/analysis/claude.py     # ClaudeAnalyzer (claude-sonnet-4-6)
src/analysis/gemini.py     # GeminiAnalyzer (gemini-3-flash-preview)
src/delivery/__init__.py   # Deliverer Protocol + get_deliverers(config)
src/delivery/slack.py      # Slack incoming webhook
src/delivery/ntfy.py       # Ntfy push
src/delivery/sms.py        # Twilio SMS
tests/                     # pytest test suite
```

---

## Architecture Conventions

- **All delivery channels are opt-in** — a channel only activates if its credentials are set in `.env`.
- **Per-deliverer try/except in pipeline** — one delivery failure must not block the others.
- **Analyzer and Deliverer are Protocols** — new implementations just need to match the interface; register in `get_analyzer` / `get_deliverers`.
- **New source module signature:** `fetch_stories(keywords: list[str], min_score: int, hours_back: int = 12) -> list[dict]`
- **New delivery module signature:** `send(brief: str) -> None` — add credentials to `config.py`, register in `src/delivery/__init__.py`.
- **HN fetcher deduplicates by `objectID`** across multi-keyword queries.
- **Keywords and schedule_times** are stored as CSV strings in config; use `.keyword_list` and `.schedule_time_list` properties.

---

## Testing Conventions

- Tests live in `tests/`, one file per source module (e.g. `test_config.py`, `test_pipeline.py`).
- Use `unittest.mock.patch` / `MagicMock` for all HTTP and external API calls — never make real network calls in tests.
- Pass `_env_file=None` when constructing `Settings` in tests to prevent loading real `.env` credentials.
- Every new module must have a corresponding test file before the PR is merged.
- Test naming: `test_<what_it_does>` in classes grouped by `class Test<ComponentName>`.

---

## LLM Providers

| Provider | Default | Key env var | Model |
|---|---|---|---|
| Gemini | Yes | `GEMINI_API_KEY` | `gemini-3-flash-preview` |
| Claude | No | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |

At least one key must be set. Selected via `--provider gemini|claude` (default: `gemini`).

---

## GitHub Issues

All planned features are tracked as GitHub issues at https://github.com/adrianchung/signal-brief/issues.
When implementing a feature, reference the issue number in commits and close it on completion.

Current open issues:
- #1 — Well-formatted markdown summaries
- #2 — Linkable source URLs
- #3 — Extended configurable content sources (HN, stocks + sentiment, AI tracker)
- #4 — Run logging / history persistence
- #5 — Error alerting on failed runs
- #6 — Cross-run story deduplication (depends on #4)
- #7 — Story relevance ranking before summarization
- #8 — Email delivery channel
- #9 — Per-schedule digest configuration
- #10 — Docker / containerization
- #11 — Dry-run mode (`--dry-run` flag)
