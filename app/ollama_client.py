from __future__ import annotations

import json
import urllib.error
import urllib.request


class OllamaClient:
    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def generate(self, model: str, prompt: str, timeout: int = 120, keep_alive: int | str | None = None) -> str:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_ctx": 4096,
            },
        }
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Ollamaに接続できません。Ollamaを起動して、必要なら `ollama pull qwen2.5:0.5b` を実行してください。"
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError("Ollamaの応答がタイムアウトしました。軽いモデルに変えるか、もう一度試してください。") from exc

        text = data.get("response")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Ollamaから有効な返答がありませんでした。")
        return text
