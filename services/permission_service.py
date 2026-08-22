from __future__ import annotations

import logging
from typing import Any

import discord

from database.database import Database
from utils.permissions import check_permission, PERMISSION_KEYS, get_preset_keys

logger = logging.getLogger("ticket_bot.permissions")


class PermissionService:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def check(
        self,
        member: discord.Member,
        permission_key: str,
        category: str,
    ) -> bool:
        db_perms = await self.db.get_all_permissions()
        guild_owner_id = member.guild.owner_id or 0
        return check_permission(
            member=member,
            permission_key=permission_key,
            category=category,
            db_permissions=db_perms,
            guild_owner_id=guild_owner_id,
        )

    def _resolve_preset(self, permission_key: str, custom_presets: list[dict[str, Any]] | None = None) -> list[str]:
        """Resolve a permission key to individual keys. Checks built-in presets first, then custom."""
        builtin = get_preset_keys(permission_key)
        if builtin:
            return builtin
        if custom_presets:
            for cp in custom_presets:
                if cp["name"] == permission_key:
                    return cp.get("permission_keys", [])
        return []

    async def add_permission(self, permission_key: str, category: str, role_id: int) -> int:
        """Add a permission (or preset) for a role. Returns number of individual permissions added."""
        custom_presets = await self.db.get_all_custom_presets()
        preset_keys = self._resolve_preset(permission_key, custom_presets)

        if preset_keys:
            for key in preset_keys:
                await self.db.add_permission(key, category, role_id)
            logger.info("Added preset '%s' (%d permissions) (category=%s) for role %d", permission_key, len(preset_keys), category, role_id)
            return len(preset_keys)

        await self.db.add_permission(permission_key, category, role_id)
        logger.info("Added permission: %s (category=%s) for role %d", permission_key, category, role_id)
        return 1

    async def remove_permission(self, permission_key: str, category: str, role_id: int) -> int:
        """Remove a permission (or preset) for a role. Returns number of individual permissions removed."""
        custom_presets = await self.db.get_all_custom_presets()
        preset_keys = self._resolve_preset(permission_key, custom_presets)

        if preset_keys:
            count = 0
            for key in preset_keys:
                if await self.db.remove_permission(key, category, role_id):
                    count += 1
            logger.info("Removed preset '%s' (%d permissions) (category=%s) for role %d", permission_key, count, category, role_id)
            return count

        result = await self.db.remove_permission(permission_key, category, role_id)
        if result:
            logger.info("Removed permission: %s (category=%s) for role %d", permission_key, category, role_id)
        return 1 if result else 0

    async def get_permissions_for_key(self, permission_key: str, category: str = "") -> list[dict[str, Any]]:
        return await self.db.get_permissions(permission_key, category)

    async def get_all_permissions(self) -> list[dict[str, Any]]:
        return await self.db.get_all_permissions()

    async def get_role_ids_for_permission(self, permission_key: str, category: str = "") -> list[int]:
        return await self.db.get_permission_role_ids(permission_key, category)

    async def create_custom_preset(self, name: str, description: str, permission_keys: list[str]) -> None:
        for key in permission_keys:
            if key not in PERMISSION_KEYS:
                raise ValueError(f"Invalid permission key: {key}")
        await self.db.add_custom_preset(name, description, permission_keys)
        logger.info("Created custom preset '%s' with %d permissions", name, len(permission_keys))

    async def delete_custom_preset(self, name: str) -> bool:
        result = await self.db.remove_custom_preset(name)
        if result:
            logger.info("Deleted custom preset '%s'", name)
        return result

    async def get_custom_preset(self, name: str) -> dict[str, Any] | None:
        return await self.db.get_custom_preset(name)

    async def get_all_custom_presets(self) -> list[dict[str, Any]]:
        return await self.db.get_all_custom_presets()
