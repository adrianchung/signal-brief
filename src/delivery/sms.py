import re

from twilio.rest import Client

SMS_LIMIT = 1600
PREFIX = "Signal Brief\n"

_MD_HEADING = re.compile(r"^#{1,3}\s+", re.MULTILINE)
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
_MD_ITALIC_SCORE = re.compile(r"_\((.+?)\)_")
_MD_ITALIC = re.compile(r"\*(.+?)\*")


def _to_sms(text: str) -> str:
    """Strip markdown to plain text suitable for SMS."""
    text = _MD_HEADING.sub("", text)
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_LINK.sub(r"\1 \2", text)        # [label](url) → label url
    text = _MD_ITALIC_SCORE.sub(r"(\1)", text)  # _(N pts)_ → (N pts)
    text = _MD_ITALIC.sub(r"\1", text)
    return text.strip()


class SMSDeliverer:
    def __init__(self, account_sid: str, auth_token: str, from_number: str, to_number: str) -> None:
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
        self.to_number = to_number

    def send(self, brief: str) -> None:
        body = PREFIX + _to_sms(brief)
        if len(body) > SMS_LIMIT:
            body = body[: SMS_LIMIT - 3] + "..."
        self.client.messages.create(
            body=body,
            from_=self.from_number,
            to=self.to_number,
        )
