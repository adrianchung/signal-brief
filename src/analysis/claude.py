import anthropic

MODEL = "claude-sonnet-4-6"

PROMPT_TEMPLATE = """\
You are a senior engineer reviewing today's Hacker News signal for a busy technical lead.

Below are {n} stories from the past 12 hours that matched keywords: {keywords}.

Your job:
1. Identify the 1 overarching theme (if any) connecting the top stories.
2. Select up to 5 stories worth reading — prioritize substance over hype.
3. For each, write ONE sentence: what it is and why it matters (or why it's hype).
4. End with a 1-sentence "bottom line" on what's actually shifting today.

Be direct. Cut noise. Flag hype explicitly. No filler phrases.

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
