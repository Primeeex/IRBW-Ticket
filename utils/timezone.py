from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

_config_tz: ZoneInfo | None = None


def init(config: dict) -> None:
    """Initialize timezone from config. Call once at bot startup."""
    global _config_tz
    tz_name = config.get("timezone", "UTC")
    try:
        _config_tz = ZoneInfo(tz_name)
    except Exception:
        _config_tz = ZoneInfo("UTC")


def now() -> datetime.datetime:
    """Return current time in the configured timezone (timezone-aware)."""
    if _config_tz is None:
        return datetime.datetime.now(datetime.timezone.utc)
    return datetime.datetime.now(_config_tz)
