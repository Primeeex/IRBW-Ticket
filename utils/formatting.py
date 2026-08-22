from __future__ import annotations

import datetime
from typing import Any, Optional

import discord

from utils import timezone

_messages = None

def _get_msg():
    global _messages
    if _messages is None:
        from utils.messages import MessageService
        _messages = MessageService()
    return _messages


def format_timestamp(iso_string: Optional[str], style: str = "F") -> str:
    if not iso_string:
        return "N/A"
    try:
        dt = datetime.datetime.fromisoformat(iso_string)
        return f"<t:{int(dt.timestamp())}:{style}>"
    except (ValueError, TypeError):
        return iso_string


def ticket_status_emoji(status: str) -> str:
    mapping = {
        "PENDING": "\u23f3",
        "OPEN": "\ud83d\udce2",
        "CLAIMED": "\ud83d\udc64",
        "RESPONDED": "\u2705",
        "CLOSED": "\ud83d\udd12",
        "DELETED": "\ud83d\uddd1\ufe0f",
    }
    return mapping.get(status, "\u2753")


def ticket_status_color(status: str, config_ui: dict[str, Any]) -> int:
    color_map = {
        "PENDING": config_ui.get("color_pending", 16776960),
        "OPEN": config_ui.get("color_open", 3066993),
        "CLAIMED": config_ui.get("color_claimed", 10181046),
        "RESPONDED": config_ui.get("color_success", 3066993),
        "CLOSED": config_ui.get("color_closed", 8487426),
        "DELETED": config_ui.get("color_deleted", 15158332),
    }
    return color_map.get(status, 5814783)


def truncate(text: str, max_length: int = 1024) -> str:
    if text is None:
        return ""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_duration(minutes: float) -> str:
    if minutes < 1:
        return "<1 minute"
    if minutes < 60:
        return f"{int(minutes)} minute{'s' if int(minutes) != 1 else ''}"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f} hour{'s' if hours != 1.0 else ''}"
    days = hours / 24
    return f"{days:.1f} day{'s' if days != 1.0 else ''}"


def make_ticket_embed(
    ticket: dict[str, Any],
    config_ui: dict[str, Any],
    *,
    title: Optional[str] = None,
    description: Optional[str] = None,
    claimed_by: Optional[str] = None,
) -> discord.Embed:
    msg = _get_msg()
    status = ticket["status"]
    color = ticket_status_color(status, config_ui)
    emoji = ticket_status_emoji(status)

    embed_title = title or f"{emoji} {ticket['ticket_id']}"
    embed_desc = description or ""

    embed = discord.Embed(title=embed_title, color=color, description=embed_desc)
    embed.add_field(name=msg.get("formatting.ticket_id"), value=ticket["ticket_id"], inline=True)
    embed.add_field(name=msg.get("formatting.user"), value=f"<@{ticket['user_id']}>", inline=True)
    embed.add_field(name=msg.get("formatting.category"), value=ticket["category"].title(), inline=True)
    embed.add_field(name=msg.get("formatting.status"), value=f"{emoji} {status}", inline=True)
    embed.add_field(name=msg.get("formatting.created"), value=format_timestamp(ticket.get("created_at")), inline=True)

    if ticket.get("opened_at"):
        embed.add_field(name=msg.get("formatting.opened"), value=format_timestamp(ticket["opened_at"]), inline=True)
    if ticket.get("responded_at"):
        embed.add_field(name=msg.get("formatting.responded"), value=format_timestamp(ticket["responded_at"]), inline=True)
    if ticket.get("closed_at"):
        embed.add_field(name=msg.get("formatting.closed"), value=format_timestamp(ticket["closed_at"]), inline=True)

    if claimed_by:
        embed.add_field(name=msg.get("formatting.claimed_by"), value=claimed_by, inline=True)
    elif ticket.get("claimed_by"):
        embed.add_field(name=msg.get("formatting.claimed_by"), value=f"<@{ticket['claimed_by']}>", inline=True)

    custom_fields = ticket.get("custom_fields", {})
    for key, val in custom_fields.items():
        if val:
            label = key.replace("_", " ").title()
            embed.add_field(name=label, value=truncate(str(val), 1024), inline=False)

    if ticket.get("response"):
        embed.add_field(
            name=msg.get("formatting.staff_response"),
            value=truncate(ticket["response"], 1024),
            inline=False,
        )

    return embed


def make_pending_embed(
    ticket: dict[str, Any],
    config_ui: dict[str, Any],
) -> discord.Embed:
    msg = _get_msg()
    embed = discord.Embed(
        title=msg.get("formatting.pending_title"),
        color=config_ui.get("color_pending", 16776960),
    )
    embed.add_field(name=msg.get("formatting.user"), value=f"<@{ticket['user_id']}>", inline=True)
    embed.add_field(name=msg.get("formatting.category"), value=ticket["category"].title(), inline=True)
    embed.add_field(name=msg.get("formatting.ticket_id"), value=ticket["ticket_id"], inline=True)
    embed.add_field(name=msg.get("formatting.status"), value="\u23f3 Pending", inline=True)
    custom_fields = ticket.get("custom_fields", {})
    for key, val in custom_fields.items():
        if val:
            label = key.replace("_", " ").title()
            embed.add_field(name=label, value=truncate(str(val), 1024), inline=False)
    embed.set_footer(text=msg.get("formatting.pending_footer"))
    return embed


def make_audit_embed(
    action: str,
    actor_name: str,
    ticket_id: Optional[str] = None,
    category: Optional[str] = None,
    details: str = "",
    color: int = 5814783,
) -> discord.Embed:
    msg = _get_msg()
    embed = discord.Embed(
        title=f"Audit: {action}",
        color=color,
    )
    embed.add_field(name=msg.get("formatting.action"), value=action, inline=True)
    embed.add_field(name=msg.get("formatting.actor"), value=actor_name, inline=True)
    if ticket_id:
        embed.add_field(name=msg.get("formatting.ticket"), value=ticket_id, inline=True)
    if category:
        embed.add_field(name=msg.get("formatting.category"), value=category.title(), inline=True)
    if details:
        embed.add_field(name=msg.get("formatting.details"), value=truncate(details, 1024), inline=False)
    embed.set_footer(text=msg.get("formatting.audit_footer", timestamp=timezone.now().strftime('%Y-%m-%d %H:%M %Z')))
    return embed


def make_archive_embed(
    ticket: dict[str, Any],
    config_ui: dict[str, Any],
    staff_name: str,
    response_text: str,
) -> discord.Embed:
    msg = _get_msg()
    embed = discord.Embed(
        title=f"Ticket Resolved - {ticket['ticket_id']}",
        color=config_ui.get("color_closed", 8487426),
    )
    embed.add_field(name=msg.get("formatting.ticket_id"), value=ticket["ticket_id"], inline=True)
    embed.add_field(name=msg.get("formatting.user"), value=f"<@{ticket['user_id']}>", inline=True)
    embed.add_field(name=msg.get("formatting.category"), value=ticket["category"].title(), inline=True)
    embed.add_field(name=msg.get("formatting.staff"), value=staff_name, inline=True)
    embed.add_field(name=msg.get("formatting.status"), value="\U0001f512 Closed", inline=True)
    custom_fields = ticket.get("custom_fields", {})
    for key, val in custom_fields.items():
        if val:
            label = key.replace("_", " ").title()
            embed.add_field(name=label, value=truncate(str(val), 1024), inline=False)
    embed.add_field(
        name=msg.get("formatting.staff_response"),
        value=truncate(response_text, 1024),
        inline=False,
    )
    if ticket.get("created_at"):
        embed.add_field(name=msg.get("formatting.opened"), value=format_timestamp(ticket["created_at"]), inline=True)
    embed.add_field(name=msg.get("formatting.closed"), value=f"<t:{int(timezone.now().timestamp())}:F>", inline=True)
    embed.set_footer(text=msg.get("formatting.archive_footer"))
    return embed
