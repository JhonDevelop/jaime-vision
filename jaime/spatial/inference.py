"""Cliente local OpenAI-compatible. URL é explicitamente configurada; sem fallback cloud."""
from __future__ import annotations
import json
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

class LocalInference:
    def __init__(self, base_url: str, model: str, allowed_hosts: set[str] | None = None):
        parsed = urlsplit(base_url)
        hosts = allowed_hosts or {"localhost", "127.0.0.1", "host.openshell.internal", "inference.local"}
        if parsed.scheme != "http" or parsed.hostname not in hosts or not model:
            raise ValueError("explicit trusted local endpoint and model required")
        self.base_url = base_url.rstrip("/")
        self.model = model

    def chat(self, messages: list[dict], timeout: float = 20) -> str:
        payload = json.dumps({"model": self.model, "messages": messages,
                              "stream": False, "temperature": 0.1}).encode()
        req = Request(self.base_url + "/chat/completions", data=payload,
                      headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(req, timeout=timeout) as response:
            data = json.load(response)
        return data["choices"][0]["message"]["content"]
