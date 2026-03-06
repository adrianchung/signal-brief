import pytest
from unittest.mock import MagicMock, patch

from src.pipeline import run_pipeline, NO_STORIES_MSG


SAMPLE_STORY = {"objectID": "1", "title": "T", "score": 200, "url": "https://example.com",
                "author": "u", "num_comments": 0, "created_at": ""}


@pytest.fixture(autouse=True)
def mock_seen_tracker():
    """Patch SeenStoryTracker so pipeline tests don't touch the filesystem
    and don't fail on MagicMock config fields."""
    with patch("src.pipeline.SeenStoryTracker") as mock_cls:
        instance = MagicMock()
        instance.filter_new.side_effect = lambda stories: stories
        mock_cls.return_value = instance
        yield mock_cls


def make_config(keywords="ai,ml", min_score=150):
    cfg = MagicMock()
    cfg.keyword_list = keywords.split(",")
    cfg.min_score = min_score
    return cfg


class TestRunPipeline:
    def test_no_stories_delivers_fallback_message(self):
        config = make_config()
        mock_deliverer = MagicMock()

        with patch("src.pipeline.fetch_stories", return_value=[]) as mock_fetch, \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]):
            run_pipeline(config, provider="gemini")

        mock_deliverer.send.assert_called_once_with(NO_STORIES_MSG)

    def test_stories_trigger_analysis_and_delivery(self):
        config = make_config()
        stories = [{"title": "Test", "score": 200, "url": "https://example.com",
                    "author": "u", "num_comments": 5, "created_at": ""}]
        mock_deliverer = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "the brief"

        with patch("src.pipeline.fetch_stories", return_value=stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]):
            run_pipeline(config, provider="gemini")

        mock_analyzer.analyze.assert_called_once_with(stories, config.keyword_list)
        mock_deliverer.send.assert_called_once_with("the brief")

    def test_delivery_failure_does_not_abort_other_channels(self):
        config = make_config()
        stories = [{"title": "T", "score": 200, "url": "https://example.com",
                    "author": "u", "num_comments": 0, "created_at": ""}]
        failing = MagicMock()
        failing.send.side_effect = Exception("network error")
        succeeding = MagicMock()

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with patch("src.pipeline.fetch_stories", return_value=stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[failing, succeeding]):
            run_pipeline(config, provider="gemini")

        succeeding.send.assert_called_once_with("brief")

    def test_no_deliverers_configured_does_not_raise(self):
        config = make_config()
        with patch("src.pipeline.fetch_stories", return_value=[]), \
             patch("src.pipeline.get_deliverers", return_value=[]):
            run_pipeline(config, provider="gemini")  # should not raise

    def test_dry_run_skips_delivery(self):
        config = make_config()
        mock_deliverer = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with patch("src.pipeline.fetch_stories", return_value=[SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]) as mock_get_deliverers:
            run_pipeline(config, provider="gemini", dry_run=True)

        mock_get_deliverers.assert_not_called()
        mock_deliverer.send.assert_not_called()

    def test_dry_run_still_fetches_and_analyzes(self):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with patch("src.pipeline.fetch_stories", return_value=[SAMPLE_STORY]) as mock_fetch, \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers") as mock_get_deliverers:
            run_pipeline(config, provider="gemini", dry_run=True)

        mock_fetch.assert_called_once()
        mock_analyzer.analyze.assert_called_once()
        mock_get_deliverers.assert_not_called()

    def test_dry_run_with_no_stories_skips_delivery(self):
        config = make_config()
        mock_deliverer = MagicMock()

        with patch("src.pipeline.fetch_stories", return_value=[]), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]) as mock_get_deliverers:
            run_pipeline(config, provider="gemini", dry_run=True)

        mock_get_deliverers.assert_not_called()
        mock_deliverer.send.assert_not_called()

    def test_provider_passed_to_get_analyzer(self):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"
        stories = [{"title": "T", "score": 200, "url": "https://example.com",
                    "author": "u", "num_comments": 0, "created_at": ""}]

        with patch("src.pipeline.fetch_stories", return_value=stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer) as mock_get_analyzer, \
             patch("src.pipeline.get_deliverers", return_value=[]):
            run_pipeline(config, provider="claude")

        mock_get_analyzer.assert_called_once_with(config, "claude")


class TestRunPipelineAlerting:
    def test_fetch_failure_sends_alert(self):
        config = make_config()
        with patch("src.pipeline.fetch_stories", side_effect=Exception("fetch error")), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini")
        mock_alert.assert_called_once()
        assert mock_alert.call_args[0][1] == "fetch"

    def test_fetch_failure_returns_early(self):
        config = make_config()
        mock_analyzer = MagicMock()
        with patch("src.pipeline.fetch_stories", side_effect=Exception("fetch error")), \
             patch("src.alerting.send_error_alert"), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer):
            run_pipeline(config, provider="gemini")
        mock_analyzer.analyze.assert_not_called()

    def test_analysis_failure_sends_alert(self):
        config = make_config()
        stories = [SAMPLE_STORY]
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = Exception("api error")

        with patch("src.pipeline.fetch_stories", return_value=stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_called_once()
        assert mock_alert.call_args[0][1] == "analyze"

    def test_analysis_failure_returns_early(self):
        config = make_config()
        stories = [SAMPLE_STORY]
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = Exception("api error")
        mock_deliverer = MagicMock()

        with patch("src.pipeline.fetch_stories", return_value=stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]), \
             patch("src.alerting.send_error_alert"):
            run_pipeline(config, provider="gemini")

        mock_deliverer.send.assert_not_called()

    def test_all_deliverers_failing_sends_alert(self):
        config = make_config()
        stories = [SAMPLE_STORY]
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"
        failing = MagicMock()
        failing.send.side_effect = Exception("network error")

        with patch("src.pipeline.fetch_stories", return_value=stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[failing]), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_called_once()
        assert mock_alert.call_args[0][1] == "deliver"

    def test_partial_delivery_success_does_not_alert(self):
        config = make_config()
        stories = [SAMPLE_STORY]
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"
        failing = MagicMock()
        failing.send.side_effect = Exception("network error")
        succeeding = MagicMock()

        with patch("src.pipeline.fetch_stories", return_value=stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[failing, succeeding]), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_not_called()

    def test_zero_stories_does_not_send_alert(self):
        config = make_config()
        mock_deliverer = MagicMock()

        with patch("src.pipeline.fetch_stories", return_value=[]), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_not_called()

    def test_fetch_failure_no_alert_in_dry_run(self):
        config = make_config()
        with patch("src.pipeline.fetch_stories", side_effect=Exception("fetch error")), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini", dry_run=True)
        mock_alert.assert_not_called()

    def test_analysis_failure_no_alert_in_dry_run(self):
        config = make_config()
        stories = [SAMPLE_STORY]
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = Exception("api error")

        with patch("src.pipeline.fetch_stories", return_value=stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini", dry_run=True)

        mock_alert.assert_not_called()


class TestRunPipelineDedup:
    def test_dedup_filter_called_by_default(self, mock_seen_tracker):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with patch("src.pipeline.fetch_stories", return_value=[SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[]):
            run_pipeline(config, provider="gemini")

        mock_seen_tracker.return_value.filter_new.assert_called_once()

    def test_ignore_seen_skips_filter(self, mock_seen_tracker):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with patch("src.pipeline.fetch_stories", return_value=[SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[]):
            run_pipeline(config, provider="gemini", ignore_seen=True)

        mock_seen_tracker.return_value.filter_new.assert_not_called()

    def test_mark_seen_called_after_analysis(self, mock_seen_tracker):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"
        mock_deliverer = MagicMock()

        with patch("src.pipeline.fetch_stories", return_value=[SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]):
            run_pipeline(config, provider="gemini")

        mock_seen_tracker.return_value.mark_seen.assert_called_once()

    def test_dry_run_skips_mark_seen(self, mock_seen_tracker):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with patch("src.pipeline.fetch_stories", return_value=[SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[]):
            run_pipeline(config, provider="gemini", dry_run=True)

        mock_seen_tracker.return_value.mark_seen.assert_not_called()

    def test_ignore_seen_skips_mark_seen(self, mock_seen_tracker):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"
        mock_deliverer = MagicMock()

        with patch("src.pipeline.fetch_stories", return_value=[SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]):
            run_pipeline(config, provider="gemini", ignore_seen=True)

        mock_seen_tracker.return_value.mark_seen.assert_not_called()
