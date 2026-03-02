import re
import httpx


def _to_mrkdwn(text: str) -> str:
    """Convert standard markdown to Slack mrkdwn format."""
    # ## Heading → *Heading*
    text = re.sub(r"^#{1,3}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # **bold** → *bold*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # [label](url) → <url|label>
    text = re.sub(r"\[([^\]]+)\]\((https?://[^\)]+)\)", r"<\2|\1>", text)
    return text


class SlackDeliverer:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, brief: str) -> None:
        payload = {"text": f"*HN Signal Brief*\n{_to_mrkdwn(brief)}"}
        response = httpx.post(self.webhook_url, json=payload, timeout=10)
        response.raise_for_status()
