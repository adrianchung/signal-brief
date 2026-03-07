from google import genai

from src.analysis.claude import PROMPT_TEMPLATE, _format_stories, _build_sources_section

MODEL = "gemini-3-flash-preview"


class GeminiAnalyzer:
    def __init__(self, api_key: str) -> None:
        self.client = genai.Client(api_key=api_key)

    def analyze(
        self,
        stories: list[dict],
        keywords: list[str],
        style_hint: str = "",
        source_names: list[str] | None = None,
    ) -> str:
        formatted = _format_stories(stories)
        style_section = f"\n{style_hint}" if style_hint else ""
        sources_section = _build_sources_section(keywords, source_names)
        prompt = PROMPT_TEMPLATE.format(
            n=len(stories),
            style_section=style_section,
            sources_section=sources_section,
            formatted_story_list=formatted,
        )
        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        return response.text
