import time
from datetime import datetime, timezone

import httpx

HN_ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"


def fetch_stories(keywords: list[str], min_score: int, hours_back: int = 12) -> list[dict]:
    since_timestamp = int(time.time()) - hours_back * 3600
    seen: dict[str, dict] = {}

    with httpx.Client(timeout=15) as client:
        for keyword in keywords:
            params = {
                "query": keyword,
                "tags": "story",
                "numericFilters": f"created_at_i>{since_timestamp},points>{min_score}",
                "hitsPerPage": 50,
            }
            try:
                response = client.get(HN_ALGOLIA_URL, params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError:
                continue

            for hit in data.get("hits", []):
                obj_id = hit.get("objectID")
                if obj_id and obj_id not in seen:
                    seen[obj_id] = {
                        "title": hit.get("title", ""),
                        "url": hit.get("url") or f"https://news.ycombinator.com/item?id={obj_id}",
                        "score": hit.get("points", 0),
                        "author": hit.get("author", ""),
                        "created_at": _parse_created_at(hit.get("created_at_i")),
                        "num_comments": hit.get("num_comments", 0),
                    }

    return sorted(seen.values(), key=lambda s: s["score"], reverse=True)


def _parse_created_at(timestamp: int | None) -> str:
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
