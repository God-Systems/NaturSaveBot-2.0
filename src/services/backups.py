from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.config import Settings


logger = logging.getLogger(__name__)


class DatabaseBackupService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def create_backup(self) -> Path | None:
        if not self.settings.backup_enabled:
            return None
        database_path = _sqlite_path(self.settings.database_url)
        if database_path is None:
            logger.warning("database backup is supported only for SQLite")
            return None
        self.settings.backup_dir.mkdir(parents=True, exist_ok=True)
        target = self.settings.backup_dir / f"app-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.db"
        await asyncio.to_thread(_copy_sqlite, database_path, target)
        await asyncio.to_thread(_prune_backups, self.settings.backup_dir, self.settings.backup_retention_days)
        logger.info("database backup created path=%s", target)
        return target


def _sqlite_path(database_url: str) -> Path | None:
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        return None
    path = database_url.removeprefix(prefix)
    return None if path == ":memory:" else Path(path)


def _copy_sqlite(source: Path, target: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    with sqlite3.connect(source) as source_db, sqlite3.connect(target) as target_db:
        source_db.backup(target_db)


def _prune_backups(directory: Path, retention_days: int) -> None:
    cutoff = datetime.now(UTC) - timedelta(days=max(retention_days, 1))
    for path in directory.glob("app-*.db"):
        if datetime.fromtimestamp(path.stat().st_mtime, UTC) < cutoff:
            path.unlink()
