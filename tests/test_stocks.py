"""Tests for src/sources/stocks.py — StocksSource."""

from unittest.mock import MagicMock, patch

from src.sources.stocks import StocksSource, _hn_mention_count


def _make_fast_info(last_price, previous_close):
    info = MagicMock()
    info.last_price = last_price
    info.previous_close = previous_close
    return info


class TestStocksSource:
    def _fetch_with_mock(self, tickers, last_price, prev_close, threshold=3.0):
        mock_ticker = MagicMock()
        mock_ticker.fast_info = _make_fast_info(last_price, prev_close)

        with patch("src.sources.stocks.yfinance") as mock_yf, \
             patch("src.sources.stocks._hn_mention_count", return_value=0):
            mock_yf.Ticker.return_value = mock_ticker
            source = StocksSource(tickers=tickers, move_threshold=threshold)
            return source.fetch()

    def test_significant_mover_included(self):
        # 5% up — above default 3% threshold
        results = self._fetch_with_mock(["NVDA"], last_price=105.0, prev_close=100.0)
        assert len(results) == 1
        assert "NVDA" in results[0]["title"]
        assert "▲" in results[0]["title"]

    def test_down_mover_included(self):
        # 5% down
        results = self._fetch_with_mock(["MSFT"], last_price=95.0, prev_close=100.0)
        assert len(results) == 1
        assert "▼" in results[0]["title"]

    def test_small_move_filtered_out(self):
        # 1% — below 3% threshold
        results = self._fetch_with_mock(["AAPL"], last_price=101.0, prev_close=100.0)
        assert results == []

    def test_custom_threshold(self):
        # 2% move passes a 1% threshold
        results = self._fetch_with_mock(["META"], last_price=102.0, prev_close=100.0, threshold=1.0)
        assert len(results) == 1

    def test_story_fields(self):
        results = self._fetch_with_mock(["NVDA"], last_price=110.0, prev_close=100.0)
        r = results[0]
        assert r["objectID"].startswith("stock_")
        assert r["source"] == "stocks"
        assert r["url"] == "https://finance.yahoo.com/quote/NVDA"
        assert r["score"] > 0  # synthetic score from pct change

    def test_objectid_stable_within_day(self):
        r1 = self._fetch_with_mock(["NVDA"], 110.0, 100.0)
        r2 = self._fetch_with_mock(["NVDA"], 112.0, 100.0)  # different price, same day
        assert r1[0]["objectID"] == r2[0]["objectID"]

    def test_failed_ticker_does_not_abort_others(self):
        mock_nvda = MagicMock()
        mock_nvda.fast_info = _make_fast_info(110.0, 100.0)

        mock_msft = MagicMock()
        mock_msft.fast_info.last_price = None  # causes skip

        def side_effect(ticker):
            return mock_nvda if ticker == "NVDA" else mock_msft

        with patch("src.sources.stocks.yfinance") as mock_yf, \
             patch("src.sources.stocks._hn_mention_count", return_value=0):
            mock_yf.Ticker.side_effect = side_effect
            source = StocksSource(tickers=["NVDA", "MSFT"], move_threshold=3.0)
            results = source.fetch()

        assert len(results) == 1
        assert "NVDA" in results[0]["title"]

    def test_zero_prev_close_skipped(self):
        results = self._fetch_with_mock(["TSLA"], last_price=100.0, prev_close=0.0)
        assert results == []


class TestHnMentionCount:
    def test_returns_count_on_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"nbHits": 7}
        mock_resp.raise_for_status = lambda: None

        with patch("src.sources.stocks.httpx.get", return_value=mock_resp):
            assert _hn_mention_count("NVDA", "NVIDIA") == 7

    def test_returns_zero_on_error(self):
        with patch("src.sources.stocks.httpx.get", side_effect=Exception("timeout")):
            assert _hn_mention_count("NVDA", "NVIDIA") == 0
