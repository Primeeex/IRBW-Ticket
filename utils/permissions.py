from __future__ import annotations

from typing import Any, Optional

import discord


PERMISSION_KEYS = [
    "ticket_create",
    "ticket_view_open",
    "ticket_view_closed",
    "ticket_respond",
    "ticket_claim",
    "ticket_unclaim",
    "ticket_add_user",
    "ticket_add_role",
    "ticket_delete",
    "ticket_close",
    "ticket_reopen",
    "ticket_transcript",
    "ticket_ban",
    "ticket_move",
    "ticket_purge",
    "ticket_purge_all",
    "ticket.helper",
    "ticket.moderator",
    "ticket.admin",
    "ticket.manager",
    "ticket.default",
    "stats",
    "adminstats",
    "adminhelp",
    "commands",
    "config",
    "reload",
    "permission_list",
    "permission_add",
    "permission_remove",
]

ROLE_PRESETS: dict[str, list[str]] = {
    "ticket.helper": [
        "ticket_view_open",
        "ticket_respond",
        "ticket_claim",
        "ticket_close",
    ],
    "ticket.moderator": [
        "ticket_view_open",
        "ticket_respond",
        "ticket_claim",
        "ticket_add_user",
        "ticket_close",
        "ticket_transcript",
        "ticket_ban",
    ],
    "ticket.admin": [
        "ticket_view_open",
        "ticket_respond",
        "ticket_claim",
        "ticket_unclaim",
        "ticket_add_user",
        "ticket_add_role",
        "ticket_delete",
        "ticket_close",
        "ticket_reopen",
        "ticket_transcript",
        "ticket_ban",
        "ticket_move",
        "adminstats",
    ],
    "ticket.manager": [
        "ticket_view_open",
        "ticket_respond",
        "ticket_claim",
        "ticket_unclaim",
        "ticket_add_user",
        "ticket_add_role",
        "ticket_delete",
        "ticket_close",
        "ticket_reopen",
        "ticket_transcript",
        "ticket_ban",
        "ticket_move",
        "adminstats",
        "commands",
        "permission_list",
    ],
    "ticket.default": [
        "ticket_create",
    ],
}

PERMISSION_DESCRIPTIONS: dict[str, str] = {
    "ticket_create": "Create a new support ticket",
    "ticket_view_open": "View open/active ticket channels",
    "ticket_view_closed": "View closed ticket channels",
    "ticket_respond": "Respond to tickets and send DM responses",
    "ticket_claim": "Claim a ticket for yourself",
    "ticket_unclaim": "Unclaim a ticket you have claimed",
    "ticket_add_user": "Add a user to a ticket channel",
    "ticket_add_role": "Add a role to a ticket channel",
    "ticket_delete": "Delete a ticket permanently",
    "ticket_close": "Close an open ticket",
    "ticket_reopen": "Reopen a closed ticket",
    "ticket_transcript": "Generate a transcript for a ticket",
    "ticket_ban": "Ban/unban users from creating tickets",
    "ticket_move": "Move a ticket to a different category",
    "ticket_purge": "Delete all tickets (root role required)",
    "ticket_purge_all": "Delete the entire database (root role required)",
    "ticket.helper": "Helper preset: view_open, respond, claim, close",
    "ticket.moderator": "Moderator preset: + view_closed, add_user, transcript, ban",
    "ticket.admin": "Admin preset: + unclaim, override, add_role, delete, reopen, move, adminstats",
    "ticket.manager": "Manager preset: + commands, permission_list, move",
    "ticket.default": "Default preset: ticket_create",
    "stats": "View your personal ticket statistics",
    "adminstats": "View administrator statistics dashboard",
    "adminhelp": "View admin help documentation",
    "commands": "View all available bot commands",
    "config": "View or modify bot configuration",
    "reload": "Hot-reload bot configuration",
    "permission_list": "List all configured permissions",
    "permission_add": "Add a permission role",
    "permission_remove": "Remove a permission role",
}


def get_preset_keys(preset: str) -> list[str]:
    """Return the individual permission keys for a preset, or empty list if not a preset."""
    return ROLE_PRESETS.get(preset, [])


def check_permission(
    member: discord.Member,
    permission_key: str,
    category: str,
    db_permissions: list[dict[str, Any]],
    guild_owner_id: int,
) -> bool:
    if member.id == guild_owner_id:
        return True

    if member.guild_permissions.administrator:
        admin_bypass_keys = [
            "permission_add",
            "permission_remove",
            "config",
            "reload",
            "adminstats",
            "adminhelp",
        ]
        if permission_key in admin_bypass_keys:
            return True

    global_role_ids = []
    category_role_ids = []

    for p in db_permissions:
        if p["permission_key"] == permission_key:
            if p["category"] == "":
                global_role_ids.append(p["role_id"])
            elif p["category"] == category:
                category_role_ids.append(p["role_id"])

    member_role_ids = {r.id for r in member.roles}

    if member_role_ids & set(category_role_ids):
        return True
    if member_role_ids & set(global_role_ids):
        return True

    return False
