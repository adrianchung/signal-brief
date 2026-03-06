import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.analysis import get_analyzer
from src.delivery import get_deliverers
from src.dedup import SeenStoryTracker
from src.history import RunLogger
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


def run_pipeline(
    config: "Settings",
    provider: str = "gemini",
    dry_run: bool = False,
    ignore_seen: bool = False,
) -> None:
    logger.info(
        "Pipeline started (provider=%s, dry_run=%s, ignore_seen=%s)",
        provider, dry_run, ignore_seen,
    )

    run_log = RunLogger(config.history_path, config.history_retention_days)
    record: dict = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "provider": provider,
        "dry_run": dry_run,
        "stories_fetched": 0,
        "stories_after_dedup": 0,
        "brief": "",
        "delivery": {},
        "status": "ok",
    }

    try:
        stories = fetch_stories(config.keyword_list, config.min_score)
    except Exception as exc:
        logger.exception("Fetch step failed")
        record["status"] = "fetch_error"
        record["brief"] = str(exc)
        if not dry_run:
            from src.alerting import send_error_alert
            send_error_alert(config, "fetch", exc)
        run_log.write(record)
        return

    record["stories_fetched"] = len(stories)
    logger.info("Fetched %d stories", len(stories))

    tracker = SeenStoryTracker(config.seen_stories_path, config.dedup_window_days)

    if not ignore_seen:
        stories = tracker.filter_new(stories)
        logger.info("%d stories after dedup filter", len(stories))

    record["stories_after_dedup"] = len(stories)

    if stories:
        stories = rank_stories(stories, config.keyword_list, config.top_n_stories)
        try:
            brief = get_analyzer(config, provider).analyze(stories, config.keyword_list)
        except Exception as exc:
            logger.exception("Analysis step failed")
            record["status"] = "analysis_error"
            record["brief"] = str(exc)
            if not dry_run:
                from src.alerting import send_error_alert
                send_error_alert(config, "analyze", exc)
            run_log.write(record)
            return
    else:
        brief = NO_STORIES_MSG
        record["status"] = "no_stories"

    record["brief"] = brief
    _print_brief(brief)

    if dry_run:
        logger.info("Dry-run mode — skipping delivery and seen-story recording")
        run_log.write(record)
        return

    # Mark stories as seen before delivery so a crash mid-delivery doesn't
    # cause the same stories to be re-analysed on the next run.
    if not ignore_seen and stories:
        tracker.mark_seen(stories)

    deliverers = get_deliverers(config)
    if not deliverers:
        logger.warning("No delivery channels configured — brief will not be sent")
        run_log.write(record)
        return

    all_failed = True
    for deliverer in deliverers:
        name = type(deliverer).__name__
        try:
            deliverer.send(brief)
            logger.info("%s: sent successfully", name)
            record["delivery"][name] = "ok"
            all_failed = False
        except Exception as exc:
            logger.exception("%s: delivery failed", name)
            record["delivery"][name] = f"failed: {exc}"

    if all_failed:
        record["status"] = "delivery_error"
        from src.alerting import send_error_alert
        send_error_alert(config, "deliver", RuntimeError("All delivery channels failed"))

    run_log.write(record)
    logger.info("Pipeline complete")
