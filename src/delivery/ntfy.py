import re
import httpx

# Matches markdown links: [label](url)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^\)]+)\)")


def _extract_story_actions(brief: str, max_actions: int = 3) -> str:
    """
    Return an Ntfy Actions header value with one 'view' button per top story URL
    found in the brief (markdown link format), capped at *max_actions*.

    Example result:
        view, Story A, https://example.com; view, Story B, https://hn.com/...
    """
    seen: set[str] = set()
    actions: list[str] = []
    for label, url in _MD_LINK_RE.findall(brief):
        if url not in seen:
            seen.add(url)
            # Ntfy action labels must not contain commas or semicolons
            safe_label = label.replace(",", "").replace(";", "")[:50]
            actions.append(f"view, {safe_label}, {url}")
        if len(actions) >= max_actions:
            break
    return "; ".join(actions)


class NtfyDeliverer:
    def __init__(self, topic: str, base_url: str, priority: int = 3) -> None:
        self.topic = topic
        self.base_url = base_url.rstrip("/")
        self.priority = priority

    def send(self, brief: str) -> None:
        url = f"{self.base_url}/{self.topic}"
        headers = {
            "Title": "HN Signal Brief",
            "Priority": str(self.priority),
            "Markdown": "yes",
            "Tags": "newspaper",
        }
        actions = _extract_story_actions(brief)
        if actions:
            headers["Actions"] = actions
        response = httpx.post(url, content=brief.encode(), headers=headers, timeout=10)
        response.raise_for_status()
