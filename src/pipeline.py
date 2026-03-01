import logging
from typing import TYPE_CHECKING

from src.analysis import get_analyzer
from src.delivery import get_deliverers
from src.sources.hackernews import fetch_stories

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger(__name__)

NO_STORIES_MSG = "No stories matched filters in the past 12 hours."


def _print_brief(brief: str) -> None:
    width = 72
    print("\n" + "─" * width)
    print(" SIGNAL BRIEF")
    print("─" * width)
    print(brief)
    print("─" * width + "\n")


def run_pipeline(config: "Settings", provider: str = "gemini") -> None:
    logger.info("Pipeline started (provider=%s)", provider)

    stories = fetch_stories(config.keyword_list, config.min_score)
    logger.info("Fetched %d stories", len(stories))

    if stories:
        brief = get_analyzer(config, provider).analyze(stories, config.keyword_list)
    else:
        brief = NO_STORIES_MSG

    _print_brief(brief)

    deliverers = get_deliverers(config)
    if not deliverers:
        logger.warning("No delivery channels configured — brief will not be sent")
        return

    for deliverer in deliverers:
        name = type(deliverer).__name__
        try:
            deliverer.send(brief)
            logger.info("%s: sent successfully", name)
        except Exception:
            logger.exception("%s: delivery failed", name)

    logger.info("Pipeline complete")
