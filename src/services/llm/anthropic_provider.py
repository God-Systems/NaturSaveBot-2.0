from __future__ import annotations

from inspect import isawaitable
from typing import Any

from src.config import Settings


class AnthropicProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.api_key = settings.secret_value(settings.anthropic_api_key)
        self._client_instance = None

    def _client(self):
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is empty")
        from anthropic import AsyncAnthropic

        if self._client_instance is None:
            self._client_instance = AsyncAnthropic(api_key=self.api_key)
        return self._client_instance

    async def generate_text(self, prompt: str, *, system: str = "", max_tokens: int = 700) -> str:
        client = self._client()
        kwargs: dict[str, Any] = {
            "model": self.settings.anthropic_model,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        response = await client.messages.create(
            **kwargs,
        )
        parts = []
        for item in response.content:
            if getattr(item, "type", None) == "text":
                parts.append(getattr(item, "text", ""))
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return "\n".join(part for part in parts if part)

    async def transcribe(self, file_path: str) -> str:
        raise RuntimeError("Anthropic transcription is not implemented in this MVP; use OpenAI Whisper")

    async def close(self) -> None:
        if self._client_instance is None:
            return
        close = getattr(self._client_instance, "close", None)
        if close is not None:
            result = close()
            if isawaitable(result):
                await result
        self._client_instance = None
