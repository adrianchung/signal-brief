from unittest.mock import MagicMock, call, patch

from src.pipeline import run_pipeline, NO_STORIES_MSG


SAMPLE_STORY = {"title": "T", "score": 200, "url": "https://example.com",
                "author": "u", "num_comments": 0, "created_at": ""}


def make_config(keywords="ai,ml", min_score=150):
    cfg = MagicMock()
    cfg.keyword_list = keywords.split(",")
    cfg.min_score = min_score
    cfg.alert_channel = None
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


class TestRunPipelineErrorAlerting:
    def test_fetch_failure_triggers_alert(self):
        config = make_config()
        exc = RuntimeError("algolia down")

        with patch("src.pipeline.fetch_stories", side_effect=exc), \
             patch("src.pipeline.send_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_called_once_with(config, "fetch", exc)

    def test_fetch_failure_skips_delivery(self):
        config = make_config()
        mock_deliverer = MagicMock()

        with patch("src.pipeline.fetch_stories", side_effect=RuntimeError("down")), \
             patch("src.pipeline.send_alert"), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]):
            run_pipeline(config, provider="gemini")

        mock_deliverer.send.assert_not_called()

    def test_analyze_failure_triggers_alert(self):
        config = make_config()
        exc = RuntimeError("llm error")
        stories = [{"title": "T", "score": 200, "url": "https://example.com",
                    "author": "u", "num_comments": 0, "created_at": ""}]
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = exc

        with patch("src.pipeline.fetch_stories", return_value=stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.send_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_called_once_with(config, "analyze", exc)

    def test_all_deliveries_fail_triggers_alert(self):
        config = make_config()
        stories = [{"title": "T", "score": 200, "url": "https://example.com",
                    "author": "u", "num_comments": 0, "created_at": ""}]
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"
        failing = MagicMock()
        exc = Exception("network error")
        failing.send.side_effect = exc

        with patch("src.pipeline.fetch_stories", return_value=stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[failing]), \
             patch("src.pipeline.send_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_called_once_with(config, "delivery", exc)

    def test_partial_delivery_success_does_not_trigger_alert(self):
        config = make_config()
        stories = [{"title": "T", "score": 200, "url": "https://example.com",
                    "author": "u", "num_comments": 0, "created_at": ""}]
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"
        failing = MagicMock()
        failing.send.side_effect = Exception("fail")
        succeeding = MagicMock()

        with patch("src.pipeline.fetch_stories", return_value=stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[failing, succeeding]), \
             patch("src.pipeline.send_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_not_called()

    def test_zero_stories_does_not_trigger_alert(self):
        config = make_config()
        mock_deliverer = MagicMock()

        with patch("src.pipeline.fetch_stories", return_value=[]), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]), \
             patch("src.pipeline.send_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_not_called()

    def test_fetch_failure_in_dry_run_does_not_alert(self):
        config = make_config()

        with patch("src.pipeline.fetch_stories", side_effect=RuntimeError("down")), \
             patch("src.pipeline.send_alert") as mock_alert:
            run_pipeline(config, provider="gemini", dry_run=True)

        mock_alert.assert_not_called()
