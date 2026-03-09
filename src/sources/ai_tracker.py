"""AI industry tracker — aggregates RSS/Atom feeds from key AI sources.

Uses httpx (already a project dependency) to fetch feed content with a
timeout, then feedparser to parse entries.  This avoids the uncontrollable
default urllib timeout in feedparser itself.
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone

import feedparser
import httpx

logger = logging.getLogger(__name__)

DEFAULT_FEEDS: list[tuple[str, str]] = [
    # --- Major labs ---
    # Anthropic has no official RSS — these are community-maintained mirrors
    ("Anthropic News",        "https://raw.githubusercontent.com/taobojlen/anthropic-rss-feed/main/anthropic_news_rss.xml"),
    ("Anthropic Engineering", "https://raw.githubusercontent.com/conoro/anthropic-engineering-rss-feed/main/anthropic_engineering_rss.xml"),
    ("OpenAI",                "https://openai.com/blog/rss.xml"),
    ("Google DeepMind",       "https://deepmind.google/blog/rss.xml"),
    ("Meta Engineering",      "https://engineering.fb.com/feed/"),       # covers Meta AI research
    ("Microsoft Research",    "https://www.microsoft.com/en-us/research/feed/"),

    # --- High-signal newsletters ---
    ("Import AI",             "https://importai.substack.com/feed"),      # Jack Clark (Anthropic co-founder), weekly
    ("Interconnects",         "https://www.interconnects.ai/feed"),       # Nathan Lambert, RLHF / open models
    ("Ahead of AI",           "https://magazine.sebastianraschka.com/feed"),  # Sebastian Raschka, ML papers
    ("Last Week in AI",       "https://lastweekin.ai/feed"),              # weekly roundup

    # --- Research & practitioner blogs ---
    ("Simon Willison",        "https://simonwillison.net/atom/everything/"),
    ("The Gradient",          "https://thegradient.pub/rss/"),            # academic-leaning long-form
    ("Hugging Face",          "https://huggingface.co/blog/feed.xml"),
    ("Alignment Forum",       "https://www.alignmentforum.org/feed.xml"), # AI safety / agent research
]

_HEADERS = {"User-Agent": "signal-brief/1.0 (RSS reader; +https://github.com/adrianchung/signal-brief)"}


class AITrackerSource:
    """Fetches recent entries from curated AI industry RSS/Atom feeds."""

    def __init__(
        self,
        hours_back: int = 24,
        extra_feeds: list[tuple[str, str]] | None = None,
    ) -> None:
        self._hours_back = hours_back
        self._feeds = DEFAULT_FEEDS + (extra_feeds or [])

    def fetch(self) -> list[dict]:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=self._hours_back)
        stories: list[dict] = []
        seen_ids: set[str] = set()

        with httpx.Client(timeout=15, follow_redirects=True, headers=_HEADERS) as client:
            for feed_name, feed_url in self._feeds:
                try:
                    stories.extend(self._fetch_feed(client, feed_name, feed_url, cutoff, seen_ids))
                except Exception:
                    logger.exception("AI tracker: failed to fetch %s (%s)", feed_name, feed_url)

        logger.info("AI tracker: fetched %d items across %d feeds", len(stories), len(self._feeds))
        return stories

    def _fetch_feed(
        self,
        client: httpx.Client,
        name: str,
        url: str,
        cutoff: datetime,
        seen_ids: set[str],
    ) -> list[dict]:
        response = client.get(url)
        response.raise_for_status()
        feed = feedparser.parse(response.text)

        results: list[dict] = []
        for entry in feed.entries:
            obj_id = _entry_id(entry)
            if obj_id in seen_ids:
                continue

            published = _parse_entry_date(entry)
            # Include undated entries (some feeds omit dates); skip confirmed-old ones
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
                "source": "ai_tracker",
                "feed": name,
            })

        return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _entry_id(entry: dict) -> str:
    raw = entry.get("id") or entry.get("link") or entry.get("title", "")
    return "ai_" + hashlib.sha1(raw.encode()).hexdigest()[:16]


def _parse_entry_date(entry: dict) -> datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        t = entry.get(attr)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                continue
    return None
