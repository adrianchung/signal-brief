from datetime import timezone, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.sources.hackernews import _parse_created_at, fetch_stories


class TestParseCreatedAt:
    def test_none_returns_empty_string(self):
        assert _parse_created_at(None) == ""

    def test_known_timestamp(self):
        # 2024-01-15 12:00:00 UTC
        ts = int(datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc).timestamp())
        result = _parse_created_at(ts)
        assert result == "2024-01-15 12:00 UTC"

    def test_returns_string(self):
        assert isinstance(_parse_created_at(1700000000), str)


class TestFetchStories:
    def _make_hit(self, obj_id, title, score, url=None):
        return {
            "objectID": obj_id,
            "title": title,
            "points": score,
            "url": url or f"https://example.com/{obj_id}",
            "author": "user",
            "num_comments": 10,
            "created_at_i": 1700000000,
        }

    def _mock_response(self, hits):
        resp = MagicMock()
        resp.json.return_value = {"hits": hits}
        resp.raise_for_status.return_value = None
        return resp

    def test_returns_sorted_by_score_descending(self):
        hits = [
            self._make_hit("1", "Low score", 100),
            self._make_hit("2", "High score", 500),
            self._make_hit("3", "Mid score", 300),
        ]
        mock_client = MagicMock()
        mock_client.get.return_value = self._mock_response(hits)

        with patch("src.sources.hackernews.httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_client
            results = fetch_stories(["ai"], min_score=50)

        assert results[0]["score"] == 500
        assert results[1]["score"] == 300
        assert results[2]["score"] == 100

    def test_deduplicates_across_keywords(self):
        hit = self._make_hit("42", "Shared story", 200)
        mock_client = MagicMock()
        mock_client.get.return_value = self._mock_response([hit])

        with patch("src.sources.hackernews.httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_client
            results = fetch_stories(["ai", "ml", "llm"], min_score=50)

        # Same objectID returned for all 3 keywords — should appear once
        assert len(results) == 1
        assert results[0]["title"] == "Shared story"

    def test_falls_back_to_hn_url_when_url_missing(self):
        hit = self._make_hit("99", "No URL story", 200, url=None)
        hit["url"] = None  # explicitly None
        mock_client = MagicMock()
        mock_client.get.return_value = self._mock_response([hit])

        with patch("src.sources.hackernews.httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_client
            results = fetch_stories(["ai"], min_score=50)

        assert results[0]["url"] == "https://news.ycombinator.com/item?id=99"

    def test_http_error_on_one_keyword_skipped(self):
        import httpx

        good_hit = self._make_hit("1", "Good story", 200)
        good_response = self._mock_response([good_hit])
        error_response = MagicMock()
        error_response.get.side_effect = httpx.HTTPError("timeout")

        mock_client = MagicMock()
        # First keyword raises, second succeeds
        mock_client.get.side_effect = [
            httpx.HTTPError("timeout"),
            good_response,
        ]

        with patch("src.sources.hackernews.httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_client
            results = fetch_stories(["bad-kw", "good-kw"], min_score=50)

        assert len(results) == 1
        assert results[0]["title"] == "Good story"

    def test_empty_results_when_no_hits(self):
        mock_client = MagicMock()
        mock_client.get.return_value = self._mock_response([])

        with patch("src.sources.hackernews.httpx.Client") as mock_cls:
            mock_cls.return_value.__enter__.return_value = mock_client
            results = fetch_stories(["ai"], min_score=50)

        assert results == []
