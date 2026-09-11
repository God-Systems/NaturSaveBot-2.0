from __future__ import annotations

import logging

from src.config import Settings


logger = logging.getLogger(__name__)


def init_error_tracking(settings: Settings) -> None:
    dsn = settings.secret_value(settings.sentry_dsn)
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        logger.warning("SENTRY_DSN is set, but sentry-sdk is not installed")
        return
    sentry_sdk.init(dsn=dsn, traces_sample_rate=0.0, send_default_pii=False)
