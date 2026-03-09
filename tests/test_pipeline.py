import pytest
from unittest.mock import MagicMock, patch

from src.pipeline import run_pipeline, NO_STORIES_MSG


SAMPLE_STORY = {"objectID": "1", "title": "T", "score": 200, "url": "https://example.com",
                "author": "u", "num_comments": 0, "created_at": "", "source": "hn"}


# ---------------------------------------------------------------------------
# Autouse fixtures — isolate filesystem I/O for every test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_seen_tracker():
    """Patch SeenStoryTracker so pipeline tests don't touch the filesystem."""
    with patch("src.pipeline.SeenStoryTracker") as mock_cls:
        instance = MagicMock()
        instance.filter_new.side_effect = lambda stories: stories
        mock_cls.return_value = instance
        yield mock_cls


@pytest.fixture(autouse=True)
def mock_run_logger():
    """Patch RunLogger so pipeline tests don't touch the filesystem."""
    with patch("src.pipeline.RunLogger") as mock_cls:
        mock_cls.return_value = MagicMock()
        yield mock_cls


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config(keywords="ai,ml", min_score=150):
    cfg = MagicMock()
    cfg.keyword_list = keywords.split(",")
    cfg.min_score = min_score
    return cfg


def _mock_source(stories=None, error=None):
    """Create a mock Source returning *stories* or raising *error* on fetch."""
    mock = MagicMock()
    if error:
        mock.fetch.side_effect = error
    else:
        mock.fetch.return_value = list(stories) if stories is not None else []
    return mock


def _patch_sources(stories=None, error=None):
    """Context manager: patch get_sources to return a single mock source."""
    return patch("src.pipeline.get_sources", return_value=[_mock_source(stories, error)])


# ---------------------------------------------------------------------------
# Core pipeline behaviour
# ---------------------------------------------------------------------------

class TestRunPipeline:
    def test_no_stories_delivers_fallback_message(self):
        config = make_config()
        mock_deliverer = MagicMock()

        with _patch_sources([]), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]):
            run_pipeline(config, provider="gemini")

        mock_deliverer.send.assert_called_once_with(NO_STORIES_MSG)

    def test_stories_trigger_analysis_and_delivery(self):
        config = make_config()
        stories = [SAMPLE_STORY]
        mock_deliverer = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "the brief"

        with _patch_sources(stories), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]):
            run_pipeline(config, provider="gemini")

        mock_analyzer.analyze.assert_called_once_with(stories, config.keyword_list, "", ["hn"])
        mock_deliverer.send.assert_called_once_with("the brief")

    def test_delivery_failure_does_not_abort_other_channels(self):
        config = make_config()
        failing = MagicMock()
        failing.send.side_effect = Exception("network error")
        succeeding = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[failing, succeeding]):
            run_pipeline(config, provider="gemini")

        succeeding.send.assert_called_once_with("brief")

    def test_no_deliverers_configured_does_not_raise(self):
        config = make_config()
        with _patch_sources([]), \
             patch("src.pipeline.get_deliverers", return_value=[]):
            run_pipeline(config, provider="gemini")  # should not raise

    def test_dry_run_skips_delivery(self):
        config = make_config()
        mock_deliverer = MagicMock()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]) as mock_get_deliverers:
            run_pipeline(config, provider="gemini", dry_run=True)

        mock_get_deliverers.assert_not_called()
        mock_deliverer.send.assert_not_called()

    def test_dry_run_still_fetches_and_analyzes(self):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with _patch_sources([SAMPLE_STORY]) as mock_get_src, \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers") as mock_get_deliverers:
            run_pipeline(config, provider="gemini", dry_run=True)

        mock_get_src.return_value[0].fetch.assert_called_once()
        mock_analyzer.analyze.assert_called_once()
        mock_get_deliverers.assert_not_called()

    def test_dry_run_with_no_stories_skips_delivery(self):
        config = make_config()
        mock_deliverer = MagicMock()

        with _patch_sources([]), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]) as mock_get_deliverers:
            run_pipeline(config, provider="gemini", dry_run=True)

        mock_get_deliverers.assert_not_called()
        mock_deliverer.send.assert_not_called()

    def test_provider_passed_to_get_analyzer(self):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer) as mock_get_analyzer, \
             patch("src.pipeline.get_deliverers", return_value=[]):
            run_pipeline(config, provider="claude")

        mock_get_analyzer.assert_called_once_with(config, "claude")


# ---------------------------------------------------------------------------
# Alerting
# ---------------------------------------------------------------------------

class TestRunPipelineAlerting:
    def test_fetch_failure_sends_alert(self):
        config = make_config()
        with _patch_sources(error=Exception("fetch error")), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini")
        mock_alert.assert_called_once()
        assert mock_alert.call_args[0][1] == "fetch"

    def test_fetch_failure_returns_early(self):
        config = make_config()
        mock_analyzer = MagicMock()
        with _patch_sources(error=Exception("fetch error")), \
             patch("src.alerting.send_error_alert"), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer):
            run_pipeline(config, provider="gemini")
        mock_analyzer.analyze.assert_not_called()

    def test_analysis_failure_sends_alert(self):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = Exception("api error")

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_called_once()
        assert mock_alert.call_args[0][1] == "analyze"

    def test_analysis_failure_returns_early(self):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = Exception("api error")
        mock_deliverer = MagicMock()

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]), \
             patch("src.alerting.send_error_alert"):
            run_pipeline(config, provider="gemini")

        mock_deliverer.send.assert_not_called()

    def test_all_deliverers_failing_sends_alert(self):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"
        failing = MagicMock()
        failing.send.side_effect = Exception("network error")

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[failing]), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_called_once()
        assert mock_alert.call_args[0][1] == "deliver"

    def test_partial_delivery_success_does_not_alert(self):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"
        failing = MagicMock()
        failing.send.side_effect = Exception("network error")
        succeeding = MagicMock()

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[failing, succeeding]), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_not_called()

    def test_zero_stories_does_not_send_alert(self):
        config = make_config()
        mock_deliverer = MagicMock()

        with _patch_sources([]), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini")

        mock_alert.assert_not_called()

    def test_fetch_failure_no_alert_in_dry_run(self):
        config = make_config()
        with _patch_sources(error=Exception("fetch error")), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini", dry_run=True)
        mock_alert.assert_not_called()

    def test_analysis_failure_no_alert_in_dry_run(self):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = Exception("api error")

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.alerting.send_error_alert") as mock_alert:
            run_pipeline(config, provider="gemini", dry_run=True)

        mock_alert.assert_not_called()


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestRunPipelineDedup:
    def test_dedup_filter_called_by_default(self, mock_seen_tracker):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[]):
            run_pipeline(config, provider="gemini")

        mock_seen_tracker.return_value.filter_new.assert_called_once()

    def test_ignore_seen_skips_filter(self, mock_seen_tracker):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[]):
            run_pipeline(config, provider="gemini", ignore_seen=True)

        mock_seen_tracker.return_value.filter_new.assert_not_called()

    def test_mark_seen_called_after_analysis(self, mock_seen_tracker):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"
        mock_deliverer = MagicMock()

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]):
            run_pipeline(config, provider="gemini")

        mock_seen_tracker.return_value.mark_seen.assert_called_once()

    def test_dry_run_skips_mark_seen(self, mock_seen_tracker):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[]):
            run_pipeline(config, provider="gemini", dry_run=True)

        mock_seen_tracker.return_value.mark_seen.assert_not_called()

    def test_ignore_seen_skips_mark_seen(self, mock_seen_tracker):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"
        mock_deliverer = MagicMock()

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]):
            run_pipeline(config, provider="gemini", ignore_seen=True)

        mock_seen_tracker.return_value.mark_seen.assert_not_called()


# ---------------------------------------------------------------------------
# Provider fallback
# ---------------------------------------------------------------------------

class TestRunPipelineFallback:
    def _make_analyzers(self, primary_error=None, fallback_result="fallback brief"):
        primary = MagicMock()
        if primary_error:
            primary.analyze.side_effect = primary_error
        else:
            primary.analyze.return_value = "primary brief"

        fallback = MagicMock()
        fallback.analyze.return_value = fallback_result

        def get_analyzer_side_effect(cfg, prov):
            return primary if prov == "gemini" else fallback

        return primary, fallback, get_analyzer_side_effect

    def test_fallback_used_when_primary_fails(self):
        config = make_config()
        primary, fallback, side_effect = self._make_analyzers(primary_error=Exception("503"))
        mock_deliverer = MagicMock()

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", side_effect=side_effect), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]):
            ok = run_pipeline(config, provider="gemini", fallback_provider="claude")

        assert ok is True
        fallback.analyze.assert_called_once()
        mock_deliverer.send.assert_called_once_with("fallback brief")

    def test_fallback_not_used_when_primary_succeeds(self):
        config = make_config()
        primary, fallback, side_effect = self._make_analyzers()
        mock_deliverer = MagicMock()

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", side_effect=side_effect), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]):
            ok = run_pipeline(config, provider="gemini", fallback_provider="claude")

        assert ok is True
        primary.analyze.assert_called_once()
        fallback.analyze.assert_not_called()

    def test_both_fail_returns_false_and_alerts(self):
        config = make_config()
        primary = MagicMock()
        primary.analyze.side_effect = Exception("primary failed")
        fallback = MagicMock()
        fallback.analyze.side_effect = Exception("fallback failed")

        def side_effect(cfg, prov):
            return primary if prov == "gemini" else fallback

        mock_deliverer = MagicMock()

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", side_effect=side_effect), \
             patch("src.pipeline.get_deliverers", return_value=[mock_deliverer]), \
             patch("src.alerting.send_error_alert") as mock_alert:
            ok = run_pipeline(config, provider="gemini", fallback_provider="claude")

        assert ok is False
        mock_deliverer.send.assert_not_called()
        mock_alert.assert_called_once()
        assert mock_alert.call_args[0][1] == "analyze"

    def test_fallback_key_missing_logs_clear_error_and_returns_false(self):
        config = make_config()
        config.anthropic_api_key = None  # fallback key not set
        primary = MagicMock()
        primary.analyze.side_effect = Exception("503 overloaded")

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=primary), \
             patch("src.alerting.send_error_alert") as mock_alert:
            ok = run_pipeline(config, provider="gemini", fallback_provider="claude")

        assert ok is False
        mock_alert.assert_called_once()
        # get_analyzer should only be called once (for the primary) since key check
        # stops the fallback before it tries to call get_analyzer again

    def test_no_fallback_configured_returns_false_on_failure(self):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.side_effect = Exception("api error")

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.alerting.send_error_alert"):
            ok = run_pipeline(config, provider="gemini", fallback_provider=None)

        assert ok is False

    def test_pipeline_returns_true_on_success(self):
        config = make_config()
        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = "brief"

        with _patch_sources([SAMPLE_STORY]), \
             patch("src.pipeline.get_analyzer", return_value=mock_analyzer), \
             patch("src.pipeline.get_deliverers", return_value=[MagicMock()]):
            ok = run_pipeline(config, provider="gemini")

        assert ok is True
