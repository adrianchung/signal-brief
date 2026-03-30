"""Personal/engineering blog RSS feeds source.

Always enabled when ``blog_feeds`` config entries are present.  Uses the
same httpx + feedparser infrastructure as ai_tracker but operates on a
user-configured feed list instead of a hard-coded DEFAULT_FEEDS catalogue.
"""

import logging
from datetime import datetime, timedelta, timezone

import feedparser
import httpx

from src.sources.ai_tracker import _entry_id, _parse_entry_date

logger = logging.getLogger(__name__)

_HEADERS = {"User-Agent": "signal-brief/1.0 (RSS reader; +https://github.com/adrianchung/signal-brief)"}


class BlogFeedsSource:
    """Fetches recent posts from a list of personal/engineering blog RSS feeds."""

    def __init__(self, feeds: list[tuple[str, str]], hours_back: int = 12) -> None:
        self._feeds = feeds
        self._hours_back = hours_back

    def fetch(self) -> list[dict]:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=self._hours_back)
        stories: list[dict] = []
        seen_ids: set[str] = set()

        with httpx.Client(timeout=15, follow_redirects=True, headers=_HEADERS) as client:
            for feed_name, feed_url in self._feeds:
                try:
                    stories.extend(self._fetch_feed(client, feed_name, feed_url, cutoff, seen_ids))
                except Exception:
                    logger.exception("blog_feeds: failed to fetch %s (%s)", feed_name, feed_url)

        logger.info("blog_feeds: fetched %d items across %d feeds", len(stories), len(self._feeds))
        return stories

    def _fetch_feed(self, client, name, url, cutoff, seen_ids):
        response = client.get(url)
        response.raise_for_status()
        feed = feedparser.parse(response.text)

        results: list[dict] = []
        for entry in feed.entries:
            obj_id = _entry_id(entry)
            if obj_id in seen_ids:
                continue

            published = _parse_entry_date(entry)
            if published is not None and published < cutoff:
                continue

            seen_ids.add(obj_id)
            results.append({
                "objectID": obj_id,
                "title": entry.get("title", "(no title)").strip(),
                "url": entry.get("link", url),
                "score": 0,
                "author": name,
                "created_at": published.strftime("%Y-%m-%d %H:%M UTC") if published else "",
                "num_comments": 0,
                "source": "blog_feeds",
                "feed": name,
            })

        return results
