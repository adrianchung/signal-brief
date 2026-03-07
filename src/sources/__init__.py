from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from src.config import Settings


class Source(Protocol):
    def fetch(self) -> list[dict]: ...


def get_sources(config: "Settings", keywords: list[str] | None = None) -> list[Source]:
    """Return all enabled source instances.

    *keywords* override ``config.keyword_list`` for the HN source (used by
    named profiles). Other sources use their own configuration.
    """
    from src.sources.hackernews import HackerNewsSource

    kws = keywords if keywords is not None else config.keyword_list
    sources: list[Source] = [HackerNewsSource(kws, config.min_score)]

    if config.enable_ai_tracker:
        from src.sources.ai_tracker import AITrackerSource
        sources.append(AITrackerSource(
            hours_back=config.ai_tracker_hours_back,
            extra_feeds=config.ai_tracker_extra_feed_list,
        ))

    if config.enable_stocks:
        from src.sources.stocks import StocksSource
        sources.append(StocksSource(
            tickers=config.stock_ticker_list,
            move_threshold=config.stock_move_threshold,
            hn_keywords=kws,
        ))

    return sources
