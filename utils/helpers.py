from __future__ import annotations

import asyncio
import logging
from typing import Any

import discord

logger = logging.getLogger("ticket_bot.helpers")

_MAX_RETRIES = 3
_MAX_WAIT_SECONDS = 120


async def safe_channel_edit(
    channel: discord.abc.Connectable,
    **kwargs: Any,
) -> bool:
    """Edit a channel with automatic retry on rate-limit (429).

    Returns True on success, False if all retries were exhausted.
    """
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            await channel.edit(**kwargs)  # type: ignore[union-attr]
            return True
        except discord.RateLimited as e:
            wait = min(getattr(e, "retry_after", 10), _MAX_WAIT_SECONDS)
            logger.warning(
                "Rate-limited editing channel %s (attempt %d/%d), waiting %.1fs",
                getattr(channel, "id", "?"),
                attempt,
                _MAX_RETRIES,
                wait,
            )
            await asyncio.sleep(wait)
        except Exception as e:
            logger.error("Failed to edit channel %s: %s", getattr(channel, "id", "?"), e)
            return False

    logger.error("Exhausted retries editing channel %s", getattr(channel, "id", "?"))
    return False
