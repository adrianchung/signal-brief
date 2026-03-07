import anthropic

MODEL = "claude-sonnet-4-6"

PROMPT_TEMPLATE = """\
You are a senior engineer reviewing today's signal digest for a busy technical lead.{style_section}
Below are {n} items from the past 24 hours.{sources_section}

Respond in **Markdown** using exactly this structure:

## Theme
One sentence naming the overarching theme connecting the top items, or "No clear theme today" if none.

## Top Stories
Up to 5 bullet points. Each must use this exact format:
- **[Title](url)** — one sentence: what it is and why it matters (or flag it as hype). _(N pts)_ for HN items; _(via Source Name)_ for non-HN items.

Use the exact URLs from the item list below as the link targets.
Use the exact point score from the item list for HN items. Use the feed name for non-HN items.

## Bottom Line
One sentence on what is actually shifting today.

Rules: Be direct. Cut noise. Flag hype explicitly. No filler phrases.

Items:
{formatted_story_list}"""


def _build_sources_section(keywords: list[str], source_names: list[str] | None) -> str:
    names = source_names or ["hn"]
    if names == ["hn"]:
        return f" These matched keywords: {', '.join(keywords)}."
    parts = []
    if "hn" in names:
        parts.append(f"Hacker News (keywords: {', '.join(keywords)})")
    if "ai_tracker" in names:
        parts.append("AI Industry Tracker")
    if "stocks" in names:
        parts.append("Market Movers")
    extras = [n for n in names if n not in ("hn", "ai_tracker", "stocks")]
    parts.extend(extras)
    return f"\nSources contributing to this brief: {', '.join(parts)}."


def _format_stories(stories: list[dict]) -> str:
    lines = []
    for i, story in enumerate(stories, 1):
        source_tag = f"[{story.get('feed') or story.get('source', 'HN')}] " if story.get("source") != "hn" else ""
        lines.append(
            f"{i}. {source_tag}[{story.get('score', 0)} pts] {story['title']}\n"
            f"   {story['url']}\n"
            f"   by {story['author']} | {story.get('num_comments', 0)} comments | {story.get('created_at', '')}"
        )
    return "\n\n".join(lines)


class ClaudeAnalyzer:
    def __init__(self, api_key: str) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)

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
        message = self.client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text  # type: ignore[union-attr]
