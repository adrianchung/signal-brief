"""Tests for src/profiles.py — DigestProfile and discover_profiles."""

import pytest

from src.profiles import DigestProfile, discover_profiles, get_profile


def make_config(keywords="ai,ml", schedule_times="08:00,17:00"):
    from unittest.mock import MagicMock
    cfg = MagicMock()
    cfg.keywords = keywords
    cfg.keyword_list = [k.strip() for k in keywords.split(",")]
    cfg.schedule_time_list = [t.strip() for t in schedule_times.split(",")]
    return cfg


class TestDiscoverProfiles:
    def test_fallback_when_no_named_profiles(self, monkeypatch):
        monkeypatch.delenv("SCHEDULE_MORNING", raising=False)
        monkeypatch.delenv("SCHEDULE_EVENING", raising=False)
        config = make_config(schedule_times="08:00,17:00")
        profiles = discover_profiles(config)
        assert len(profiles) == 2
        assert all(p.name == "default" for p in profiles)
        assert profiles[0].time == "08:00"
        assert profiles[1].time == "17:00"

    def test_fallback_uses_config_keywords(self, monkeypatch):
        monkeypatch.delenv("SCHEDULE_MORNING", raising=False)
        config = make_config(keywords="python,rust")
        profiles = discover_profiles(config)
        assert profiles[0].keywords == ["python", "rust"]

    def test_discovers_named_profile(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_MORNING", "08:00")
        monkeypatch.delenv("SCHEDULE_MORNING_KEYWORDS", raising=False)
        monkeypatch.delenv("SCHEDULE_MORNING_STYLE", raising=False)
        config = make_config()
        profiles = discover_profiles(config)
        names = [p.name for p in profiles]
        assert "morning" in names

    def test_named_profile_uses_custom_keywords(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_MORNING", "08:00")
        monkeypatch.setenv("SCHEDULE_MORNING_KEYWORDS", "llm,agents")
        monkeypatch.delenv("SCHEDULE_MORNING_STYLE", raising=False)
        config = make_config(keywords="default,keywords")
        profiles = discover_profiles(config)
        morning = next(p for p in profiles if p.name == "morning")
        assert morning.keywords == ["llm", "agents"]

    def test_named_profile_inherits_config_keywords_when_not_set(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_MORNING", "08:00")
        monkeypatch.delenv("SCHEDULE_MORNING_KEYWORDS", raising=False)
        monkeypatch.delenv("SCHEDULE_MORNING_STYLE", raising=False)
        config = make_config(keywords="k8s,helm")
        profiles = discover_profiles(config)
        morning = next(p for p in profiles if p.name == "morning")
        assert morning.keywords == ["k8s", "helm"]

    def test_named_profile_uses_style(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_EVENING", "17:00")
        monkeypatch.setenv("SCHEDULE_EVENING_STYLE", "end-of-day roundup")
        monkeypatch.delenv("SCHEDULE_EVENING_KEYWORDS", raising=False)
        config = make_config()
        profiles = discover_profiles(config)
        evening = next(p for p in profiles if p.name == "evening")
        assert evening.style == "end-of-day roundup"

    def test_schedule_times_env_not_treated_as_profile(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_TIMES", "08:00,17:00")
        config = make_config()
        profiles = discover_profiles(config)
        assert not any(p.name == "times" for p in profiles)

    def test_modifier_var_not_treated_as_profile(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_MORNING", "08:00")
        monkeypatch.setenv("SCHEDULE_MORNING_KEYWORDS", "ai,ml")
        config = make_config()
        profiles = discover_profiles(config)
        # SCHEDULE_MORNING_KEYWORDS should not create a profile named "morning_keywords"
        assert not any(p.name == "morning_keywords" for p in profiles)

    def test_profiles_sorted_by_time(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_EVENING", "17:00")
        monkeypatch.setenv("SCHEDULE_MORNING", "08:00")
        monkeypatch.delenv("SCHEDULE_MORNING_KEYWORDS", raising=False)
        monkeypatch.delenv("SCHEDULE_MORNING_STYLE", raising=False)
        monkeypatch.delenv("SCHEDULE_EVENING_KEYWORDS", raising=False)
        monkeypatch.delenv("SCHEDULE_EVENING_STYLE", raising=False)
        config = make_config()
        profiles = discover_profiles(config)
        named = [p for p in profiles if p.name != "default"]
        times = [p.time for p in named]
        assert times == sorted(times)

    def test_multiple_named_profiles(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_MORNING", "08:00")
        monkeypatch.setenv("SCHEDULE_EVENING", "17:00")
        monkeypatch.delenv("SCHEDULE_MORNING_KEYWORDS", raising=False)
        monkeypatch.delenv("SCHEDULE_MORNING_STYLE", raising=False)
        monkeypatch.delenv("SCHEDULE_EVENING_KEYWORDS", raising=False)
        monkeypatch.delenv("SCHEDULE_EVENING_STYLE", raising=False)
        config = make_config()
        profiles = discover_profiles(config)
        names = {p.name for p in profiles}
        assert {"morning", "evening"} == names


class TestGetProfile:
    def test_returns_matching_profile(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_MORNING", "08:00")
        monkeypatch.delenv("SCHEDULE_MORNING_KEYWORDS", raising=False)
        monkeypatch.delenv("SCHEDULE_MORNING_STYLE", raising=False)
        config = make_config()
        p = get_profile(config, "morning")
        assert p is not None
        assert p.name == "morning"

    def test_returns_none_for_unknown_profile(self, monkeypatch):
        monkeypatch.delenv("SCHEDULE_MORNING", raising=False)
        config = make_config()
        assert get_profile(config, "morning") is None

    def test_case_insensitive(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_MORNING", "08:00")
        monkeypatch.delenv("SCHEDULE_MORNING_KEYWORDS", raising=False)
        monkeypatch.delenv("SCHEDULE_MORNING_STYLE", raising=False)
        config = make_config()
        assert get_profile(config, "MORNING") is not None
        assert get_profile(config, "Morning") is not None


class TestDigestProfile:
    def test_default_style_is_empty(self):
        p = DigestProfile(name="test", time="08:00", keywords=["ai"])
        assert p.style == ""

    def test_keywords_default_empty(self):
        p = DigestProfile(name="test", time="08:00")
        assert p.keywords == []
