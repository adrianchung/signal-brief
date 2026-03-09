from unittest.mock import MagicMock, patch

import pytest

from src.delivery import get_deliverers
from src.delivery.slack import SlackDeliverer, _to_mrkdwn
from src.delivery.ntfy import NtfyDeliverer, _extract_story_actions
from src.delivery.sms import SMSDeliverer, _to_sms
from src.delivery.email import EmailDeliverer, _make_subject, _to_html, _to_plain


# ---------------------------------------------------------------------------
# get_deliverers
# ---------------------------------------------------------------------------

def make_config(**kwargs):
    cfg = MagicMock()
    cfg.slack_webhook_url = kwargs.get("slack_webhook_url", None)
    cfg.ntfy_topic = kwargs.get("ntfy_topic", None)
    cfg.ntfy_base_url = kwargs.get("ntfy_base_url", "https://ntfy.sh")
    cfg.ntfy_priority = kwargs.get("ntfy_priority", 3)
    cfg.twilio_account_sid = kwargs.get("twilio_account_sid", None)
    cfg.twilio_auth_token = kwargs.get("twilio_auth_token", None)
    cfg.twilio_from_number = kwargs.get("twilio_from_number", None)
    cfg.twilio_to_number = kwargs.get("twilio_to_number", None)
    cfg.email_to = kwargs.get("email_to", None)
    cfg.email_from = kwargs.get("email_from", None)
    cfg.sendgrid_api_key = kwargs.get("sendgrid_api_key", None)
    cfg.smtp_host = kwargs.get("smtp_host", None)
    cfg.smtp_port = kwargs.get("smtp_port", 587)
    cfg.smtp_user = kwargs.get("smtp_user", None)
    cfg.smtp_pass = kwargs.get("smtp_pass", None)
    return cfg


class TestGetDeliverers:
    def test_no_config_returns_empty(self):
        assert get_deliverers(make_config()) == []

    def test_slack_added_when_webhook_set(self):
        deliverers = get_deliverers(make_config(slack_webhook_url="https://hooks.slack.com/x"))
        assert len(deliverers) == 1
        assert isinstance(deliverers[0], SlackDeliverer)

    def test_ntfy_added_when_topic_set(self):
        deliverers = get_deliverers(make_config(ntfy_topic="my-topic"))
        assert len(deliverers) == 1
        assert isinstance(deliverers[0], NtfyDeliverer)

    def test_sms_not_added_when_partial_twilio_config(self):
        deliverers = get_deliverers(make_config(
            twilio_account_sid="sid",
            twilio_auth_token="token",
            twilio_from_number="+1555000001",
            # missing twilio_to_number
        ))
        assert not any(isinstance(d, SMSDeliverer) for d in deliverers)

    def test_sms_added_when_all_twilio_fields_set(self):
        with patch("src.delivery.sms.Client"):
            deliverers = get_deliverers(make_config(
                twilio_account_sid="sid",
                twilio_auth_token="token",
                twilio_from_number="+1555000001",
                twilio_to_number="+1555000002",
            ))
        assert any(isinstance(d, SMSDeliverer) for d in deliverers)

    def test_all_channels_configured(self):
        with patch("src.delivery.sms.Client"):
            deliverers = get_deliverers(make_config(
                slack_webhook_url="https://hooks.slack.com/x",
                ntfy_topic="my-topic",
                twilio_account_sid="sid",
                twilio_auth_token="token",
                twilio_from_number="+1555000001",
                twilio_to_number="+1555000002",
            ))
        assert len(deliverers) == 3


# ---------------------------------------------------------------------------
# SlackDeliverer
# ---------------------------------------------------------------------------

class TestToMrkdwn:
    def test_heading_converted_to_bold(self):
        assert _to_mrkdwn("## Theme") == "*Theme*"

    def test_h3_converted_to_bold(self):
        assert _to_mrkdwn("### Bottom Line") == "*Bottom Line*"

    def test_bold_converted(self):
        assert _to_mrkdwn("**important**") == "*important*"

    def test_link_converted(self):
        assert _to_mrkdwn("[Story](https://example.com)") == "<https://example.com|Story>"

    def test_plain_text_unchanged(self):
        assert _to_mrkdwn("plain text") == "plain text"

    def test_full_brief_conversion(self):
        brief = "## Theme\nAI is rising.\n\n- **[Cool Story](https://example.com)** — it matters."
        result = _to_mrkdwn(brief)
        assert "*Theme*" in result
        assert "<https://example.com|Cool Story>" in result
        assert "**" not in result
        assert "##" not in result


class TestSlackDeliverer:
    def test_posts_to_webhook_url(self):
        with patch("src.delivery.slack.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            SlackDeliverer("https://hooks.slack.com/x").send("hello")
        mock_post.assert_called_once()
        assert mock_post.call_args[0][0] == "https://hooks.slack.com/x"

    def test_brief_converted_to_mrkdwn_in_payload(self):
        with patch("src.delivery.slack.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            SlackDeliverer("https://hooks.slack.com/x").send("## Theme\n**bold** and [link](https://example.com)")
        payload = mock_post.call_args[1]["json"]
        assert "*Theme*" in payload["text"]
        assert "*bold*" in payload["text"]
        assert "<https://example.com|link>" in payload["text"]


# ---------------------------------------------------------------------------
# NtfyDeliverer
# ---------------------------------------------------------------------------

class TestNtfyDeliverer:
    def test_posts_to_correct_url(self):
        with patch("src.delivery.ntfy.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            NtfyDeliverer("my-topic", "https://ntfy.sh").send("hello")
        assert mock_post.call_args[0][0] == "https://ntfy.sh/my-topic"

    def test_trailing_slash_stripped_from_base_url(self):
        with patch("src.delivery.ntfy.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            NtfyDeliverer("topic", "https://ntfy.sh/").send("hello")
        assert mock_post.call_args[0][0] == "https://ntfy.sh/topic"

    def test_brief_sent_as_content(self):
        with patch("src.delivery.ntfy.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            NtfyDeliverer("topic", "https://ntfy.sh").send("my brief")
        assert mock_post.call_args[1]["content"] == b"my brief"

    def test_priority_header_sent(self):
        with patch("src.delivery.ntfy.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            NtfyDeliverer("topic", "https://ntfy.sh", priority=4).send("hello")
        headers = mock_post.call_args[1]["headers"]
        assert headers["Priority"] == "4"

    def test_markdown_header_sent(self):
        with patch("src.delivery.ntfy.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            NtfyDeliverer("topic", "https://ntfy.sh").send("hello")
        headers = mock_post.call_args[1]["headers"]
        assert headers.get("Markdown") == "yes"

    def test_action_buttons_added_for_markdown_links(self):
        brief = "## Brief\n- [Story One](https://example.com/a)\n- [Story Two](https://hn.com/b)"
        with patch("src.delivery.ntfy.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            NtfyDeliverer("topic", "https://ntfy.sh").send(brief)
        headers = mock_post.call_args[1]["headers"]
        assert "Actions" in headers
        assert "view, Story One, https://example.com/a" in headers["Actions"]
        assert "view, Story Two, https://hn.com/b" in headers["Actions"]

    def test_no_action_header_when_no_links(self):
        with patch("src.delivery.ntfy.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            NtfyDeliverer("topic", "https://ntfy.sh").send("plain text, no links")
        headers = mock_post.call_args[1]["headers"]
        assert "Actions" not in headers

    def test_actions_capped_at_three(self):
        brief = "\n".join(
            f"[Story {i}](https://example.com/{i})" for i in range(10)
        )
        with patch("src.delivery.ntfy.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            NtfyDeliverer("topic", "https://ntfy.sh").send(brief)
        headers = mock_post.call_args[1]["headers"]
        assert headers["Actions"].count("view") == 3


# ---------------------------------------------------------------------------
# _extract_story_actions (format contract tests — no mocking)
# ---------------------------------------------------------------------------

class TestExtractStoryActions:
    def test_single_link_correct_format(self):
        result = _extract_story_actions("[Story One](https://example.com)")
        assert result == "view, Story One, https://example.com"

    def test_multiple_links_semicolon_separated(self):
        brief = "[A](https://a.com)\n[B](https://b.com)"
        result = _extract_story_actions(brief)
        assert result == "view, A, https://a.com; view, B, https://b.com"

    def test_capped_at_max_actions(self):
        brief = "\n".join(f"[S{i}](https://example.com/{i})" for i in range(5))
        result = _extract_story_actions(brief, max_actions=2)
        assert result.count("view,") == 2

    def test_deduplicates_same_url(self):
        brief = "[A](https://example.com)\n[B](https://example.com)"
        result = _extract_story_actions(brief)
        assert result.count("view,") == 1

    def test_no_links_returns_empty_string(self):
        assert _extract_story_actions("plain text no links") == ""

    def test_label_commas_stripped(self):
        result = _extract_story_actions("[Story, With, Commas](https://example.com)")
        assert result == "view, Story With Commas, https://example.com"

    def test_label_semicolons_stripped(self):
        result = _extract_story_actions("[Story; Title](https://example.com)")
        label_part = result.split(", https://")[0].replace("view, ", "")
        assert ";" not in label_part


# ---------------------------------------------------------------------------
# SMSDeliverer
# ---------------------------------------------------------------------------

class TestToSms:
    def test_markdown_link_becomes_label_then_url(self):
        assert _to_sms("[Story](https://example.com)") == "Story https://example.com"

    def test_heading_stripped(self):
        assert _to_sms("## Theme") == "Theme"

    def test_bold_stripped(self):
        assert _to_sms("**important**") == "important"

    def test_italic_score_preserved_as_parens(self):
        assert _to_sms("_(123 pts)_") == "(123 pts)"

    def test_plain_text_unchanged(self):
        assert _to_sms("plain text") == "plain text"

    def test_full_brief_plain(self):
        brief = "## Theme\nAI is rising.\n\n- **[Cool Story](https://example.com)** — it matters. _(50 pts)_"
        result = _to_sms(brief)
        assert "##" not in result
        assert "**" not in result
        assert "https://example.com" in result
        assert "Cool Story" in result
        assert "(50 pts)" in result


class TestSMSDeliverer:
    def _make_deliverer(self):
        with patch("src.delivery.sms.Client") as mock_client_cls:
            d = SMSDeliverer("sid", "token", "+1000", "+2000")
            d._mock_client = mock_client_cls.return_value
        return d

    def test_send_calls_messages_create(self):
        with patch("src.delivery.sms.Client") as mock_client_cls:
            d = SMSDeliverer("sid", "token", "+1000", "+2000")
            d.send("hello")
            mock_client_cls.return_value.messages.create.assert_called_once()

    def test_brief_truncated_at_limit(self):
        with patch("src.delivery.sms.Client") as mock_client_cls:
            d = SMSDeliverer("sid", "token", "+1000", "+2000")
            long_brief = "x" * 2000
            d.send(long_brief)
            call_kwargs = mock_client_cls.return_value.messages.create.call_args[1]
            assert len(call_kwargs["body"]) <= 1600

    def test_short_brief_not_truncated(self):
        with patch("src.delivery.sms.Client") as mock_client_cls:
            d = SMSDeliverer("sid", "token", "+1000", "+2000")
            d.send("short")
            call_kwargs = mock_client_cls.return_value.messages.create.call_args[1]
            assert "short" in call_kwargs["body"]


# ---------------------------------------------------------------------------
# EmailDeliverer helpers
# ---------------------------------------------------------------------------

BRIEF = """\
## Theme
AI agents are eating the world.

## Top Stories
- **[Some Article](https://example.com/article)** — it matters. _(42 pts)_

## Bottom Line
Everything is fine.
"""


class TestEmailHelpers:
    def test_make_subject_extracts_theme(self):
        assert _make_subject(BRIEF) == "Signal Brief: AI agents are eating the world."

    def test_make_subject_fallback(self):
        assert _make_subject("no theme here") == "Signal Brief"

    def test_to_html_contains_link(self):
        html = _to_html(BRIEF)
        assert '<a href="https://example.com/article">' in html

    def test_to_html_contains_heading(self):
        html = _to_html(BRIEF)
        assert "<h2>" in html

    def test_to_html_wraps_in_template(self):
        html = _to_html(BRIEF)
        assert "<!DOCTYPE html>" in html
        assert "Signal Brief" in html

    def test_to_plain_strips_headings(self):
        plain = _to_plain(BRIEF)
        assert "##" not in plain

    def test_to_plain_exposes_url(self):
        plain = _to_plain(BRIEF)
        assert "https://example.com/article" in plain

    def test_to_plain_strips_bold(self):
        plain = _to_plain(BRIEF)
        assert "**" not in plain


class TestEmailDelivererSendGrid:
    def _deliverer(self):
        return EmailDeliverer(
            to="to@example.com",
            from_="from@example.com",
            sendgrid_api_key="SG.fake",
        )

    def test_posts_to_sendgrid(self):
        with patch("src.delivery.email.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            self._deliverer().send(BRIEF)
        assert mock_post.call_args[0][0] == "https://api.sendgrid.com/v3/mail/send"

    def test_authorization_header_sent(self):
        with patch("src.delivery.email.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            self._deliverer().send(BRIEF)
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer SG.fake"

    def test_payload_has_html_and_plain(self):
        with patch("src.delivery.email.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            self._deliverer().send(BRIEF)
        payload = mock_post.call_args[1]["json"]
        types = [c["type"] for c in payload["content"]]
        assert "text/html" in types
        assert "text/plain" in types

    def test_subject_uses_theme(self):
        with patch("src.delivery.email.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            self._deliverer().send(BRIEF)
        payload = mock_post.call_args[1]["json"]
        assert "AI agents" in payload["subject"]


class TestEmailDelivererSMTP:
    def test_smtp_send_called(self):
        d = EmailDeliverer(
            to="to@example.com",
            from_="from@example.com",
            smtp_host="smtp.example.com",
            smtp_user="user",
            smtp_pass="pass",
        )
        with patch("src.delivery.email.smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_smtp
            d.send(BRIEF)
        mock_smtp.send_message.assert_called_once()

    def test_smtp_login_called_when_credentials_set(self):
        d = EmailDeliverer(
            to="to@example.com",
            from_="from@example.com",
            smtp_host="smtp.example.com",
            smtp_user="user",
            smtp_pass="secret",
        )
        with patch("src.delivery.email.smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_smtp
            d.send(BRIEF)
        mock_smtp.login.assert_called_once_with("user", "secret")

    def test_smtp_login_skipped_when_no_credentials(self):
        d = EmailDeliverer(
            to="to@example.com",
            from_="from@example.com",
            smtp_host="smtp.example.com",
        )
        with patch("src.delivery.email.smtplib.SMTP") as mock_smtp_cls:
            mock_smtp = MagicMock()
            mock_smtp_cls.return_value.__enter__.return_value = mock_smtp
            d.send(BRIEF)
        mock_smtp.login.assert_not_called()


class TestGetDeliverersEmail:
    def test_email_added_with_sendgrid(self):
        cfg = make_config(
            slack_webhook_url=None,
            ntfy_topic=None,
        )
        cfg.email_to = "to@example.com"
        cfg.email_from = "from@example.com"
        cfg.sendgrid_api_key = "SG.fake"
        cfg.smtp_host = None
        deliverers = get_deliverers(cfg)
        assert any(isinstance(d, EmailDeliverer) for d in deliverers)

    def test_email_added_with_smtp(self):
        cfg = make_config()
        cfg.email_to = "to@example.com"
        cfg.email_from = "from@example.com"
        cfg.sendgrid_api_key = None
        cfg.smtp_host = "smtp.example.com"
        cfg.smtp_port = 587
        cfg.smtp_user = None
        cfg.smtp_pass = None
        deliverers = get_deliverers(cfg)
        assert any(isinstance(d, EmailDeliverer) for d in deliverers)

    def test_email_not_added_when_no_transport(self):
        cfg = make_config()
        cfg.email_to = "to@example.com"
        cfg.email_from = "from@example.com"
        cfg.sendgrid_api_key = None
        cfg.smtp_host = None
        deliverers = get_deliverers(cfg)
        assert not any(isinstance(d, EmailDeliverer) for d in deliverers)

    def test_email_not_added_when_no_recipient(self):
        cfg = make_config()
        cfg.email_to = None
        cfg.email_from = "from@example.com"
        cfg.sendgrid_api_key = "SG.fake"
        cfg.smtp_host = None
        deliverers = get_deliverers(cfg)
        assert not any(isinstance(d, EmailDeliverer) for d in deliverers)
