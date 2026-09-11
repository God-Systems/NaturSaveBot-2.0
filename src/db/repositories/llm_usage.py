from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import LLMUsageDaily


async def consume_llm_request(session: AsyncSession, *, day: date, limit: int) -> None:
    usage = await session.get(LLMUsageDaily, day)
    if usage is None:
        session.add(LLMUsageDaily(day=day, count=1))
        await session.flush()
        return
    if usage.count >= limit:
        raise RuntimeError("Daily LLM limit reached")
    usage.count += 1
    await session.flush()
