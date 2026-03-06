"""End-to-end smoke tests that run the real pipeline with live credentials.

These tests are **skipped by default** — they require real API keys and a
configured Slack webhook.  Run them explicitly with:

    pytest -m e2e

Required environment variables (via .env or exported):
    - GEMINI_API_KEY or ANTHROPIC_API_KEY  (at least one)
    - SLACK_WEBHOOK_URL                    (Slack incoming-webhook URL)
"""

import os
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

# Load .env so credentials are available even when not exported in the shell.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from src.config import Settings
from src.delivery.slack import SlackDeliverer, _to_mrkdwn
from src.pipeline import run_pipeline

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HAS_SLACK = bool(os.environ.get("SLACK_WEBHOOK_URL"))
_HAS_GEMINI = bool(os.environ.get("GEMINI_API_KEY"))
_HAS_CLAUDE = bool(os.environ.get("ANTHROPIC_API_KEY"))
_HAS_ANY_LLM = _HAS_GEMINI or _HAS_CLAUDE

_skip_no_slack = pytest.mark.skipif(not _HAS_SLACK, reason="SLACK_WEBHOOK_URL not set")
_skip_no_llm = pytest.mark.skipif(not _HAS_ANY_LLM, reason="No LLM key set")
_skip_no_gemini = pytest.mark.skipif(not _HAS_GEMINI, reason="GEMINI_API_KEY not set")
_skip_no_claude = pytest.mark.skipif(not _HAS_CLAUDE, reason="ANTHROPIC_API_KEY not set")


def _make_settings(**overrides) -> Settings:
    """Build a Settings from the real environment (reads .env)."""
    return Settings(**overrides)


def _brief_sections_present(brief: str) -> None:
    """Assert the brief contains the expected Theme / Top Stories / Bottom Line
    sections produced by the analyzer prompt template."""
    lower = brief.lower()
    assert "theme" in lower or "📡" in brief, f"Missing theme section:\n{brief}"
    assert "top stories" in lower or "stories" in lower, f"Missing stories section:\n{brief}"
    assert "bottom line" in lower or "🔭" in brief, f"Missing bottom-line section:\n{brief}"


# ---------------------------------------------------------------------------
# Full pipeline e2e — Gemini → Slack
# ---------------------------------------------------------------------------

class TestE2EGeminiSlack:
    """Run the complete pipeline with real Gemini + Slack credentials."""

    @_skip_no_gemini
    @_skip_no_slack
    def test_pipeline_completes_without_error(self):
        """Pipeline should fetch, analyse, and deliver without raising."""
        config = _make_settings()
        # Should not raise
        run_pipeline(config, provider="gemini")

    @_skip_no_gemini
    @_skip_no_slack
    def test_brief_has_expected_structure(self):
        """Capture the brief and validate it contains the expected sections."""
        config = _make_settings()
        captured = {}

        original_print = run_pipeline.__module__
        with patch("src.pipeline._print_brief", side_effect=lambda b: captured.update(brief=b)):
            run_pipeline(config, provider="gemini")

        assert "brief" in captured, "Pipeline did not produce a brief"
        brief = captured["brief"]

        # Non-empty
        assert len(brief.strip()) > 0, "Brief is empty"

        # If stories were found, the brief should have structured sections
        if "No stories matched" not in brief:
            _brief_sections_present(brief)

    @_skip_no_gemini
    @_skip_no_slack
    def test_brief_contains_urls(self):
        """If stories were found, the brief should contain at least one URL."""
        config = _make_settings()
        captured = {}

        with patch("src.pipeline._print_brief", side_effect=lambda b: captured.update(brief=b)):
            run_pipeline(config, provider="gemini")

        brief = captured.get("brief", "")
        if "No stories matched" not in brief:
            assert re.search(r"https?://", brief), f"No URLs in brief:\n{brief}"


# ---------------------------------------------------------------------------
# Full pipeline e2e — Claude → Slack
# ---------------------------------------------------------------------------

class TestE2EClaudeSlack:
    """Run the complete pipeline with real Claude + Slack credentials."""

    @_skip_no_claude
    @_skip_no_slack
    def test_pipeline_completes_without_error(self):
        config = _make_settings()
        run_pipeline(config, provider="claude")

    @_skip_no_claude
    @_skip_no_slack
    def test_brief_has_expected_structure(self):
        config = _make_settings()
        captured = {}

        with patch("src.pipeline._print_brief", side_effect=lambda b: captured.update(brief=b)):
            run_pipeline(config, provider="claude")

        assert "brief" in captured, "Pipeline did not produce a brief"
        brief = captured["brief"]
        assert len(brief.strip()) > 0

        if "No stories matched" not in brief:
            _brief_sections_present(brief)


# ---------------------------------------------------------------------------
# Slack delivery unit smoke — validates webhook accepts a payload
# ---------------------------------------------------------------------------

class TestSlackWebhookSmoke:
    """Send a small test payload to the real Slack webhook to verify it
    accepts messages (HTTP 200)."""

    @_skip_no_slack
    def test_send_test_message(self):
        url = os.environ["SLACK_WEBHOOK_URL"]
        deliverer = SlackDeliverer(url)
        # Should not raise
        deliverer.send("E2E smoke test from signal-brief test suite.")

    @_skip_no_slack
    def test_mrkdwn_message_accepted(self):
        """Slack should accept a message with mrkdwn formatting."""
        url = os.environ["SLACK_WEBHOOK_URL"]
        deliverer = SlackDeliverer(url)
        md_brief = (
            "## Theme\nAI agents dominate the conversation.\n\n"
            "## Top Stories\n"
            "- [Story One](https://example.com/1) — a summary\n"
            "- **Story Two** — another summary\n\n"
            "## Bottom Line\nThe shift continues."
        )
        deliverer.send(md_brief)
