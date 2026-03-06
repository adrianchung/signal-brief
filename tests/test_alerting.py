from unittest.mock import MagicMock, patch

import pytest

from src.alerting import _format_alert, _try_channel, send_error_alert


# ---------------------------------------------------------------------------
# _format_alert
# ---------------------------------------------------------------------------

class TestFormatAlert:
    def test_contains_timestamp(self):
        msg = _format_alert("fetch", ValueError("boom"))
        assert "UTC" in msg

    def test_contains_step(self):
        msg = _format_alert("fetch", ValueError("boom"))
        assert "Step: fetch" in msg

    def test_contains_error_type_and_message(self):
        msg = _format_alert("analyze", RuntimeError("api error"))
        assert "RuntimeError" in msg
        assert "api error" in msg

    def test_contains_header(self):
        msg = _format_alert("fetch", ValueError("x"))
        assert "[SIGNAL BRIEF ERROR]" in msg


# ---------------------------------------------------------------------------
# _try_channel
# ---------------------------------------------------------------------------

def _make_config(**kwargs):
    cfg = MagicMock()
    cfg.ntfy_topic = kwargs.get("ntfy_topic", None)
    cfg.ntfy_base_url = kwargs.get("ntfy_base_url", "https://ntfy.sh")
    cfg.ntfy_priority = kwargs.get("ntfy_priority", 3)
    cfg.slack_webhook_url = kwargs.get("slack_webhook_url", None)
    cfg.twilio_account_sid = kwargs.get("twilio_account_sid", None)
    cfg.twilio_auth_token = kwargs.get("twilio_auth_token", None)
    cfg.twilio_from_number = kwargs.get("twilio_from_number", None)
    cfg.twilio_to_number = kwargs.get("twilio_to_number", None)
    cfg.alert_channel = kwargs.get("alert_channel", None)
    return cfg


class TestTryChannel:
    def test_ntfy_sends_when_configured(self):
        config = _make_config(ntfy_topic="alerts")
        with patch("src.delivery.ntfy.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            _try_channel(config, "ntfy", "test alert")
        mock_post.assert_called_once()

    def test_ntfy_skips_when_not_configured(self):
        config = _make_config()  # ntfy_topic=None
        with patch("src.delivery.ntfy.httpx.post") as mock_post:
            _try_channel(config, "ntfy", "test alert")
        mock_post.assert_not_called()

    def test_slack_sends_when_configured(self):
        config = _make_config(slack_webhook_url="https://hooks.slack.com/x")
        with patch("src.delivery.slack.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            _try_channel(config, "slack", "test alert")
        mock_post.assert_called_once()

    def test_slack_skips_when_not_configured(self):
        config = _make_config()
        with patch("src.delivery.slack.httpx.post") as mock_post:
            _try_channel(config, "slack", "test alert")
        mock_post.assert_not_called()

    def test_sms_sends_when_configured(self):
        config = _make_config(
            twilio_account_sid="sid",
            twilio_auth_token="token",
            twilio_from_number="+1000",
            twilio_to_number="+2000",
        )
        with patch("src.delivery.sms.Client") as mock_client:
            _try_channel(config, "sms", "test alert")
        mock_client.return_value.messages.create.assert_called_once()

    def test_sms_skips_when_partial_config(self):
        config = _make_config(twilio_account_sid="sid")  # missing other fields
        with patch("src.delivery.sms.Client") as mock_client:
            _try_channel(config, "sms", "test alert")
        mock_client.return_value.messages.create.assert_not_called()

    def test_unknown_channel_does_not_raise(self):
        config = _make_config()
        _try_channel(config, "carrier_pigeon", "test alert")  # should just log and return

    def test_channel_name_is_case_insensitive(self):
        config = _make_config(ntfy_topic="alerts")
        with patch("src.delivery.ntfy.httpx.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            _try_channel(config, "NTFY", "test alert")
        mock_post.assert_called_once()

    def test_delivery_exception_does_not_propagate(self):
        config = _make_config(ntfy_topic="alerts")
        with patch("src.delivery.ntfy.httpx.post", side_effect=Exception("network error")):
            _try_channel(config, "ntfy", "test alert")  # must not raise


# ---------------------------------------------------------------------------
# send_error_alert
# ---------------------------------------------------------------------------

class TestSendErrorAlert:
    def test_uses_alert_channel_when_configured(self):
        config = _make_config(ntfy_topic="alerts", alert_channel="ntfy")
        with patch("src.alerting._try_channel") as mock_try:
            send_error_alert(config, "fetch", ValueError("boom"))
        mock_try.assert_called_once_with(config, "ntfy", mock_try.call_args[0][2])

    def test_falls_back_to_deliverers_when_no_alert_channel(self):
        config = _make_config()
        config.alert_channel = None
        mock_deliverer = MagicMock()

        with patch("src.alerting.get_deliverers", return_value=[mock_deliverer]):
            send_error_alert(config, "fetch", ValueError("boom"))

        mock_deliverer.send.assert_called_once()

    def test_stops_after_first_successful_deliverer(self):
        config = _make_config()
        config.alert_channel = None
        d1 = MagicMock()
        d2 = MagicMock()

        with patch("src.alerting.get_deliverers", return_value=[d1, d2]):
            send_error_alert(config, "fetch", ValueError("x"))

        d1.send.assert_called_once()
        d2.send.assert_not_called()

    def test_tries_next_deliverer_on_failure(self):
        config = _make_config()
        config.alert_channel = None
        d1 = MagicMock()
        d1.send.side_effect = Exception("fail")
        d2 = MagicMock()

        with patch("src.alerting.get_deliverers", return_value=[d1, d2]):
            send_error_alert(config, "fetch", ValueError("x"))

        d2.send.assert_called_once()

    def test_no_channels_does_not_raise(self):
        config = _make_config()
        config.alert_channel = None

        with patch("src.alerting.get_deliverers", return_value=[]):
            send_error_alert(config, "fetch", ValueError("x"))  # must not raise

    def test_alert_message_contains_step_and_error(self):
        config = _make_config()
        config.alert_channel = None
        mock_deliverer = MagicMock()

        with patch("src.alerting.get_deliverers", return_value=[mock_deliverer]):
            send_error_alert(config, "analyze", RuntimeError("api timeout"))

        sent_message = mock_deliverer.send.call_args[0][0]
        assert "analyze" in sent_message
        assert "RuntimeError" in sent_message
        assert "api timeout" in sent_message
