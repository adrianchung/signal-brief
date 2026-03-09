import logging

from google import genai

from src.analysis.claude import PROMPT_TEMPLATE, _format_stories, _build_sources_section

logger = logging.getLogger(__name__)

# Default fallback chain — overridden by config.gemini_model_list
DEFAULT_MODELS = ["gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash"]

_RETRYABLE_KEYWORDS = ("503", "unavailable", "overloaded", "429", "rate limit", "quota exceeded")


def _is_retryable(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(k in msg for k in _RETRYABLE_KEYWORDS)


class GeminiAnalyzer:
    def __init__(self, api_key: str, models: list[str] | None = None) -> None:
        self.client = genai.Client(api_key=api_key)
        self.models = models or DEFAULT_MODELS

    def analyze(
        self,
        stories: list[dict],
        keywords: list[str],
        style_hint: str = "",
        source_names: list[str] | None = None,
        include_hn_discussion: bool = False,
    ) -> str:
        formatted = _format_stories(stories, include_hn_discussion)
        style_section = f"\n{style_hint}" if style_hint else ""
        sources_section = _build_sources_section(keywords, source_names)
        hn_discussion_instruction = (
            "\n  For HN stories that have a separate 'HN discussion:' URL in the item list, "
            "add a second line under the bullet: `[N comments on HN](hn_url)`."
            if include_hn_discussion else ""
        )
        prompt = PROMPT_TEMPLATE.format(
            n=len(stories),
            style_section=style_section,
            sources_section=sources_section,
            hn_discussion_instruction=hn_discussion_instruction,
            formatted_story_list=formatted,
        )

        last_exc: Exception | None = None
        for model in self.models:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                if model != self.models[0]:
                    logger.info("Gemini model %s succeeded", model)
                return response.text
            except Exception as exc:
                if _is_retryable(exc):
                    logger.warning("Gemini model %s failed (%s) — trying next model", model, exc)
                    last_exc = exc
                    continue
                raise  # non-transient error — surface immediately

        raise last_exc  # type: ignore[misc]  # all models failed with transient errors
