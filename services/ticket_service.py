from __future__ import annotations

import datetime
import logging
from typing import Any, Optional

import discord

from database.database import Database
from utils import timezone
from utils.errors import (
    MaxTicketsReachedError,
    TicketAlreadyClaimedError,
    TicketAlreadyRespondedError,
    InvalidTicketStateError,
    TicketNotFoundError,
    DMFailedError,
)
from utils.messages import MessageService

_msg = MessageService()

logger = logging.getLogger("ticket_bot.ticket")


def _parse_duration(duration_str: str) -> Optional[datetime.timedelta]:
    """Parse a duration string like '3d', '7d', '14d', '30d', 'permanent'."""
    duration_str = duration_str.strip().lower()
    if duration_str in ("permanent", "perm", "forever", "inf"):
        return None
    unit = duration_str[-1]
    try:
        value = int(duration_str[:-1])
    except (ValueError, IndexError):
        return None
    if unit == "d":
        return datetime.timedelta(days=value)
    elif unit == "h":
        return datetime.timedelta(hours=value)
    elif unit == "w":
        return datetime.timedelta(weeks=value)
    elif unit == "m":
        return datetime.timedelta(minutes=value)
    return None


def format_duration_display(td: Optional[datetime.timedelta]) -> str:
    """Format a timedelta into a human-readable string."""
    if td is None:
        return "permanent"
    total_seconds = int(td.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds} second{'s' if total_seconds != 1 else ''}"
    if total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    if total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''}"
    days = total_seconds // 86400
    return f"{days} day{'s' if days != 1 else ''}"


class TicketService:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def create_ticket(
        self,
        category: str,
        prefix: str,
        user_id: int,
        username: str,
        custom_fields: dict[str, str],
    ) -> dict[str, Any]:
        await self.db.get_or_create_user(user_id, username)
        ticket_id = await self.db.get_next_ticket_number(category, prefix)
        internal_id = await self.db.get_total_ticket_count() + 1
        ticket = await self.db.create_ticket(
            ticket_id=ticket_id,
            internal_id=internal_id,
            category=category,
            user_id=user_id,
            custom_fields=custom_fields,
        )
        await self.db.increment_user_ticket_count(user_id)
        logger.info("Created ticket %s for user %d in category %s", ticket_id, user_id, category)
        return ticket

    async def get_ticket(self, ticket_id: str) -> dict[str, Any]:
        ticket = await self.db.get_ticket(ticket_id)
        if not ticket:
            raise TicketNotFoundError(ticket_id)
        return ticket

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[dict[str, Any]]:
        return await self.db.get_ticket_by_channel(channel_id)

    async def get_active_tickets_by_user(self, user_id: int) -> list[dict[str, Any]]:
        return await self.db.get_active_tickets_by_user(user_id)

    async def count_active_tickets(self, user_id: int) -> int:
        return await self.db.count_active_tickets_by_user(user_id)

    async def count_pending_tickets(self, user_id: int, category: str) -> int:
        return await self.db.count_pending_tickets_by_user(user_id, category)

    async def open_ticket(self, ticket_id: str, channel_id: int) -> dict[str, Any]:
        ticket = await self.get_ticket(ticket_id)
        if ticket["status"] != "PENDING":
            raise InvalidTicketStateError(
                f"Cannot open ticket {ticket_id}: current status is {ticket['status']}, expected PENDING."
            )
        await self.db.update_ticket_status(ticket_id, "OPEN")
        await self.db.update_ticket_channel(ticket_id, channel_id)
        return await self.get_ticket(ticket_id)

    async def store_pending_message(self, ticket_id: str, message_id: int) -> None:
        await self.db.update_pending_message_id(ticket_id, message_id)

    async def claim_ticket(self, ticket_id: str, staff_id: int) -> dict[str, Any]:
        ticket = await self.get_ticket(ticket_id)
        if ticket["status"] not in ("OPEN", "PENDING"):
            raise InvalidTicketStateError(
                f"Cannot claim ticket {ticket_id}: current status is {ticket['status']}."
            )
        if ticket.get("claimed_by") and ticket["claimed_by"] != staff_id:
            raise TicketAlreadyClaimedError(ticket["claimed_by"])
        await self.db.update_ticket_claim(ticket_id, staff_id)
        await self.db.add_claim(ticket_id, staff_id, "CLAIM")
        if ticket["status"] == "PENDING":
            await self.db.update_ticket_status(ticket_id, "CLAIMED")
        elif ticket["status"] == "OPEN":
            await self.db.update_ticket_status(ticket_id, "CLAIMED")
        return await self.get_ticket(ticket_id)

    async def unclaim_ticket(self, ticket_id: str, staff_id: int) -> dict[str, Any]:
        ticket = await self.get_ticket(ticket_id)
        if ticket.get("claimed_by") != staff_id:
            raise InvalidTicketStateError("You have not claimed this ticket.")
        await self.db.update_ticket_claim(ticket_id, None)
        await self.db.add_claim(ticket_id, staff_id, "UNCLAIM")
        await self.db.update_ticket_status(ticket_id, "OPEN")
        return await self.get_ticket(ticket_id)

    async def override_claim(self, ticket_id: str, new_staff_id: int) -> dict[str, Any]:
        ticket = await self.get_ticket(ticket_id)
        old_claimer = ticket.get("claimed_by")
        await self.db.update_ticket_claim(ticket_id, new_staff_id)
        await self.db.add_claim(ticket_id, new_staff_id, f"OVERRIDE:{old_claimer}")
        await self.db.update_ticket_status(ticket_id, "CLAIMED")
        return await self.get_ticket(ticket_id)

    async def respond_to_ticket(
        self, ticket_id: str, staff_id: int, response: str
    ) -> dict[str, Any]:
        ticket = await self.get_ticket(ticket_id)
        if ticket["status"] in ("RESPONDED", "CLOSED", "DELETED"):
            raise TicketAlreadyRespondedError()
        await self.db.update_ticket_response(ticket_id, response, staff_id)
        await self.db.add_response(ticket_id, staff_id, response)
        await self.db.update_ticket_status(ticket_id, "RESPONDED")
        return await self.get_ticket(ticket_id)

    async def close_ticket(self, ticket_id: str) -> dict[str, Any]:
        ticket = await self.get_ticket(ticket_id)
        if ticket["status"] in ("CLOSED", "DELETED"):
            raise InvalidTicketStateError(f"Ticket {ticket_id} is already {ticket['status']}.")
        await self.db.update_ticket_status(ticket_id, "CLOSED")
        return await self.get_ticket(ticket_id)

    async def reopen_ticket(self, ticket_id: str) -> dict[str, Any]:
        ticket = await self.get_ticket(ticket_id)
        if ticket["status"] != "CLOSED":
            raise InvalidTicketStateError(
                f"Cannot reopen ticket {ticket_id}: current status is {ticket['status']}, expected CLOSED."
            )
        if not ticket.get("discord_channel_id"):
            raise InvalidTicketStateError(
                f"Cannot reopen ticket {ticket_id}: no channel exists for this ticket."
            )
        await self.db.reopen_ticket(ticket_id)
        return await self.get_ticket(ticket_id)

    async def delete_ticket(self, ticket_id: str) -> dict[str, Any]:
        await self.db.update_ticket_deleted(ticket_id)
        return await self.get_ticket(ticket_id)

    async def move_ticket(self, ticket_id: str, new_category: str) -> dict[str, Any]:
        """Move a ticket to a different category. Returns the updated ticket."""
        ticket = await self.get_ticket(ticket_id)
        if ticket["status"] in ("CLOSED", "DELETED"):
            raise InvalidTicketStateError(
                f"Cannot move ticket {ticket_id}: current status is {ticket['status']}."
            )
        if ticket["category"] == new_category:
            raise InvalidTicketStateError(
                f"Ticket {ticket_id} is already in the {new_category} category."
            )
        old_category = ticket["category"]
        await self.db.update_ticket_category(ticket_id, new_category)
        if ticket.get("claimed_by"):
            await self.db.update_ticket_claim(ticket_id, None)
        logger.info("Moved ticket %s from %s to %s", ticket_id, old_category, new_category)
        return await self.get_ticket(ticket_id)

    async def send_dm_response(
        self, member: discord.Member, ticket: dict[str, Any], response: str, response_fa: str = "",
    ) -> bool:
        try:
            fields = [
                (_msg.get("dm.field_ticket"), ticket["ticket_id"], True),
                (_msg.get("dm.field_category"), ticket["category"].title(), True),
            ]
            fa_fields = [
                (_msg.get_persian("dm.field_ticket") or _msg.get("dm.field_ticket"), ticket["ticket_id"], True),
                (_msg.get_persian("dm.field_category") or _msg.get("dm.field_category"), ticket["category"].title(), True),
            ]
            cf = ticket.get("custom_fields", {})
            for key, val in cf.items():
                if val:
                    label = key.replace("_", " ").title()
                    fields.append((label, str(val)[:1024], True))
                    fa_fields.append((label, str(val)[:1024], True))
            fields.append((_msg.get("dm.field_response"), response, False))
            fa_fields.append((_msg.get_persian("dm.field_response") or _msg.get("dm.field_response"), response_fa or response, False))

            embeds = _msg.build_dual_embed(
                "dm.ticket_response",
                color=5814783,
                fields=fields,
                fa_fields=fa_fields,
                ticket_id=ticket["ticket_id"],
            )
            await member.send(embeds=embeds)
            return True
        except discord.Forbidden:
            logger.warning("Failed to send DM to user %d (DMs may be closed)", member.id)
            return False
        except Exception as e:
            logger.error("Error sending DM to user %d: %s", member.id, e)
            return False

    # ── Ban Operations ───────────────────────────────────────────

    async def check_user_banned(self, user_id: int) -> Optional[dict[str, Any]]:
        """Check if a user is currently banned from creating tickets. Returns ban dict or None."""
        return await self.db.get_active_ban(user_id)

    async def ban_user(
        self,
        user_id: int,
        banned_by: int,
        reason: str = "",
        duration_str: Optional[str] = None,
        config: Optional[dict[str, Any]] = None,
        count_offense: bool = True,
    ) -> dict[str, Any]:
        """Ban a user from creating tickets. Returns ban info with duration and offense.

        If count_offense=False, the offense number is not incremented (used for custom duration bans).
        """
        existing_ban = await self.db.get_active_ban(user_id)
        if existing_ban:
            raise InvalidTicketStateError("This user is already banned from creating tickets.")

        offense_count = await self.db.get_user_offense_count(user_id)
        if count_offense:
            next_offense = offense_count + 1
        else:
            next_offense = offense_count

        now = timezone.now()
        banned_at = now.isoformat()

        if duration_str:
            td = _parse_duration(duration_str)
            if td is None:
                expires_at = None
                display_duration = "permanent"
            else:
                expires_at = (now + td).isoformat()
                display_duration = format_duration_display(td)
        else:
            if config:
                ban_config = config.get("ticket_ban", {})
                offense_durations = ban_config.get("offense_durations", {})
                duration_str_config = offense_durations.get(str(next_offense), "permanent")
                td = _parse_duration(duration_str_config)
            else:
                default_map = {1: "3d", 2: "7d", 3: "14d", 4: "30d"}
                duration_str_config = default_map.get(next_offense, "permanent")
                td = _parse_duration(duration_str_config)

            if td is None:
                expires_at = None
                display_duration = "permanent"
            else:
                expires_at = (now + td).isoformat()
                display_duration = format_duration_display(td)

        await self.db.add_ticket_ban(
            user_id=user_id,
            offense_number=next_offense,
            banned_at=banned_at,
            expires_at=expires_at,
            reason=reason,
            banned_by=banned_by,
        )

        return {
            "user_id": user_id,
            "offense_number": next_offense,
            "banned_at": banned_at,
            "expires_at": expires_at,
            "reason": reason,
            "banned_by": banned_by,
            "display_duration": display_duration,
            "permanent": expires_at is None,
        }

    async def unban_user(self, user_id: int) -> bool:
        """Unban a user from creating tickets. Returns True if a ban was deactivated."""
        return await self.db.deactivate_ban(user_id)

    async def get_ban_history(self, user_id: int) -> list[dict[str, Any]]:
        """Get full ban history for a user."""
        return await self.db.get_ban_history(user_id)

    async def get_active_bans(self) -> list[dict[str, Any]]:
        """Get all currently active bans."""
        return await self.db.get_all_active_bans()
