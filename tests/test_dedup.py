"""Tests for src/dedup.py — SeenStoryTracker."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src.dedup import SeenStoryTracker


def _story(obj_id: str) -> dict:
    return {"objectID": obj_id, "title": f"Story {obj_id}", "score": 100}


class TestFilterNew:
    def test_all_new_when_empty(self, tmp_path):
        tracker = SeenStoryTracker(tmp_path / "seen.json")
        stories = [_story("1"), _story("2")]
        assert tracker.filter_new(stories) == stories

    def test_filters_previously_seen(self, tmp_path):
        path = tmp_path / "seen.json"
        tracker = SeenStoryTracker(path)
        stories = [_story("1"), _story("2")]
        tracker.mark_seen(stories)

        tracker2 = SeenStoryTracker(path)
        new_stories = [_story("2"), _story("3")]
        result = tracker2.filter_new(new_stories)
        assert len(result) == 1
        assert result[0]["objectID"] == "3"

    def test_empty_stories_returns_empty(self, tmp_path):
        tracker = SeenStoryTracker(tmp_path / "seen.json")
        assert tracker.filter_new([]) == []

    def test_stories_without_objectid_pass_through(self, tmp_path):
        tracker = SeenStoryTracker(tmp_path / "seen.json")
        story = {"title": "No ID story", "score": 50}
        assert tracker.filter_new([story]) == [story]


class TestMarkSeen:
    def test_creates_file(self, tmp_path):
        path = tmp_path / "seen.json"
        tracker = SeenStoryTracker(path)
        tracker.mark_seen([_story("abc")])
        assert path.exists()

    def test_persists_ids(self, tmp_path):
        path = tmp_path / "seen.json"
        tracker = SeenStoryTracker(path)
        tracker.mark_seen([_story("x"), _story("y")])

        data = json.loads(path.read_text())
        assert "x" in data
        assert "y" in data

    def test_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "deep" / "seen.json"
        tracker = SeenStoryTracker(path)
        tracker.mark_seen([_story("z")])
        assert path.exists()

    def test_stories_without_objectid_ignored(self, tmp_path):
        path = tmp_path / "seen.json"
        tracker = SeenStoryTracker(path)
        tracker.mark_seen([{"title": "No ID"}])
        assert not path.exists() or json.loads(path.read_text()) == {}


class TestDeduplicationWindow:
    def test_expired_entries_pruned_on_load(self, tmp_path):
        path = tmp_path / "seen.json"
        # Write an entry timestamped 8 days ago (beyond default 7-day window)
        old_ts = (datetime.now(tz=timezone.utc) - timedelta(days=8)).isoformat()
        path.write_text(json.dumps({"old-story": old_ts}))

        tracker = SeenStoryTracker(path, dedup_window_days=7)
        # Old story should be pruned — treated as new
        assert tracker.filter_new([_story("old-story")]) == [_story("old-story")]

    def test_recent_entries_kept(self, tmp_path):
        path = tmp_path / "seen.json"
        recent_ts = (datetime.now(tz=timezone.utc) - timedelta(days=3)).isoformat()
        path.write_text(json.dumps({"recent-story": recent_ts}))

        tracker = SeenStoryTracker(path, dedup_window_days=7)
        assert tracker.filter_new([_story("recent-story")]) == []

    def test_custom_window(self, tmp_path):
        path = tmp_path / "seen.json"
        ts_2_days_ago = (datetime.now(tz=timezone.utc) - timedelta(days=2)).isoformat()
        path.write_text(json.dumps({"story": ts_2_days_ago}))

        # Window of 1 day — 2-day-old entry should be pruned
        tracker = SeenStoryTracker(path, dedup_window_days=1)
        assert tracker.filter_new([_story("story")]) == [_story("story")]


class TestRobustness:
    def test_missing_file_returns_empty(self, tmp_path):
        tracker = SeenStoryTracker(tmp_path / "nonexistent.json")
        assert tracker.filter_new([_story("1")]) == [_story("1")]

    def test_malformed_json_recovers(self, tmp_path):
        path = tmp_path / "seen.json"
        path.write_text("not json {{{")
        tracker = SeenStoryTracker(path)
        assert tracker.filter_new([_story("1")]) == [_story("1")]

    def test_malformed_timestamp_skipped(self, tmp_path):
        path = tmp_path / "seen.json"
        path.write_text(json.dumps({"story": "not-a-date"}))
        tracker = SeenStoryTracker(path)
        # Malformed entry skipped — story is treated as new
        assert tracker.filter_new([_story("story")]) == [_story("story")]
