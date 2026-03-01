from unittest.mock import MagicMock, patch

from src.pipeline import run_pipeline, NO_STORIES_MSG


SAMPLE_STORY = {"title": "T", "score": 200, "url": "https://example.com",
                "author": "u", "num_comments": 0, "created_at": ""}


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
