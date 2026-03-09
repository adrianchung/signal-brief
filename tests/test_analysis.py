from unittest.mock import MagicMock, patch

import pytest

from src.analysis import get_analyzer
from src.analysis.claude import PROMPT_TEMPLATE, _format_stories, ClaudeAnalyzer
from src.analysis.gemini import GeminiAnalyzer


SAMPLE_STORIES = [
    {
        "title": "AI Takes Over the World",
        "score": 500,
        "url": "https://example.com/ai",
        "author": "alice",
        "num_comments": 42,
        "created_at": "2024-01-01T00:00:00Z",
    },
    {
        "title": "Kubernetes 2.0 Released",
        "score": 300,
        "url": "https://example.com/k8s",
        "author": "bob",
        "num_comments": 17,
        "created_at": "2024-01-01T01:00:00Z",
    },
]


# ---------------------------------------------------------------------------
# _format_stories
# ---------------------------------------------------------------------------

class TestFormatStories:
    def test_includes_story_title(self):
        result = _format_stories(SAMPLE_STORIES)
        assert "AI Takes Over the World" in result

    def test_includes_story_url(self):
        result = _format_stories(SAMPLE_STORIES)
        assert "https://example.com/ai" in result
        assert "https://example.com/k8s" in result

    def test_includes_score(self):
        result = _format_stories(SAMPLE_STORIES)
        assert "500" in result

    def test_includes_author(self):
        result = _format_stories(SAMPLE_STORIES)
        assert "alice" in result

    def test_numbered_from_one(self):
        result = _format_stories(SAMPLE_STORIES)
        assert result.startswith("1.")

    def test_empty_list_returns_empty_string(self):
        assert _format_stories([]) == ""

    def test_hn_discussion_url_included_when_flag_set(self):
        story = {
            "title": "Some Article",
            "url": "https://example.com/article",
            "hn_url": "https://news.ycombinator.com/item?id=12345",
            "score": 100,
            "author": "alice",
            "num_comments": 42,
            "created_at": "",
            "source": "hn",
        }
        result = _format_stories([story], include_hn_discussion=True)
        assert "HN discussion:" in result
        assert "https://news.ycombinator.com/item?id=12345" in result

    def test_hn_discussion_not_shown_when_url_equals_hn_url(self):
        """Ask HN / Show HN posts have no external URL — hn_url == url, don't duplicate."""
        hn_url = "https://news.ycombinator.com/item?id=99999"
        story = {
            "title": "Ask HN: Something",
            "url": hn_url,
            "hn_url": hn_url,
            "score": 50,
            "author": "bob",
            "num_comments": 10,
            "created_at": "",
            "source": "hn",
        }
        result = _format_stories([story], include_hn_discussion=True)
        assert result.count(hn_url) == 1  # url appears once, not twice

    def test_hn_discussion_not_shown_by_default(self):
        story = {
            "title": "Article",
            "url": "https://example.com",
            "hn_url": "https://news.ycombinator.com/item?id=1",
            "score": 50,
            "author": "alice",
            "num_comments": 5,
            "created_at": "",
            "source": "hn",
        }
        result = _format_stories([story])
        assert "HN discussion:" not in result


# ---------------------------------------------------------------------------
# PROMPT_TEMPLATE
# ---------------------------------------------------------------------------

class TestPromptTemplate:
    def test_template_renders_with_placeholders(self):
        formatted = _format_stories(SAMPLE_STORIES)
        prompt = PROMPT_TEMPLATE.format(
            n=len(SAMPLE_STORIES),
            keywords="ai, kubernetes",
            style_section="",
            sources_section=" These matched keywords: ai, kubernetes.",
            hn_discussion_instruction="",
            formatted_story_list=formatted,
        )
        assert "2" in prompt
        assert "ai, kubernetes" in prompt
        assert "AI Takes Over the World" in prompt

    def test_prompt_requests_markdown(self):
        assert "Markdown" in PROMPT_TEMPLATE or "markdown" in PROMPT_TEMPLATE

    def test_prompt_has_theme_section(self):
        assert "## Theme" in PROMPT_TEMPLATE

    def test_prompt_has_top_stories_section(self):
        assert "## Top Stories" in PROMPT_TEMPLATE

    def test_prompt_has_bottom_line_section(self):
        assert "## Bottom Line" in PROMPT_TEMPLATE

    def test_prompt_instructs_markdown_link_format(self):
        # The prompt must instruct the model to use [Title](url) markdown links
        assert "[Story Title](url)" in PROMPT_TEMPLATE or "[title](url)" in PROMPT_TEMPLATE.lower()


# ---------------------------------------------------------------------------
# ClaudeAnalyzer
# ---------------------------------------------------------------------------

class TestClaudeAnalyzer:
    def test_analyze_returns_text_from_api(self):
        with patch("src.analysis.claude.anthropic.Anthropic") as mock_cls:
            mock_client = mock_cls.return_value
            mock_msg = MagicMock()
            mock_msg.content = [MagicMock(text="## Theme\nSome theme")]
            mock_client.messages.create.return_value = mock_msg

            analyzer = ClaudeAnalyzer("fake-key")
            result = analyzer.analyze(SAMPLE_STORIES, ["ai"])

        assert result == "## Theme\nSome theme"

    def test_analyze_sends_correct_model(self):
        with patch("src.analysis.claude.anthropic.Anthropic") as mock_cls:
            mock_client = mock_cls.return_value
            mock_msg = MagicMock()
            mock_msg.content = [MagicMock(text="brief")]
            mock_client.messages.create.return_value = mock_msg

            ClaudeAnalyzer("fake-key").analyze(SAMPLE_STORIES, ["ai"])
            call_kwargs = mock_client.messages.create.call_args[1]

        assert call_kwargs["model"] == "claude-sonnet-4-6"

    def test_analyze_includes_story_urls_in_prompt(self):
        with patch("src.analysis.claude.anthropic.Anthropic") as mock_cls:
            mock_client = mock_cls.return_value
            mock_msg = MagicMock()
            mock_msg.content = [MagicMock(text="brief")]
            mock_client.messages.create.return_value = mock_msg

            ClaudeAnalyzer("fake-key").analyze(SAMPLE_STORIES, ["ai"])
            call_kwargs = mock_client.messages.create.call_args[1]
            prompt = call_kwargs["messages"][0]["content"]

        assert "https://example.com/ai" in prompt
        assert "https://example.com/k8s" in prompt

    def test_analyze_uses_max_tokens_1024(self):
        with patch("src.analysis.claude.anthropic.Anthropic") as mock_cls:
            mock_client = mock_cls.return_value
            mock_msg = MagicMock()
            mock_msg.content = [MagicMock(text="brief")]
            mock_client.messages.create.return_value = mock_msg

            ClaudeAnalyzer("fake-key").analyze(SAMPLE_STORIES, ["ai"])
            call_kwargs = mock_client.messages.create.call_args[1]

        assert call_kwargs["max_tokens"] == 1024


# ---------------------------------------------------------------------------
# GeminiAnalyzer
# ---------------------------------------------------------------------------

class TestGeminiAnalyzer:
    def test_analyze_returns_text_from_api(self):
        with patch("src.analysis.gemini.genai.Client") as mock_cls:
            mock_client = mock_cls.return_value
            mock_response = MagicMock()
            mock_response.text = "## Theme\nSome theme"
            mock_client.models.generate_content.return_value = mock_response

            analyzer = GeminiAnalyzer("fake-key")
            result = analyzer.analyze(SAMPLE_STORIES, ["ai"])

        assert result == "## Theme\nSome theme"

    def test_analyze_uses_shared_prompt_template(self):
        """GeminiAnalyzer must use the same PROMPT_TEMPLATE as ClaudeAnalyzer."""
        with patch("src.analysis.gemini.genai.Client") as mock_cls:
            mock_client = mock_cls.return_value
            mock_response = MagicMock()
            mock_response.text = "brief"
            mock_client.models.generate_content.return_value = mock_response

            GeminiAnalyzer("fake-key").analyze(SAMPLE_STORIES, ["ai"])
            call_kwargs = mock_client.models.generate_content.call_args[1]
            prompt = call_kwargs["contents"]

        assert "## Theme" in prompt
        assert "## Top Stories" in prompt
        assert "## Bottom Line" in prompt

    def test_analyze_sends_correct_model(self):
        with patch("src.analysis.gemini.genai.Client") as mock_cls:
            mock_client = mock_cls.return_value
            mock_response = MagicMock()
            mock_response.text = "brief"
            mock_client.models.generate_content.return_value = mock_response

            GeminiAnalyzer("fake-key").analyze(SAMPLE_STORIES, ["ai"])
            call_kwargs = mock_client.models.generate_content.call_args[1]

        assert call_kwargs["model"] == "gemini-3-flash-preview"


# ---------------------------------------------------------------------------
# get_analyzer factory
# ---------------------------------------------------------------------------

class TestGetAnalyzer:
    def test_returns_claude_analyzer_for_claude_provider(self):
        cfg = MagicMock()
        cfg.anthropic_api_key = "fake-key"
        analyzer = get_analyzer(cfg, "claude")
        assert isinstance(analyzer, ClaudeAnalyzer)

    def test_returns_gemini_analyzer_for_gemini_provider(self):
        with patch("src.analysis.gemini.genai.Client"):
            cfg = MagicMock()
            cfg.gemini_api_key = "fake-key"
            analyzer = get_analyzer(cfg, "gemini")
        assert isinstance(analyzer, GeminiAnalyzer)

    def test_raises_for_unknown_provider(self):
        cfg = MagicMock()
        with pytest.raises(RuntimeError, match="Unknown provider"):
            get_analyzer(cfg, "unknown")

    def test_raises_when_claude_key_missing(self):
        cfg = MagicMock()
        cfg.anthropic_api_key = None
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            get_analyzer(cfg, "claude")

    def test_raises_when_gemini_key_missing(self):
        cfg = MagicMock()
        cfg.gemini_api_key = None
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            get_analyzer(cfg, "gemini")
