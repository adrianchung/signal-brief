import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from src.delivery import get_deliverers

if TYPE_CHECKING:
    from src.config import Settings

logger = logging.getLogger(__name__)


def _format_alert(step: str, error: Exception) -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"[SIGNAL BRIEF ERROR]\n"
        f"Time: {timestamp}\n"
        f"Step: {step}\n"
        f"Error: {type(error).__name__}: {error}"
    )


def send_error_alert(config: "Settings", step: str, error: Exception) -> None:
    """Send an error alert via configured channels. Never raises."""
    message = _format_alert(step, error)
    alert_channel = getattr(config, "alert_channel", None)

    if alert_channel:
        _try_channel(config, alert_channel, message)
    else:
        # Fallback: try each available channel until one succeeds
        for deliverer in get_deliverers(config):
            name = type(deliverer).__name__
            try:
                deliverer.send(message)
                logger.info("Error alert sent via %s", name)
                return
            except Exception:
                logger.exception("Failed to send error alert via %s", name)
        logger.error("Could not deliver error alert via any channel")


def _try_channel(config: "Settings", channel: str, message: str) -> None:
    """Attempt to send an alert via the named channel. Logs on failure."""
    channel = channel.lower()
    try:
        if channel == "ntfy":
            if config.ntfy_topic:
                from src.delivery.ntfy import NtfyDeliverer

                NtfyDeliverer(config.ntfy_topic, config.ntfy_base_url, config.ntfy_priority).send(message)
                logger.info("Error alert sent via ntfy")
            else:
                logger.warning("ALERT_CHANNEL=ntfy but ntfy not configured; no alert sent")
        elif channel == "slack":
            if config.slack_webhook_url:
                from src.delivery.slack import SlackDeliverer

                SlackDeliverer(config.slack_webhook_url).send(message)
                logger.info("Error alert sent via slack")
            else:
                logger.warning("ALERT_CHANNEL=slack but slack not configured; no alert sent")
        elif channel == "sms":
            if all([config.twilio_account_sid, config.twilio_auth_token,
                    config.twilio_from_number, config.twilio_to_number]):
                from src.delivery.sms import SMSDeliverer

                SMSDeliverer(
                    config.twilio_account_sid,   # type: ignore[arg-type]
                    config.twilio_auth_token,    # type: ignore[arg-type]
                    config.twilio_from_number,   # type: ignore[arg-type]
                    config.twilio_to_number,     # type: ignore[arg-type]
                ).send(message)
                logger.info("Error alert sent via sms")
            else:
                logger.warning("ALERT_CHANNEL=sms but SMS not fully configured; no alert sent")
        else:
            logger.warning("Unknown ALERT_CHANNEL '%s'; no alert sent", channel)
    except Exception:
        logger.exception("Failed to send error alert via channel '%s'", channel)
