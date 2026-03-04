from __future__ import annotations

import json
import requests
from typing import Iterator


class OllamaLLM:
    def __init__(self, model: str, system_prompt: str, host: str = "http://localhost:11434", timeout: float = 60.0):
        self.model = model
        self.system_prompt = system_prompt
        self.host = host.rstrip("/")
        self.timeout = timeout

    def stream_chat(self, user_text: str) -> Iterator[str]:
        payload = {
            "model": self.model,
            "stream": True,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_text},
            ],
        }
        try:
            with requests.post(self.host + "/api/chat", json=payload, stream=True, timeout=self.timeout) as r:
                r.raise_for_status()
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        j = json.loads(line)
                    except Exception:
                        continue
                    msg = j.get("message", {}) or {}
                    chunk = msg.get("content", "")
                    if chunk:
                        yield chunk
        except Exception as e:
            yield f"\n[LLM ERROR] {e}\n"
