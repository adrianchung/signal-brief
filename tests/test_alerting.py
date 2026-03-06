from unittest.mock import MagicMock, patch

from src.alerting import send_alert, _pick_deliverer


def make_config(alert_channel=None, has_slack=True, has_ntfy=False, has_sms=False):
    cfg = MagicMock()
    cfg.alert_channel = alert_channel
    cfg.slack_webhook_url = "https://hooks.slack.com/x" if has_slack else None
    cfg.ntfy_topic = "mytopic" if has_ntfy else None
    cfg.ntfy_base_url = "https://ntfy.sh"
    cfg.ntfy_priority = 3
    cfg.twilio_account_sid = "sid" if has_sms else None
    cfg.twilio_auth_token = "token" if has_sms else None
    cfg.twilio_from_number = "+1000" if has_sms else None
    cfg.twilio_to_number = "+2000" if has_sms else None
    return cfg


class TestSendAlert:
    def test_sends_message_with_step_and_error(self):
        config = make_config()
        mock_deliverer = MagicMock()

        with patch("src.alerting._pick_deliverer", return_value=mock_deliverer):
            send_alert(config, "fetch", ValueError("timeout"))

        mock_deliverer.send.assert_called_once()
        sent_msg = mock_deliverer.send.call_args[0][0]
        assert "fetch" in sent_msg
        assert "ValueError" in sent_msg
        assert "timeout" in sent_msg

    def test_message_includes_timestamp(self):
        config = make_config()
        mock_deliverer = MagicMock()

        with patch("src.alerting._pick_deliverer", return_value=mock_deliverer):
            send_alert(config, "analyze", RuntimeError("boom"))

        sent_msg = mock_deliverer.send.call_args[0][0]
        assert "UTC" in sent_msg

    def test_message_includes_signal_brief_prefix(self):
        config = make_config()
        mock_deliverer = MagicMock()

        with patch("src.alerting._pick_deliverer", return_value=mock_deliverer):
            send_alert(config, "delivery", Exception("fail"))

        sent_msg = mock_deliverer.send.call_args[0][0]
        assert "signal-brief" in sent_msg

    def test_no_deliverer_does_not_raise(self):
        config = make_config(has_slack=False)

        with patch("src.alerting._pick_deliverer", return_value=None):
            send_alert(config, "fetch", ValueError("x"))  # should not raise

    def test_deliverer_send_failure_does_not_raise(self):
        config = make_config()
        mock_deliverer = MagicMock()
        mock_deliverer.send.side_effect = Exception("send blew up")

        with patch("src.alerting._pick_deliverer", return_value=mock_deliverer):
            send_alert(config, "fetch", ValueError("x"))  # should not raise


class TestPickDeliverer:
    def test_returns_none_when_no_channels_configured(self):
        config = make_config(has_slack=False)

        with patch("src.alerting.get_deliverers", return_value=[]):
            result = _pick_deliverer(config)

        assert result is None

    def test_returns_first_available_when_no_preference(self):
        config = make_config(alert_channel=None)
        slack = MagicMock(__class__=type("SlackDeliverer", (), {}))
        ntfy = MagicMock(__class__=type("NtfyDeliverer", (), {}))

        with patch("src.alerting.get_deliverers", return_value=[slack, ntfy]):
            result = _pick_deliverer(config)

        assert result is slack

    def test_preferred_channel_selected(self):
        config = make_config(alert_channel="ntfy", has_slack=True, has_ntfy=True)

        class SlackDeliverer:
            pass

        class NtfyDeliverer:
            pass

        slack = SlackDeliverer()
        ntfy = NtfyDeliverer()

        with patch("src.alerting.get_deliverers", return_value=[slack, ntfy]):
            result = _pick_deliverer(config)

        assert result is ntfy

    def test_falls_back_to_first_when_preferred_unavailable(self):
        config = make_config(alert_channel="sms", has_slack=True)

        class SlackDeliverer:
            pass

        slack = SlackDeliverer()

        with patch("src.alerting.get_deliverers", return_value=[slack]):
            result = _pick_deliverer(config)

        assert result is slack
