from __future__ import annotations

import json
import re
from inspect import isawaitable
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.config import Settings, get_settings
from src.db.repositories.llm_usage import consume_llm_request
from src.db.session import get_session
from src.services.llm.anthropic_provider import AnthropicProvider
from src.services.llm.base import LLMProvider
from src.services.llm.gemini_provider import GeminiProvider
from src.services.llm.openai_provider import OpenAIProvider
from src.utils.text import chunk_text, clean_text


INTENT_SYSTEM = """You route Russian Telegram assistant commands.
Return strict JSON only. Allowed intents:
send_message, search_messages, summarize_chat, catchup_chat, create_reminder,
extract_tasks, digest, business_status, health, settings_change, unknown.
For send_message include recipient and text. For create_reminder include text.
Prefer business_status for status/state requests and health for technical checks.
Never invent contacts."""


@dataclass(slots=True)
class LLMUsage:
    day: date
    count: int = 0


class LLMRouter:
    def __init__(self, settings: Settings | None = None, provider: LLMProvider | None = None) -> None:
        self.settings = settings or get_settings()
        self._provider_override = provider
        self._usage = LLMUsage(day=date.today())
        self._providers: dict[str, LLMProvider] = {}

    def _provider(self) -> LLMProvider:
        if self._provider_override is not None:
            return self._provider_override
        provider_name = self.settings.llm_provider
        if provider_name == "none":
            raise RuntimeError("LLM is disabled; configure a provider to enable it")
        if provider_name not in self._providers:
            if provider_name == "gemini":
                self._providers[provider_name] = GeminiProvider(self.settings)
            elif provider_name == "anthropic":
                self._providers[provider_name] = AnthropicProvider(self.settings)
            else:
                self._providers[provider_name] = OpenAIProvider(self.settings)
        return self._providers[provider_name]

    async def _consume(self) -> None:
        if self.settings.llm_provider == "none" and self._provider_override is None:
            raise RuntimeError("LLM is disabled")
        if self._provider_override is None:
            async with get_session() as session:
                await consume_llm_request(session, day=date.today(), limit=self.settings.daily_llm_limit)
                await session.commit()
            return
        today = date.today()
        if self._usage.day != today:
            self._usage = LLMUsage(day=today)
        if self._usage.count >= self.settings.daily_llm_limit:
            raise RuntimeError("Daily LLM limit reached")
        self._usage.count += 1

    def _trim(self, text: str) -> str:
        return text[: self.settings.max_llm_input_chars]

    async def generate_text(self, prompt: str, *, system: str = "", max_tokens: int = 700) -> str:
        await self._consume()
        return await self._provider().generate_text(self._trim(prompt), system=system, max_tokens=max_tokens)

    async def summarize(self, messages: list[str]) -> str:
        limited = messages[-self.settings.max_context_messages :]
        chunks = chunk_text(limited, self.settings.max_llm_input_chars)
        partials: list[str] = []
        for chunk in chunks[:4]:
            partials.append(
                await self.generate_text(
                    chunk,
                    system="Кратко суммируй переписку: темы, решения, вопросы, что требует ответа. Без лишних вводных.",
                    max_tokens=500,
                )
            )
        if len(partials) == 1:
            return partials[0][: self.settings.max_summary_chars]
        merged = await self.generate_text(
            "\n\n".join(partials),
            system="Сожми несколько частичных выжимок в одну короткую Telegram-сводку.",
            max_tokens=700,
        )
        return merged[: self.settings.max_summary_chars]

    async def extract_tasks(self, messages: list[str]) -> list[dict[str, Any]]:
        prompt = "\n".join(messages[-self.settings.max_context_messages :])
        raw = await self.generate_text(
            prompt,
            system=(
                "Извлеки задачи, обещания и дедлайны из сообщений. "
                "Верни JSON array объектов: title, actor, deadline, source."
            ),
            max_tokens=700,
        )
        try:
            parsed = json.loads(_strip_fence(raw))
            return parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return []

    async def classify_intent(self, text: str) -> dict[str, Any]:
        heuristic = heuristic_intent(text)
        if heuristic["intent"] != "unknown":
            return heuristic
        try:
            raw = await self.generate_text(text, system=INTENT_SYSTEM, max_tokens=300)
            parsed = json.loads(_strip_fence(raw))
            return parsed if isinstance(parsed, dict) else {"intent": "unknown"}
        except Exception:
            return {"intent": "unknown"}

    async def transcribe(self, file_path: str) -> str:
        await self._consume()
        return await self._provider().transcribe(file_path)

    async def shutdown(self) -> None:
        for provider in self._providers.values():
            close = getattr(provider, "close", None)
            if close is None:
                continue
            result = close()
            if isawaitable(result):
                await result

    @property
    def enabled(self) -> bool:
        return self._provider_override is not None or self.settings.llm_provider != "none"


def _strip_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.I).strip()
        text = re.sub(r"```$", "", text).strip()
    return text


def heuristic_intent(text: str) -> dict[str, Any]:
    value = clean_text(text)
    lowered = value.lower()

    send_match = re.match(
        r"^(напиши|скажи|отправь|ответь)\s+([^,:|]+?)(?:,|:|\||\s+что\s+)(.+)$",
        value,
        flags=re.I,
    )
    if send_match:
        body = re.sub(r"^что\s+", "", send_match.group(3).strip(), flags=re.I)
        return {"intent": "send_message", "recipient": send_match.group(2).strip(), "text": body}

    if lowered.startswith(("напомни ", "поставь напоминание ", "напоминание ")):
        return {"intent": "create_reminder", "text": value}
    if lowered.startswith(("найди ", "поиск ")):
        return {"intent": "search_messages", "query": re.sub(r"^(найди|поиск)\s+", "", value, flags=re.I)}
    if "выжим" in lowered or "саммари" in lowered or lowered.startswith("summary"):
        return {"intent": "summarize_chat", "chat": value}
    if "где мы остановились" in lowered or "catchup" in lowered:
        return {"intent": "catchup_chat", "chat": value}
    if "задач" in lowered or "что я обещал" in lowered:
        return {"intent": "extract_tasks", "chat": value}
    if "дайджест" in lowered or lowered.startswith("digest"):
        return {"intent": "digest"}
    if "business status" in lowered or "статус" in lowered:
        return {"intent": "business_status"}
    if "health" in lowered or "здоровье" in lowered or "проверка" in lowered:
        return {"intent": "health"}
    if "провайдер" in lowered or "llm" in lowered:
        return {"intent": "settings_change", "text": value}
    return {"intent": "unknown"}
