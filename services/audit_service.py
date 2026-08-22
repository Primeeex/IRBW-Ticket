from __future__ import annotations

import logging
from typing import Any, Optional

import discord

from database.database import Database
from utils.formatting import make_audit_embed

logger = logging.getLogger("ticket_bot.audit")


class AuditService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._bot: Optional[Any] = None
        self._config_service: Optional[Any] = None

    def set_refs(self, bot: Any, config_service: Any) -> None:
        self._bot = bot
        self._config_service = config_service

    async def log(
        self,
        action: str,
        actor_id: int,
        actor_name: str,
        target_id: Optional[int] = None,
        target_name: str = "",
        ticket_id: Optional[str] = None,
        category: Optional[str] = None,
        channel_id: Optional[int] = None,
        details: str = "",
    ) -> None:
        await self.db.add_audit_log(
            action=action,
            actor_id=actor_id,
            actor_name=actor_name,
            target_id=target_id,
            target_name=target_name,
            ticket_id=ticket_id,
            category=category,
            channel_id=channel_id,
            details=details,
        )
        logger.info(
            "Audit: %s by %s (%d) | ticket=%s category=%s | %s",
            action,
            actor_name,
            actor_id,
            ticket_id or "N/A",
            category or "N/A",
            details,
        )
        await self._send_to_channel(action, actor_name, ticket_id, category, details)

    async def _send_to_channel(
        self,
        action: str,
        actor_name: str,
        ticket_id: Optional[str] = None,
        category: Optional[str] = None,
        details: str = "",
    ) -> None:
        if not self._config_service or not self._bot:
            return
        audit_config = self._config_service.get_audit_log()
        if not audit_config.get("enabled"):
            return
        channel_id = audit_config.get("channel_id")
        if not channel_id:
            return
        guild_id = self._config_service.get_guild_id()
        guild = self._bot.get_guild(guild_id) if guild_id else None
        if not guild:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        await self.send_to_channel(channel, action, actor_name, ticket_id, category, details)

    async def send_to_channel(
        self,
        channel: Optional[discord.TextChannel],
        action: str,
        actor_name: str,
        ticket_id: Optional[str] = None,
        category: Optional[str] = None,
        details: str = "",
    ) -> None:
        if not channel:
            return
        color_map = {
            "TICKET_CREATED": 5814783,
            "TICKET_OPENED": 3066993,
            "TICKET_CLAIMED": 10181046,
            "TICKET_UNCLAIMED": 16776960,
            "TICKET_OVERRIDE_CLAIM": 16746496,
            "TICKET_RESPONDED": 3066993,
            "TICKET_CLOSED": 8487426,
            "TICKET_REOPENED": 3066993,
            "TICKET_DELETED": 15158332,
            "TICKET_ARCHIVED": 5814783,
            "USER_ADDED": 3066993,
            "ROLE_ADDED": 3066993,
            "USER_BANNED": 15158332,
            "USER_UNBANNED": 3066993,
            "TRANSCRIPT_GENERATED": 5814783,
            "PERMISSION_CHANGED": 16776960,
            "CONFIG_RELOADED": 3066993,
            "PANEL_DEPLOYED": 3066993,
            "CONFIG_CHANGED": 16776960,
        }
        color = color_map.get(action, 5814783)
        embed = make_audit_embed(
            action=action,
            actor_name=actor_name,
            ticket_id=ticket_id,
            category=category,
            details=details,
            color=color,
        )
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error("Failed to send audit log to channel: %s", e)

    async def get_logs(
        self,
        ticket_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await self.db.get_audit_logs(ticket_id=ticket_id, action=action, limit=limit)
