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

    if config.email_to and config.email_from and (config.sendgrid_api_key or config.smtp_host):
        from src.delivery.email import EmailDeliverer
        deliverers.append(EmailDeliverer(
            to=config.email_to,
            from_=config.email_from,
            sendgrid_api_key=config.sendgrid_api_key,
            smtp_host=config.smtp_host,
            smtp_port=config.smtp_port,
            smtp_user=config.smtp_user,
            smtp_pass=config.smtp_pass,
        ))

    return deliverers
