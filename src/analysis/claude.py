import anthropic

MODEL = "claude-sonnet-4-6"

PROMPT_TEMPLATE = """\
You are a senior engineer reviewing today's Hacker News signal for a busy technical lead.

Below are {n} stories from the past 12 hours that matched keywords: {keywords}.

Respond in **Markdown** using exactly this structure:

## Theme
One sentence naming the overarching theme connecting the top stories, or "No clear theme today" if none.

## Top Stories
Up to 5 bullet points. Each must use this exact format:
- **[Story Title](url)** — one sentence: what it is and why it matters (or flag it as hype).

Use the exact URLs from the story list below as the link targets.

## Bottom Line
One sentence on what is actually shifting today.

Rules: Be direct. Cut noise. Flag hype explicitly. No filler phrases.

Stories:
{formatted_story_list}"""


def _format_stories(stories: list[dict]) -> str:
    lines = []
    for i, story in enumerate(stories, 1):
        lines.append(
            f"{i}. [{story['score']} pts] {story['title']}\n"
            f"   {story['url']}\n"
            f"   by {story['author']} | {story['num_comments']} comments | {story['created_at']}"
        )
    return "\n\n".join(lines)


class ClaudeAnalyzer:
    def __init__(self, api_key: str) -> None:
        self.client = anthropic.Anthropic(api_key=api_key)

    def analyze(self, stories: list[dict], keywords: list[str]) -> str:
        formatted = _format_stories(stories)
        prompt = PROMPT_TEMPLATE.format(
            n=len(stories),
            keywords=", ".join(keywords),
            formatted_story_list=formatted,
        )
        message = self.client.messages.create(
            model=MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text  # type: ignore[union-attr]
