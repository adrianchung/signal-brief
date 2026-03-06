import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.delivery import get_deliverers

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger(__name__)

_CHANNEL_PREFIXES = {"slack": "Slack", "ntfy": "Ntfy", "sms": "SMS"}


def send_alert(config: "Settings", step: str, error: Exception) -> None:
    """Send a plain-text error alert via a configured delivery channel.

    Respects ALERT_CHANNEL if set; otherwise falls back to the first available
    channel. Swallows exceptions so that alerting never crashes the caller.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    message = (
        f"[signal-brief] pipeline error\n"
        f"Step: {step}\n"
        f"Time: {timestamp}\n"
        f"Error: {type(error).__name__}: {error}"
    )

    deliverer = _pick_deliverer(config)
    if deliverer is None:
        logger.warning("No delivery channel available to send error alert")
        return

    try:
        deliverer.send(message)
        logger.info("Error alert sent via %s", type(deliverer).__name__)
    except Exception:
        logger.exception("Failed to send error alert")


def _pick_deliverer(config: "Settings"):
    deliverers = get_deliverers(config)
    if not deliverers:
        return None

    preferred = (config.alert_channel or "").strip().lower()
    if preferred:
        for d in deliverers:
            if type(d).__name__.lower().startswith(preferred):
                return d
        logger.warning(
            "ALERT_CHANNEL=%r not available — falling back to first channel", preferred
        )

    return deliverers[0]
