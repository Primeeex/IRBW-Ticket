from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import discord

logger = logging.getLogger("ticket_bot.helpers")

_MAX_RETRIES = 5
_MAX_WAIT_SECONDS = 120
_MIN_EDIT_GAP = 1.5
_edit_lock: asyncio.Lock = asyncio.Lock()
_last_edit_time: float = 0.0


def _is_rate_limited(exc: Exception) -> bool:
    if isinstance(exc, discord.RateLimited):
        return True
    if isinstance(exc, discord.HTTPException) and exc.status == 429:
        return True
    return False


def _get_retry_after(exc: Exception) -> float:
    if isinstance(exc, discord.RateLimited):
        return min(getattr(exc, "retry_after", 10), _MAX_WAIT_SECONDS)
    return 10.0


async def safe_channel_edit(
    channel: discord.abc.Connectable,
    **kwargs: Any,
) -> bool:
    """Edit a channel with automatic retry on rate-limit (429).

    Enforces a minimum gap between successive edits globally to avoid
    Discord's aggressive rate-limit penalties. Uses exponential backoff.
    Lock is released during sleep so other tasks aren't blocked.

    Returns True on success, False if all retries were exhausted.
    """
    global _last_edit_time

    elapsed = time.monotonic() - _last_edit_time
    if elapsed < _MIN_EDIT_GAP:
        await asyncio.sleep(_MIN_EDIT_GAP - elapsed)

    for attempt in range(1, _MAX_RETRIES + 1):
        async with _edit_lock:
            try:
                await channel.edit(**kwargs)  # type: ignore[union-attr]
                _last_edit_time = time.monotonic()
                return True
            except discord.RateLimited as e:
                base_wait = min(getattr(e, "retry_after", 10), _MAX_WAIT_SECONDS)
                wait = min(base_wait * (2 ** (attempt - 1)), _MAX_WAIT_SECONDS)
                logger.warning(
                    "Rate-limited editing channel %s (attempt %d/%d), waiting %.1fs",
                    getattr(channel, "id", "?"),
                    attempt,
                    _MAX_RETRIES,
                    wait,
                )
            except discord.HTTPException as e:
                if e.status == 429:
                    wait = min(10.0 * (2 ** (attempt - 1)), _MAX_WAIT_SECONDS)
                    logger.warning(
                        "Rate-limited (HTTPException 429) editing channel %s (attempt %d/%d), waiting %.1fs",
                        getattr(channel, "id", "?"),
                        attempt,
                        _MAX_RETRIES,
                        wait,
                    )
                else:
                    logger.error(
                        "Failed to edit channel %s (HTTP %d): %s",
                        getattr(channel, "id", "?"),
                        e.status,
                        e,
                    )
                    return False
            except Exception as e:
                logger.error("Failed to edit channel %s: %s", getattr(channel, "id", "?"), e)
                return False
        await asyncio.sleep(wait)

    logger.error("Exhausted retries editing channel %s", getattr(channel, "id", "?"))
    return False
