"""Tests for src/sources/ai_tracker.py — AITrackerSource."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.sources.ai_tracker import AITrackerSource, _entry_id, _parse_entry_date


def _make_entry(title="Test Post", link="https://example.com/post", entry_id=None,
                published_parsed=None, updated_parsed=None):
    entry = {
        "title": title,
        "link": link,
        "id": entry_id or link,
    }
    if published_parsed:
        entry["published_parsed"] = published_parsed
    if updated_parsed:
        entry["updated_parsed"] = updated_parsed
    return entry


def _now_struct():
    now = datetime.now(tz=timezone.utc)
    return (now.year, now.month, now.day, now.hour, now.minute, now.second, 0, 0, 0)


def _old_struct(days=2):
    old = datetime.now(tz=timezone.utc) - timedelta(days=days)
    return (old.year, old.month, old.day, old.hour, old.minute, old.second, 0, 0, 0)


def _mock_feed(entries):
    feed = MagicMock()
    feed.entries = entries
    return feed


class TestAITrackerSourceFetch:
    def test_returns_recent_entries(self):
        entry = _make_entry(published_parsed=_now_struct())
        with patch("src.sources.ai_tracker.httpx.Client") as mock_client_cls, \
             patch("src.sources.ai_tracker.feedparser.parse", return_value=_mock_feed([entry])):
            mock_client_cls.return_value.__enter__.return_value.get.return_value = MagicMock(
                text="<rss/>", raise_for_status=lambda: None
            )
            source = AITrackerSource(hours_back=24, extra_feeds=[])
            source._feeds = [("TestFeed", "https://example.com/feed")]
            results = source.fetch()

        assert len(results) == 1
        assert results[0]["title"] == "Test Post"
        assert results[0]["source"] == "ai_tracker"
        assert results[0]["feed"] == "TestFeed"

    def test_filters_old_entries(self):
        old_entry = _make_entry("Old", published_parsed=_old_struct(days=2))
        with patch("src.sources.ai_tracker.httpx.Client") as mock_client_cls, \
             patch("src.sources.ai_tracker.feedparser.parse", return_value=_mock_feed([old_entry])):
            mock_client_cls.return_value.__enter__.return_value.get.return_value = MagicMock(
                text="<rss/>", raise_for_status=lambda: None
            )
            source = AITrackerSource(hours_back=24, extra_feeds=[])
            source._feeds = [("TestFeed", "https://example.com/feed")]
            results = source.fetch()

        assert results == []

    def test_includes_undated_entries(self):
        """Entries without a date should be included (some feeds omit dates)."""
        entry = _make_entry("No date")  # no published_parsed
        with patch("src.sources.ai_tracker.httpx.Client") as mock_client_cls, \
             patch("src.sources.ai_tracker.feedparser.parse", return_value=_mock_feed([entry])):
            mock_client_cls.return_value.__enter__.return_value.get.return_value = MagicMock(
                text="<rss/>", raise_for_status=lambda: None
            )
            source = AITrackerSource(hours_back=24, extra_feeds=[])
            source._feeds = [("TestFeed", "https://example.com/feed")]
            results = source.fetch()

        assert len(results) == 1

    def test_deduplicates_across_feeds(self):
        entry = _make_entry("Same", link="https://example.com/same", published_parsed=_now_struct())
        with patch("src.sources.ai_tracker.httpx.Client") as mock_client_cls, \
             patch("src.sources.ai_tracker.feedparser.parse", return_value=_mock_feed([entry])):
            mock_client_cls.return_value.__enter__.return_value.get.return_value = MagicMock(
                text="<rss/>", raise_for_status=lambda: None
            )
            source = AITrackerSource(hours_back=24, extra_feeds=[])
            source._feeds = [("Feed1", "https://f1.com/feed"), ("Feed2", "https://f2.com/feed")]
            results = source.fetch()

        assert len(results) == 1

    def test_failed_feed_does_not_abort_others(self):
        good_entry = _make_entry("Good", published_parsed=_now_struct())

        def mock_get(url, **kwargs):
            if "bad" in url:
                raise Exception("connection refused")
            resp = MagicMock()
            resp.text = "<rss/>"
            resp.raise_for_status = lambda: None
            return resp

        with patch("src.sources.ai_tracker.httpx.Client") as mock_client_cls, \
             patch("src.sources.ai_tracker.feedparser.parse", return_value=_mock_feed([good_entry])):
            mock_client_cls.return_value.__enter__.return_value.get.side_effect = mock_get
            source = AITrackerSource(hours_back=24, extra_feeds=[])
            source._feeds = [
                ("Bad", "https://bad.example.com/feed"),
                ("Good", "https://good.example.com/feed"),
            ]
            results = source.fetch()

        assert len(results) == 1

    def test_story_fields(self):
        entry = _make_entry("My Title", "https://example.com/post", published_parsed=_now_struct())
        with patch("src.sources.ai_tracker.httpx.Client") as mock_client_cls, \
             patch("src.sources.ai_tracker.feedparser.parse", return_value=_mock_feed([entry])):
            mock_client_cls.return_value.__enter__.return_value.get.return_value = MagicMock(
                text="<rss/>", raise_for_status=lambda: None
            )
            source = AITrackerSource(hours_back=24, extra_feeds=[])
            source._feeds = [("Anthropic", "https://anthropic.com/rss")]
            results = source.fetch()

        r = results[0]
        assert r["objectID"].startswith("ai_")
        assert r["url"] == "https://example.com/post"
        assert r["author"] == "Anthropic"
        assert r["score"] == 0
        assert r["source"] == "ai_tracker"


class TestHelpers:
    def test_entry_id_uses_link(self):
        entry = {"link": "https://example.com/post"}
        assert _entry_id(entry).startswith("ai_")

    def test_entry_id_stable(self):
        entry = {"link": "https://example.com/post"}
        assert _entry_id(entry) == _entry_id(entry)

    def test_parse_entry_date_published(self):
        t = _now_struct()
        entry = {"published_parsed": t}
        result = _parse_entry_date(entry)
        assert isinstance(result, datetime)

    def test_parse_entry_date_falls_back_to_updated(self):
        t = _now_struct()
        entry = {"updated_parsed": t}
        result = _parse_entry_date(entry)
        assert isinstance(result, datetime)

    def test_parse_entry_date_none_when_missing(self):
        assert _parse_entry_date({}) is None
