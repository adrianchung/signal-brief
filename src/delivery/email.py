"""Email delivery channel.

Supports SendGrid (REST API) and SMTP. Activate by setting:
  EMAIL_TO, EMAIL_FROM, and either SENDGRID_API_KEY or SMTP_HOST.

Markdown is converted to an HTML body; a plain-text fallback is always
included for clients that don't render HTML.
"""
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
import markdown as _md

_SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;margin:0 auto;padding:24px 16px;color:#111;line-height:1.65;">
<p style="font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#888;margin:0 0 20px;padding-bottom:8px;border-bottom:2px solid #111;">Signal Brief</p>
{body}
</body>
</html>"""

_SUBJECT_RE = re.compile(r"##\s*Theme\s*\n(.+)")
_HEADING_RE = re.compile(r"^#{1,3}\s+", re.MULTILINE)
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")
_ITALIC_SCORE_RE = re.compile(r"_\((.+?)\)_")
_ITALIC_RE = re.compile(r"\*(.+?)\*")


def _make_subject(brief: str) -> str:
    match = _SUBJECT_RE.search(brief)
    if match:
        return f"Signal Brief: {match.group(1).strip()}"
    return "Signal Brief"


def _to_html(brief: str) -> str:
    body = _md.markdown(brief)
    return _HTML_TEMPLATE.format(body=body)


def _to_plain(brief: str) -> str:
    text = _HEADING_RE.sub("", brief)
    text = _BOLD_RE.sub(r"\1", text)
    text = _LINK_RE.sub(r"\1: \2", text)
    text = _ITALIC_SCORE_RE.sub(r"(\1)", text)
    text = _ITALIC_RE.sub(r"\1", text)
    return text.strip()


class EmailDeliverer:
    def __init__(
        self,
        to: str,
        from_: str,
        sendgrid_api_key: str | None = None,
        smtp_host: str | None = None,
        smtp_port: int = 587,
        smtp_user: str | None = None,
        smtp_pass: str | None = None,
    ) -> None:
        self._to = to
        self._from = from_
        self._sendgrid_api_key = sendgrid_api_key
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_pass = smtp_pass

    def send(self, brief: str) -> None:
        subject = _make_subject(brief)
        html = _to_html(brief)
        plain = _to_plain(brief)
        if self._sendgrid_api_key:
            self._send_sendgrid(subject, html, plain)
        else:
            self._send_smtp(subject, html, plain)

    def _send_sendgrid(self, subject: str, html: str, plain: str) -> None:
        resp = httpx.post(
            _SENDGRID_URL,
            json={
                "personalizations": [{"to": [{"email": self._to}]}],
                "from": {"email": self._from},
                "subject": subject,
                "content": [
                    {"type": "text/plain", "value": plain},
                    {"type": "text/html", "value": html},
                ],
            },
            headers={"Authorization": f"Bearer {self._sendgrid_api_key}"},
            timeout=15,
        )
        resp.raise_for_status()

    def _send_smtp(self, subject: str, html: str, plain: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = self._to
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(self._smtp_host, self._smtp_port) as smtp:  # type: ignore[arg-type]
            smtp.ehlo()
            smtp.starttls()
            if self._smtp_user and self._smtp_pass:
                smtp.login(self._smtp_user, self._smtp_pass)
            smtp.send_message(msg)
