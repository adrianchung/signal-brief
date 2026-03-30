"""Tests for src/sources/blog_feeds.py — BlogFeedsSource."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.sources.blog_feeds import BlogFeedsSource


def _now_struct():
    now = datetime.now(tz=timezone.utc)
    return (now.year, now.month, now.day, now.hour, now.minute, now.second, 0, 0, 0)


def _old_struct(days=2):
    old = datetime.now(tz=timezone.utc) - timedelta(days=days)
    return (old.year, old.month, old.day, old.hour, old.minute, old.second, 0, 0, 0)


def _make_entry(title="Test Post", link="https://example.com/post", published_parsed=None):
    entry = {"title": title, "link": link, "id": link}
    if published_parsed:
        entry["published_parsed"] = published_parsed
    return entry


def _mock_feed(entries):
    feed = MagicMock()
    feed.entries = entries
    return feed


class TestBlogFeedsSource:
    def test_returns_recent_entries(self):
        entry = _make_entry(published_parsed=_now_struct())
        with patch("src.sources.blog_feeds.httpx.Client") as mock_client_cls, \
             patch("src.sources.blog_feeds.feedparser.parse", return_value=_mock_feed([entry])):
            mock_client_cls.return_value.__enter__.return_value.get.return_value = MagicMock(
                text="<rss/>", raise_for_status=lambda: None
            )
            source = BlogFeedsSource(feeds=[("Addy Osmani", "https://addyosmani.com/rss.xml")])
            results = source.fetch()

        assert len(results) == 1
        assert results[0]["title"] == "Test Post"
        assert results[0]["source"] == "blog_feeds"
        assert results[0]["feed"] == "Addy Osmani"
        assert results[0]["author"] == "Addy Osmani"

    def test_filters_old_entries(self):
        old_entry = _make_entry("Old Post", published_parsed=_old_struct(days=2))
        with patch("src.sources.blog_feeds.httpx.Client") as mock_client_cls, \
             patch("src.sources.blog_feeds.feedparser.parse", return_value=_mock_feed([old_entry])):
            mock_client_cls.return_value.__enter__.return_value.get.return_value = MagicMock(
                text="<rss/>", raise_for_status=lambda: None
            )
            source = BlogFeedsSource(feeds=[("Addy Osmani", "https://addyosmani.com/rss.xml")], hours_back=12)
            results = source.fetch()

        assert results == []

    def test_includes_undated_entries(self):
        entry = _make_entry("No date")
        with patch("src.sources.blog_feeds.httpx.Client") as mock_client_cls, \
             patch("src.sources.blog_feeds.feedparser.parse", return_value=_mock_feed([entry])):
            mock_client_cls.return_value.__enter__.return_value.get.return_value = MagicMock(
                text="<rss/>", raise_for_status=lambda: None
            )
            source = BlogFeedsSource(feeds=[("Addy Osmani", "https://addyosmani.com/rss.xml")])
            results = source.fetch()

        assert len(results) == 1

    def test_failed_feed_does_not_abort_others(self):
        good_entry = _make_entry("Good Post", link="https://good.com/post", published_parsed=_now_struct())

        def mock_get(url, **kwargs):
            if "bad" in url:
                raise Exception("connection refused")
            resp = MagicMock()
            resp.text = "<rss/>"
            resp.raise_for_status = lambda: None
            return resp

        with patch("src.sources.blog_feeds.httpx.Client") as mock_client_cls, \
             patch("src.sources.blog_feeds.feedparser.parse", return_value=_mock_feed([good_entry])):
            mock_client_cls.return_value.__enter__.return_value.get.side_effect = mock_get
            source = BlogFeedsSource(feeds=[
                ("Bad Blog", "https://bad.example.com/feed"),
                ("Good Blog", "https://good.example.com/feed"),
            ])
            results = source.fetch()

        assert len(results) == 1

    def test_empty_feeds_list_returns_nothing(self):
        source = BlogFeedsSource(feeds=[])
        results = source.fetch()
        assert results == []

    def test_story_fields(self):
        entry = _make_entry("My Post", "https://addyosmani.com/post/1", published_parsed=_now_struct())
        with patch("src.sources.blog_feeds.httpx.Client") as mock_client_cls, \
             patch("src.sources.blog_feeds.feedparser.parse", return_value=_mock_feed([entry])):
            mock_client_cls.return_value.__enter__.return_value.get.return_value = MagicMock(
                text="<rss/>", raise_for_status=lambda: None
            )
            source = BlogFeedsSource(feeds=[("Addy Osmani", "https://addyosmani.com/rss.xml")])
            results = source.fetch()

        r = results[0]
        assert r["objectID"].startswith("ai_")
        assert r["url"] == "https://addyosmani.com/post/1"
        assert r["score"] == 0
        assert r["num_comments"] == 0
        assert r["source"] == "blog_feeds"


class TestBlogFeedConfig:
    def test_blog_feed_list_parses_default(self):
        from src.config import Settings
        s = Settings(gemini_api_key="x", _env_file=None)
        feeds = s.blog_feed_list
        assert ("Addy Osmani", "https://addyosmani.com/rss.xml") in feeds

    def test_blog_feed_list_multiple(self):
        from src.config import Settings
        s = Settings(
            gemini_api_key="x",
            blog_feeds="Blog A=https://a.com/rss,Blog B=https://b.com/feed",
            _env_file=None,
        )
        feeds = s.blog_feed_list
        assert feeds == [("Blog A", "https://a.com/rss"), ("Blog B", "https://b.com/feed")]

    def test_blog_feed_list_empty_string(self):
        from src.config import Settings
        s = Settings(gemini_api_key="x", blog_feeds="", _env_file=None)
        assert s.blog_feed_list == []
