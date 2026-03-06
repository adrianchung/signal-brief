from google import genai

from src.analysis.claude import PROMPT_TEMPLATE, _format_stories

MODEL = "gemini-3-flash-preview"


class GeminiAnalyzer:
    def __init__(self, api_key: str) -> None:
        self.client = genai.Client(api_key=api_key)

    def analyze(self, stories: list[dict], keywords: list[str], style_hint: str = "") -> str:
        formatted = _format_stories(stories)
        style_section = f"\n{style_hint}" if style_hint else ""
        prompt = PROMPT_TEMPLATE.format(
            n=len(stories),
            keywords=", ".join(keywords),
            style_section=style_section,
            formatted_story_list=formatted,
        )
        response = self.client.models.generate_content(
            model=MODEL,
            contents=prompt,
        )
        return response.text
