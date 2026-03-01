import httpx


class SlackDeliverer:
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, brief: str) -> None:
        payload = {"text": f"*HN Signal Brief*\n{brief}"}
        response = httpx.post(self.webhook_url, json=payload, timeout=10)
        response.raise_for_status()
