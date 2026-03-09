from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from src.config import Settings


class Analyzer(Protocol):
    def analyze(self, stories: list[dict], keywords: list[str], style_hint: str = "", source_names: list[str] | None = None, include_hn_discussion: bool = False) -> str: ...


def get_analyzer(config: "Settings", provider: str) -> Analyzer:
    if provider == "gemini":
        if not config.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY not configured")
        from src.analysis.gemini import GeminiAnalyzer
        return GeminiAnalyzer(config.gemini_api_key)
    if provider == "claude":
        if not config.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not configured")
        from src.analysis.claude import ClaudeAnalyzer
        return ClaudeAnalyzer(config.anthropic_api_key)
    raise RuntimeError(f"Unknown provider: {provider!r}")
