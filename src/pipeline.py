import logging
from typing import TYPE_CHECKING

from src.alerting import send_alert
from src.analysis import get_analyzer
from src.delivery import get_deliverers
from src.ranking import rank_stories
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


def run_pipeline(config: "Settings", provider: str = "gemini", dry_run: bool = False) -> None:
    logger.info("Pipeline started (provider=%s, dry_run=%s)", provider, dry_run)

    try:
        stories = fetch_stories(config.keyword_list, config.min_score)
    except Exception as exc:
        logger.exception("Fetch step failed")
        if not dry_run:
            send_alert(config, "fetch", exc)
        return

    logger.info("Fetched %d stories", len(stories))

    if stories:
        try:
            stories = rank_stories(stories, config.keyword_list, config.top_n_stories)
            brief = get_analyzer(config, provider).analyze(stories, config.keyword_list)
        except Exception as exc:
            logger.exception("Analyze step failed")
            if not dry_run:
                send_alert(config, "analyze", exc)
            return
    else:
        brief = NO_STORIES_MSG

    _print_brief(brief)

    if dry_run:
        logger.info("Dry-run mode — skipping delivery")
        return

    deliverers = get_deliverers(config)
    if not deliverers:
        logger.warning("No delivery channels configured — brief will not be sent")
        return

    successes = 0
    last_exc: Exception | None = None
    for deliverer in deliverers:
        name = type(deliverer).__name__
        try:
            deliverer.send(brief)
            logger.info("%s: sent successfully", name)
            successes += 1
        except Exception as exc:
            logger.exception("%s: delivery failed", name)
            last_exc = exc

    if successes == 0 and last_exc is not None:
        send_alert(config, "delivery", last_exc)

    logger.info("Pipeline complete")
