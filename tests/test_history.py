"""Tests for src/history.py — RunLogger."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.history import RunLogger, _fmt_ts, _short_name


def _record(**overrides) -> dict:
    base = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "provider": "gemini",
        "dry_run": False,
        "stories_fetched": 5,
        "stories_after_dedup": 3,
        "brief": "## Theme\nAI rules.\n\n## Bottom Line\nYep.",
        "delivery": {"SlackDeliverer": "ok"},
        "status": "ok",
    }
    base.update(overrides)
    return base


class TestWrite:
    def test_creates_file_and_appends(self, tmp_path):
        path = tmp_path / "runs.jsonl"
        rl = RunLogger(path)
        rl.write(_record())
        assert path.exists()
        lines = path.read_text().splitlines()
        assert len(lines) == 1
        assert json.loads(lines[0])["provider"] == "gemini"

    def test_appends_multiple_records(self, tmp_path):
        path = tmp_path / "runs.jsonl"
        rl = RunLogger(path)
        rl.write(_record(provider="gemini"))
        rl.write(_record(provider="claude"))
        lines = path.read_text().splitlines()
        assert len(lines) == 2

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "data" / "runs.jsonl"
        RunLogger(path).write(_record())
        assert path.exists()


class TestGetHistory:
    def test_empty_when_no_file(self, tmp_path):
        rl = RunLogger(tmp_path / "runs.jsonl")
        assert rl.get_history() == []

    def test_returns_records_in_order(self, tmp_path):
        path = tmp_path / "runs.jsonl"
        rl = RunLogger(path)
        rl.write(_record(provider="gemini"))
        rl.write(_record(provider="claude"))
        history = rl.get_history()
        assert len(history) == 2
        assert history[0]["provider"] == "gemini"
        assert history[1]["provider"] == "claude"

    def test_limits_to_n_most_recent(self, tmp_path):
        path = tmp_path / "runs.jsonl"
        rl = RunLogger(path)
        for i in range(5):
            rl.write(_record(stories_fetched=i))
        history = rl.get_history(n=3)
        assert len(history) == 3
        # Should be the last 3 written
        assert history[0]["stories_fetched"] == 2
        assert history[2]["stories_fetched"] == 4

    def test_skips_malformed_lines(self, tmp_path):
        path = tmp_path / "runs.jsonl"
        path.write_text('{"provider":"gemini"}\nnot json\n{"provider":"claude"}\n')
        history = RunLogger(path).get_history()
        assert len(history) == 2


class TestPrune:
    def test_prunes_old_records(self, tmp_path):
        path = tmp_path / "runs.jsonl"
        old_ts = (datetime.now(tz=timezone.utc) - timedelta(days=35)).isoformat()
        recent_ts = datetime.now(tz=timezone.utc).isoformat()

        rl = RunLogger(path, retention_days=30)
        rl.write(_record(timestamp=old_ts))
        # Trigger another write to cause pruning
        rl.write(_record(timestamp=recent_ts))

        history = rl.get_history(n=100)
        assert len(history) == 1
        assert history[0]["timestamp"] == recent_ts

    def test_keeps_records_within_retention(self, tmp_path):
        path = tmp_path / "runs.jsonl"
        rl = RunLogger(path, retention_days=30)
        for _ in range(3):
            rl.write(_record())
        assert len(rl.get_history(n=100)) == 3

    def test_keeps_records_with_bad_timestamp(self, tmp_path):
        path = tmp_path / "runs.jsonl"
        path.write_text('{"timestamp":"bad","provider":"x"}\n')
        rl = RunLogger(path, retention_days=30)
        rl.write(_record())  # triggers prune
        # Record with bad timestamp is preserved
        history = rl.get_history(n=100)
        providers = [r["provider"] for r in history]
        assert "x" in providers


class TestPrintHistory:
    def test_prints_no_history_message(self, tmp_path, capsys):
        RunLogger(tmp_path / "runs.jsonl").print_history()
        out = capsys.readouterr().out
        assert "No run history" in out

    def test_prints_table_with_records(self, tmp_path, capsys):
        rl = RunLogger(tmp_path / "runs.jsonl")
        rl.write(_record(status="ok", delivery={"SlackDeliverer": "ok"}))
        rl.write(_record(provider="claude", status="no_stories", delivery={}))
        rl.print_history()
        out = capsys.readouterr().out
        assert "SIGNAL BRIEF HISTORY" in out
        assert "gemini" in out
        assert "claude" in out
        assert "no_stories" in out
        assert "slack:ok" in out

    def test_dry_run_shows_dry_run_label(self, tmp_path, capsys):
        rl = RunLogger(tmp_path / "runs.jsonl")
        rl.write(_record(dry_run=True, delivery={}))
        rl.print_history()
        out = capsys.readouterr().out
        assert "dry-run" in out


class TestHelpers:
    def test_fmt_ts_valid(self):
        ts = "2024-06-15T08:30:00+00:00"
        assert _fmt_ts(ts) == "2024-06-15 08:30 UTC"

    def test_fmt_ts_invalid(self):
        assert _fmt_ts("bad") == "bad"[:22]

    def test_short_name(self):
        assert _short_name("SlackDeliverer") == "slack"
        assert _short_name("NtfyDeliverer") == "ntfy"
        assert _short_name("SmsDeliverer") == "sms"
