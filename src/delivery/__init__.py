from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.config import Settings


@runtime_checkable
class Deliverer(Protocol):
    def send(self, brief: str) -> None: ...


def get_deliverers(config: "Settings") -> list[Deliverer]:
    deliverers: list[Deliverer] = []

    if config.slack_webhook_url:
        from src.delivery.slack import SlackDeliverer
        deliverers.append(SlackDeliverer(config.slack_webhook_url))

    if config.ntfy_topic:
        from src.delivery.ntfy import NtfyDeliverer
        deliverers.append(NtfyDeliverer(config.ntfy_topic, config.ntfy_base_url, config.ntfy_priority))

    if all([config.twilio_account_sid, config.twilio_auth_token, config.twilio_from_number, config.twilio_to_number]):
        from src.delivery.sms import SMSDeliverer
        deliverers.append(SMSDeliverer(
            config.twilio_account_sid,  # type: ignore[arg-type]
            config.twilio_auth_token,   # type: ignore[arg-type]
            config.twilio_from_number,  # type: ignore[arg-type]
            config.twilio_to_number,    # type: ignore[arg-type]
        ))

    return deliverers
