import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src.pipeline import run_pipeline

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger(__name__)


def start(config: "Settings", provider: str = "gemini") -> None:
    scheduler = BlockingScheduler()

    for time_str in config.schedule_time_list:
        try:
            hour, minute = time_str.strip().split(":")
            trigger = CronTrigger(hour=int(hour), minute=int(minute))
            scheduler.add_job(run_pipeline, trigger=trigger, args=[config, provider])
            logger.info("Scheduled job at %s", time_str)
        except (ValueError, AttributeError):
            logger.error("Invalid schedule time format: %r (expected HH:MM)", time_str)

    if not scheduler.get_jobs():
        logger.error("No valid schedule times configured — exiting")
        return

    logger.info("Scheduler started with %d job(s)", len(scheduler.get_jobs()))
    scheduler.start()
