import httpx


class NtfyDeliverer:
    def __init__(self, topic: str, base_url: str) -> None:
        self.topic = topic
        self.base_url = base_url.rstrip("/")

    def send(self, brief: str) -> None:
        url = f"{self.base_url}/{self.topic}"
        headers = {
            "Title": "HN Signal Brief",
            "Content-Type": "text/plain",
        }
        response = httpx.post(url, content=brief.encode(), headers=headers, timeout=10)
        response.raise_for_status()
