"""Stock market mover source.

Fetches daily price data for configured tickers via yfinance and filters
for significant movers.  Optionally cross-references HN (via the Algolia
API) for community discussion around the same companies.
"""

import hashlib
import logging
import time
from datetime import datetime, timezone

import httpx
import yfinance

logger = logging.getLogger(__name__)

# Lookup table: ticker → common name used in HN searches
_COMPANY_NAMES: dict[str, str] = {
    "NVDA":  "NVIDIA",
    "MSFT":  "Microsoft",
    "GOOGL": "Google",
    "AAPL":  "Apple",
    "META":  "Meta",
    "AMZN":  "Amazon",
    "TSLA":  "Tesla",
    "ORCL":  "Oracle",
    "AMD":   "AMD",
    "INTC":  "Intel",
    "NFLX":  "Netflix",
    "CRM":   "Salesforce",
    "SNOW":  "Snowflake",
    "PLTR":  "Palantir",
    "COIN":  "Coinbase",
}


class StocksSource:
    """Surfaces significant daily stock movers using yfinance."""

    def __init__(
        self,
        tickers: list[str],
        move_threshold: float = 3.0,
        hn_keywords: list[str] | None = None,
    ) -> None:
        self._tickers = tickers
        self._threshold = move_threshold
        self._hn_keywords = hn_keywords or []

    def fetch(self) -> list[dict]:
        today = datetime.now(tz=timezone.utc)
        today_str = today.strftime("%Y-%m-%d %H:%M UTC")
        date_key = today.strftime("%Y-%m-%d")

        stories: list[dict] = []

        for ticker in self._tickers:
            try:
                info = yfinance.Ticker(ticker).fast_info
                price = info.last_price
                prev_close = info.previous_close
                if not price or not prev_close or prev_close == 0:
                    continue

                pct = (price - prev_close) / prev_close * 100
                if abs(pct) < self._threshold:
                    continue

                company = _COMPANY_NAMES.get(ticker, ticker)
                direction = "▲" if pct > 0 else "▼"
                title = f"{ticker} ({company}): {direction}{abs(pct):.1f}% — ${price:.2f}"
                obj_id = "stock_" + hashlib.sha1(f"{ticker}_{date_key}".encode()).hexdigest()[:16]

                stories.append({
                    "objectID": obj_id,
                    "title": title,
                    "url": f"https://finance.yahoo.com/quote/{ticker}",
                    "score": int(abs(pct) * 10),  # synthetic score for ranking
                    "author": "Yahoo Finance",
                    "created_at": today_str,
                    "num_comments": _hn_mention_count(ticker, company),
                    "source": "stocks",
                    "feed": "Market Movers",
                })
            except Exception:
                logger.exception("Stocks: failed to fetch %s", ticker)

        logger.info("Stocks: %d mover(s) above %.1f%% threshold", len(stories), self._threshold)
        return stories


def _hn_mention_count(ticker: str, company: str) -> int:
    """Return the number of recent HN posts mentioning the ticker or company.

    Returns 0 on any error (network, timeout, etc.) — this is best-effort
    context enrichment, not critical data.
    """
    since = int(time.time()) - 24 * 3600
    query = company if company != ticker else ticker
    try:
        resp = httpx.get(
            "https://hn.algolia.com/api/v1/search",
            params={"query": query, "tags": "story", "numericFilters": f"created_at_i>{since}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("nbHits", 0)
    except Exception:
        return 0
