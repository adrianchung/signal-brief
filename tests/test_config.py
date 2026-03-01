import pytest
from pydantic import ValidationError

from src.config import Settings


def make_settings(**kwargs):
    """Helper: build Settings with a valid LLM key by default, ignoring any .env file."""
    defaults = {"gemini_api_key": "test-gemini-key"}
    defaults.update(kwargs)
    return Settings(_env_file=None, **defaults)


class TestKeywordList:
    def test_default_keywords_parsed(self):
        s = make_settings()
        assert isinstance(s.keyword_list, list)
        assert len(s.keyword_list) > 0

    def test_custom_keywords(self):
        s = make_settings(keywords="python,rust,go")
        assert s.keyword_list == ["python", "rust", "go"]

    def test_whitespace_stripped(self):
        s = make_settings(keywords=" ai , ml , llm ")
        assert s.keyword_list == ["ai", "ml", "llm"]

    def test_empty_entries_ignored(self):
        s = make_settings(keywords="ai,,ml,")
        assert s.keyword_list == ["ai", "ml"]


class TestScheduleTimeList:
    def test_default_times(self):
        s = make_settings()
        assert s.schedule_time_list == ["08:00", "17:00"]

    def test_custom_times(self):
        s = make_settings(schedule_times="09:00,18:30")
        assert s.schedule_time_list == ["09:00", "18:30"]

    def test_single_time(self):
        s = make_settings(schedule_times="07:00")
        assert s.schedule_time_list == ["07:00"]


class TestEnabledDeliverers:
    def test_none_configured(self):
        s = make_settings()
        assert s.enabled_deliverers == []

    def test_slack_only(self):
        s = make_settings(slack_webhook_url="https://hooks.slack.com/xxx")
        assert s.enabled_deliverers == ["slack"]

    def test_ntfy_only(self):
        s = make_settings(ntfy_topic="my-topic")
        assert s.enabled_deliverers == ["ntfy"]

    def test_sms_requires_all_four_fields(self):
        # Missing twilio_to_number — should not include sms
        s = make_settings(
            twilio_account_sid="sid",
            twilio_auth_token="token",
            twilio_from_number="+15550000001",
        )
        assert "sms" not in s.enabled_deliverers

    def test_sms_all_fields(self):
        s = make_settings(
            twilio_account_sid="sid",
            twilio_auth_token="token",
            twilio_from_number="+15550000001",
            twilio_to_number="+15550000002",
        )
        assert "sms" in s.enabled_deliverers

    def test_all_channels(self):
        s = make_settings(
            slack_webhook_url="https://hooks.slack.com/xxx",
            ntfy_topic="my-topic",
            twilio_account_sid="sid",
            twilio_auth_token="token",
            twilio_from_number="+15550000001",
            twilio_to_number="+15550000002",
        )
        assert s.enabled_deliverers == ["slack", "ntfy", "sms"]


class TestLLMKeyValidator:
    def test_no_keys_raises(self):
        with pytest.raises(ValidationError, match="At least one"):
            Settings(_env_file=None, gemini_api_key=None, anthropic_api_key=None)

    def test_gemini_key_only_ok(self):
        s = Settings(_env_file=None, gemini_api_key="key", anthropic_api_key=None)
        assert s.gemini_api_key == "key"

    def test_anthropic_key_only_ok(self):
        s = Settings(_env_file=None, gemini_api_key=None, anthropic_api_key="key")
        assert s.anthropic_api_key == "key"

    def test_both_keys_ok(self):
        s = Settings(_env_file=None, gemini_api_key="g-key", anthropic_api_key="a-key")
        assert s.gemini_api_key == "g-key"
        assert s.anthropic_api_key == "a-key"
