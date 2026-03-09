import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.analysis import get_analyzer
from src.delivery import get_deliverers
from src.dedup import SeenStoryTracker
from src.history import RunLogger
from src.ranking import rank_stories
from src.sources import get_sources

if TYPE_CHECKING:
    from src.config import Settings
    from src.profiles import DigestProfile

logger = logging.getLogger(__name__)

NO_STORIES_MSG = "No stories matched filters in the past 12 hours."

_PROVIDER_KEY_VARS = {"gemini": "GEMINI_API_KEY", "claude": "ANTHROPIC_API_KEY"}


def _provider_key_available(config: "Settings", provider: str) -> bool:
    """Return True if the API key for *provider* is set in config."""
    if provider == "claude":
        return bool(config.anthropic_api_key)
    if provider == "gemini":
        return bool(config.gemini_api_key)
    return False


def _print_brief(brief: str) -> None:
    width = 72
    print("\n" + "─" * width)
    print(" SIGNAL BRIEF")
    print("─" * width)
    print(brief)
    print("─" * width + "\n")


def _merge_stories(all_stories: list[dict]) -> list[dict]:
    """Deduplicate by objectID, preserving first occurrence."""
    seen: dict[str, dict] = {}
    for story in all_stories:
        obj_id = story.get("objectID")
        if obj_id and obj_id not in seen:
            seen[obj_id] = story
        elif not obj_id:
            seen[id(story)] = story  # no objectID — keep as-is
    return list(seen.values())


def run_pipeline(
    config: "Settings",
    provider: str = "gemini",
    fallback_provider: "str | None" = None,
    dry_run: bool = False,
    ignore_seen: bool = False,
    profile: "DigestProfile | None" = None,
) -> bool:
    """Run the full pipeline.  Returns True on success, False on error."""
    profile_name = profile.name if profile else "default"
    keywords = profile.keywords if profile else config.keyword_list
    style_hint = profile.style if profile else ""

    logger.info(
        "Pipeline started (provider=%s, fallback=%s, profile=%s, dry_run=%s, ignore_seen=%s)",
        provider, fallback_provider or "none", profile_name, dry_run, ignore_seen,
    )

    run_log = RunLogger(config.history_path, config.history_retention_days)
    record: dict = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "provider": provider,
        "profile": profile_name,
        "dry_run": dry_run,
        "stories_fetched": 0,
        "stories_after_dedup": 0,
        "brief": "",
        "delivery": {},
        "status": "ok",
    }

    # --- Fetch from all enabled sources ---
    raw_stories: list[dict] = []
    active_source_names: list[str] = []
    any_source_succeeded = False

    for source in get_sources(config, keywords):
        source_label = type(source).__name__
        try:
            items = source.fetch()
            any_source_succeeded = True
            raw_stories.extend(items)
            for s in items:
                sv = s.get("source", source_label)
                if sv not in active_source_names:
                    active_source_names.append(sv)
            logger.info("%s: fetched %d items", source_label, len(items))
        except Exception as exc:
            logger.exception("%s: fetch failed", source_label)
            if not dry_run:
                from src.alerting import send_error_alert
                send_error_alert(config, "fetch", exc)

    if not any_source_succeeded:
        # Every source raised — nothing to show
        record["status"] = "fetch_error"
        record["brief"] = "All sources failed to fetch"
        run_log.write(record)
        return False

    stories = _merge_stories(raw_stories)
    record["stories_fetched"] = len(stories)
    logger.info("Fetched %d stories total (after merge)", len(stories))

    tracker = SeenStoryTracker(config.seen_stories_path, config.dedup_window_days)

    if not ignore_seen:
        stories = tracker.filter_new(stories)
        logger.info("%d stories after dedup filter", len(stories))

    record["stories_after_dedup"] = len(stories)

    if stories:
        stories = rank_stories(stories, keywords, config.top_n_stories)
        try:
            brief = get_analyzer(config, provider).analyze(
                stories, keywords, style_hint, active_source_names
            )
        except Exception as primary_exc:
            if fallback_provider and fallback_provider != provider:
                if not _provider_key_available(config, fallback_provider):
                    key_var = _PROVIDER_KEY_VARS.get(fallback_provider, "API key")
                    logger.error(
                        "Primary provider %s failed and fallback %s is not usable: "
                        "%s is not configured. Add it to your environment/secrets.",
                        provider, fallback_provider, key_var,
                    )
                    record["status"] = "analysis_error"
                    record["brief"] = str(primary_exc)
                    if not dry_run:
                        from src.alerting import send_error_alert
                        send_error_alert(config, "analyze", primary_exc)
                    run_log.write(record)
                    return False
                logger.warning(
                    "Primary provider %s failed (%s) — trying fallback %s",
                    provider, primary_exc, fallback_provider,
                )
                try:
                    brief = get_analyzer(config, fallback_provider).analyze(
                        stories, keywords, style_hint, active_source_names
                    )
                    logger.info("Fallback provider %s succeeded", fallback_provider)
                except Exception as fallback_exc:
                    logger.exception("Fallback provider %s also failed", fallback_provider)
                    record["status"] = "analysis_error"
                    record["brief"] = f"Primary ({provider}): {primary_exc}; Fallback ({fallback_provider}): {fallback_exc}"
                    if not dry_run:
                        from src.alerting import send_error_alert
                        send_error_alert(config, "analyze", fallback_exc)
                    run_log.write(record)
                    return False
            else:
                logger.exception("Analysis step failed")
                record["status"] = "analysis_error"
                record["brief"] = str(primary_exc)
                if not dry_run:
                    from src.alerting import send_error_alert
                    send_error_alert(config, "analyze", primary_exc)
                run_log.write(record)
                return False
    else:
        brief = NO_STORIES_MSG
        record["status"] = "no_stories"

    record["brief"] = brief
    _print_brief(brief)

    if dry_run:
        logger.info("Dry-run mode — skipping delivery and seen-story recording")
        run_log.write(record)
        return True

    if not ignore_seen and stories:
        tracker.mark_seen(stories)

    deliverers = get_deliverers(config)
    if not deliverers:
        logger.warning("No delivery channels configured — brief will not be sent")
        run_log.write(record)
        return True

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
        return False

    run_log.write(record)
    logger.info("Pipeline complete")
    return True
