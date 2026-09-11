from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.crypto import decrypt_secret, encrypt_secret
from src.db.models import AppSetting, SecretValue, TelegramCredential


DEFAULT_SETTINGS: dict[str, Any] = {
    "llm_provider": "none",
    "telegram_mode": "business",
    "save_mode_enabled": True,
    "save_mode_scope": "private",
    "save_media_enabled": True,
    "save_mode_notify_deletes": True,
    "save_mode_notify_edits": True,
    "save_media_max_mb": 50,
    "auto_reply_enabled": False,
    "auto_reply_mode": "static",
    "auto_reply_text": "Сейчас не могу ответить, напишу позже.",
    "auto_reply_cooldown_seconds": 900,
    "auto_reply_require_whitelist": False,
    "digest_enabled": False,
    "digest_time": "09:00",
    "timezone": "Europe/Moscow",
}


def _runtime_defaults() -> dict[str, Any]:
    from src.config import get_settings

    settings = get_settings()
    return {
        "llm_provider": settings.llm_provider,
        "telegram_mode": settings.telegram_mode,
        "save_mode_enabled": settings.save_mode_enabled,
        "save_mode_scope": settings.save_mode_scope,
        "save_media_enabled": settings.save_media_enabled,
        "save_mode_notify_deletes": settings.effective_notify_deletes,
        "save_mode_notify_edits": settings.effective_notify_edits,
        "save_media_max_mb": settings.effective_save_media_max_mb,
        "auto_reply_enabled": settings.auto_reply_enabled,
        "auto_reply_mode": settings.auto_reply_mode,
        "auto_reply_text": settings.auto_reply_text,
        "auto_reply_cooldown_seconds": settings.auto_reply_cooldown_seconds,
        "auto_reply_require_whitelist": settings.auto_reply_require_whitelist,
        "digest_enabled": settings.digest_enabled,
        "digest_time": settings.digest_time,
        "timezone": settings.timezone,
    }


async def get_setting(session: AsyncSession, key: str, default: Any = None) -> Any:
    row = await session.get(AppSetting, key)
    if row is None:
        return DEFAULT_SETTINGS.get(key, default)
    try:
        return json.loads(row.value)
    except json.JSONDecodeError:
        return row.value


async def set_setting(session: AsyncSession, key: str, value: Any) -> None:
    row = await session.get(AppSetting, key)
    payload = json.dumps(value, ensure_ascii=False)
    if row is None:
        session.add(AppSetting(key=key, value=payload))
    else:
        row.value = payload
    await session.flush()


async def get_all_settings(session: AsyncSession) -> dict[str, Any]:
    result = await session.execute(select(AppSetting))
    values = dict(DEFAULT_SETTINGS)
    values.update(_runtime_defaults())
    for row in result.scalars():
        try:
            values[row.key] = json.loads(row.value)
        except json.JSONDecodeError:
            values[row.key] = row.value
    return values


async def get_persisted_settings(session: AsyncSession) -> dict[str, Any]:
    result = await session.execute(select(AppSetting))
    values: dict[str, Any] = {}
    for row in result.scalars():
        try:
            values[row.key] = json.loads(row.value)
        except json.JSONDecodeError:
            values[row.key] = row.value
    return values


async def save_secret(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(SecretValue, key)
    encrypted = encrypt_secret(value)
    if row is None:
        session.add(SecretValue(key=key, value_enc=encrypted))
    else:
        row.value_enc = encrypted
    await session.flush()


async def load_secret(session: AsyncSession, key: str) -> str:
    row = await session.get(SecretValue, key)
    return decrypt_secret(row.value_enc) if row else ""


async def save_telegram_credentials(session: AsyncSession, api_id: int, api_hash: str, session_string: str) -> None:
    row = await session.get(TelegramCredential, 1)
    if row is None:
        session.add(
            TelegramCredential(
                id=1,
                api_id=api_id,
                api_hash_enc=encrypt_secret(api_hash),
                session_string_enc=encrypt_secret(session_string),
            )
        )
    else:
        row.api_id = api_id
        row.api_hash_enc = encrypt_secret(api_hash)
        row.session_string_enc = encrypt_secret(session_string)
    await session.flush()


async def load_telegram_credentials(session: AsyncSession) -> tuple[int, str, str] | None:
    row = await session.get(TelegramCredential, 1)
    if row is None:
        return None
    return row.api_id, decrypt_secret(row.api_hash_enc), decrypt_secret(row.session_string_enc)


async def delete_telegram_credentials(session: AsyncSession) -> None:
    row = await session.get(TelegramCredential, 1)
    if row is not None:
        await session.delete(row)
        await session.flush()
