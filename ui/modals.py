from __future__ import annotations

import logging
import traceback
from typing import Any

import discord

from utils.helpers import safe_channel_edit

logger = logging.getLogger("ticket_bot.ui.modals")


async def _send_dm_fallback_alert(
    bot: Any,
    guild: discord.Guild,
    user_id: int,
    ticket_id: str,
) -> None:
    """Send an alert to the configured alerts channel when a DM fails to deliver."""
    try:
        config = bot.config_service
        alerts = config.get("alerts", {})
        if not alerts.get("enabled"):
            return
        channel_id = alerts.get("channel_id")
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        message = alerts.get(
            "dm_failed_message",
            "We tried DMing you the ticket response, but your DMs are closed. "
            "Run the `/status` command to view the response.",
        )
        await channel.send(f"<@{user_id}> {message}")
    except Exception as e:
        logger.error("Failed to send DM fallback alert: %s", e)


_STYLE_MAP = {
    "short": discord.TextStyle.short,
    "paragraph": discord.TextStyle.paragraph,
}

_DEFAULT_FIELDS = [
    {"key": "ign", "label": "IGN", "placeholder": "Enter your Minecraft/In-Game Name", "style": "short", "required": True, "min_length": 3, "max_length": 16},
    {"key": "question", "label": "Problem / Question", "placeholder": "Explain your problem. Our team will review it and assist you.", "style": "paragraph", "required": True, "min_length": 10, "max_length": 2000},
]



class TicketCreationModal(discord.ui.Modal):
    """Dynamic modal for collecting ticket creation information.

    Built from per-category fields config. Falls back to IGN + Problem defaults.
    """

    def __init__(
        self,
        category: str = "",
        category_display: str = "",
        fields: list[dict[str, Any]] | None = None,
        *,
        custom_id: str = "ticket_modal_create",
    ) -> None:
        self._fields = fields or _DEFAULT_FIELDS
        self.title = f"Create {category_display} Ticket" if category_display else "Create Support Ticket"
        super().__init__(custom_id=custom_id)
        self.category = category
        self.category_display = category_display
        self._field_keys = [f["key"] for f in self._fields[:5]]

        for f in self._fields[:5]:
            key = f["key"]
            style_str = f.get("style", "short")
            style = _STYLE_MAP.get(style_str, discord.TextStyle.short)
            self.add_item(discord.ui.TextInput(
                label=f["label"],
                placeholder=f.get("placeholder", ""),
                style=style,
                required=f.get("required", True),
                min_length=f.get("min_length", 0),
                max_length=f.get("max_length", 2000),
                custom_id=f"ticket_modal_{category}_{key}",
            ))

    async def on_submit(self, interaction: discord.Interaction) -> None:
        bot = interaction.client
        msg = bot.messages
        try:
            await self._handle_submit(interaction)
        except Exception as e:
            logger.error("Unhandled error in TicketCreationModal.on_submit: %s", e, exc_info=True)
            traceback.print_exc()
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
                await interaction.followup.send(
                    msg.get("ticket_creation.create_failed"),
                    ephemeral=True,
                )
            except Exception:
                pass

    async def _handle_submit(self, interaction: discord.Interaction) -> None:
        logger.info("[MODAL] TicketCreationModal.callback fired for user=%s category=%s", interaction.user, self.category)

        await interaction.response.defer()

        bot = interaction.client
        msg = bot.messages
        config_service = bot.config_service
        ticket_service = bot.ticket_service
        audit_service = bot.audit_service

        cat_config = config_service.get_category(self.category)
        if not cat_config:
            try:
                await interaction.followup.send(
                    msg.get("ticket_creation.category_unavailable"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        custom_fields: dict[str, str] = {}
        for child in self.children:
            if isinstance(child, discord.ui.TextInput) and child.custom_id.rsplit("_", 1)[-1] in self._field_keys:
                field_key = child.custom_id.rsplit("_", 1)[-1]
                custom_fields[field_key] = child.value

        try:
            ticket = await ticket_service.create_ticket(
                category=self.category,
                prefix=cat_config.get("id_prefix", self.category),
                user_id=interaction.user.id,
                username=str(interaction.user),
                custom_fields=custom_fields,
            )
        except Exception as e:
            logger.error("Failed to create ticket: %s", e, exc_info=True)
            traceback.print_exc()
            await interaction.followup.send(
                msg.get("ticket_creation.create_error"),
                ephemeral=True,
            )
            return

        logger.info("[MODAL] Ticket %s created in DB", ticket["ticket_id"])

        pending_channel_id = cat_config.get("pending_channel_id")
        if not pending_channel_id:
            try:
                await interaction.followup.send(
                    msg.get("ticket_creation.pending_not_configured"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        pending_channel = interaction.guild.get_channel(pending_channel_id) if interaction.guild else None
        if not pending_channel:
            try:
                await interaction.followup.send(
                    msg.get("ticket_creation.pending_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        from utils.formatting import make_pending_embed
        from ui.ticket_views import PendingTicketView

        embed = make_pending_embed(ticket, config_service.get_ui())
        view = PendingTicketView(ticket_id=ticket["ticket_id"], category=self.category)

        reasons = cat_config.get("quick_close_reasons", [])
        if reasons:
            options = []
            for i, r in enumerate(reasons[:25]):
                label = r.get("label", f"Template {i+1}")[:25]
                desc = r.get("message", "")[:100]
                options.append(discord.SelectOption(label=label, value=str(i), description=desc))
            view.template_select.options = options
        else:
            view._children.remove(view.template_select)

        try:
            pending_msg = await pending_channel.send(embed=embed, view=view)
            logger.info("[MODAL] Pending message sent to channel %s (id=%d)", pending_channel.name, pending_msg.id)
            await ticket_service.store_pending_message(ticket["ticket_id"], pending_msg.id)
        except Exception as e:
            logger.error("Failed to send pending ticket message: %s", e, exc_info=True)
            traceback.print_exc()
            try:
                await interaction.followup.send(
                    msg.get("ticket_creation.pending_send_failed"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        try:
            await audit_service.log(
                action="TICKET_CREATED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                ticket_id=ticket["ticket_id"],
                category=self.category,
                channel_id=interaction.channel.id if interaction.channel else None,
                details=f"User {interaction.user} created a {self.category_display} ticket.",
            )
        except Exception as e:
            logger.error("Failed to log audit: %s", e, exc_info=True)

        try:
            await interaction.followup.send(
                msg.get(
                    "ticket_creation.success",
                    category=self.category_display,
                    ticket_id=ticket["ticket_id"],
                ),
                ephemeral=True,
            )
        except Exception:
            pass
        logger.info("[MODAL] Ticket creation response sent to user")


class ResponseModal(discord.ui.Modal, title="Ticket Response"):
    """Modal for staff to respond to a ticket."""

    response = discord.ui.TextInput(
        label="Response",
        placeholder="Type your response to the user...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000,
        custom_id="response_modal_text",
    )

    response_fa = discord.ui.TextInput(
        label="Persian response (optional)",
        placeholder="Optional Persian translation for the DM embed...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=4000,
        custom_id="response_modal_text_fa",
    )

    def __init__(self, ticket_id: str = "", *, custom_id: str = "response_modal") -> None:
        super().__init__(custom_id=custom_id)
        self.ticket_id = ticket_id

    def _get_ticket_id_from_channel(self, interaction: discord.Interaction) -> str:
        if self.ticket_id:
            return self.ticket_id
        if interaction.channel:
            return interaction.channel.name
        return ""

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer()
        except Exception:
            pass

        bot = interaction.client
        msg = bot.messages
        ticket_service = bot.ticket_service
        audit_service = bot.audit_service
        transcript_service = bot.transcript_service
        config_service = bot.config_service

        ticket_id = self._get_ticket_id_from_channel(interaction)
        if not ticket_id:
            try:
                await interaction.followup.send(
                    msg.get("response.not_identified"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        try:
            ticket = await ticket_service.get_ticket(ticket_id)
        except Exception:
            await interaction.followup.send(
                msg.get("response.ticket_not_found"),
                ephemeral=True,
            )
            return

        was_pending = ticket["status"] == "PENDING"

        try:
            updated_ticket = await ticket_service.respond_to_ticket(
                ticket_id, interaction.user.id, self.response.value
            )
        except Exception as e:
            logger.error("Failed to respond to ticket %s: %s", ticket_id, e)
            await interaction.followup.send(
                msg.get("response.send_failed", error=e),
                ephemeral=True,
            )
            return

        member = interaction.guild.get_member(ticket["user_id"]) if interaction.guild else None
        dm_sent = True
        dm_settings = config_service.get_dm_settings()
        if member and dm_settings.get("enabled"):
            dm_sent = await ticket_service.send_dm_response(member, updated_ticket, self.response.value, response_fa=self.response_fa.value or "")

        dm_status = "" if dm_sent else msg.get("response.dm_note_closed")

        if not dm_sent and interaction.guild:
            await _send_dm_fallback_alert(bot, interaction.guild, ticket["user_id"], ticket_id)

        await audit_service.log(
            action="TICKET_RESPONDED",
            actor_id=interaction.user.id,
            actor_name=str(interaction.user),
            ticket_id=ticket_id,
            category=ticket["category"],
            details=f"Staff responded to ticket {ticket_id}.{dm_status}",
        )

        cat_config = config_service.get_category(ticket["category"])

        try:
            await ticket_service.close_ticket(ticket_id)
            updated_ticket = await ticket_service.get_ticket(ticket_id)
        except Exception as e:
            logger.error("Failed to auto-close ticket %s: %s", ticket_id, e)

        if was_pending:
            pending_msg_id = ticket.get("pending_message_id")
            if pending_msg_id and interaction.guild:
                pending_channel_id = cat_config.get("pending_channel_id") if cat_config else None
                if pending_channel_id:
                    pending_channel = interaction.guild.get_channel(pending_channel_id)
                    if pending_channel:
                        try:
                            pending_msg = await pending_channel.fetch_message(pending_msg_id)
                            await pending_msg.delete()
                        except Exception as e:
                            logger.warning("Failed to delete pending message %d: %s", pending_msg_id, e)
        else:
            closed_category_id = cat_config.get("closed_category_id") if cat_config else None
            if closed_category_id and interaction.guild and interaction.channel:
                closed_category = interaction.guild.get_channel(closed_category_id)
                if closed_category and isinstance(closed_category, discord.CategoryChannel):
                    try:
                        naming_format = config_service.get_closed_naming_format()
                        prefix = cat_config.get("id_prefix", ticket["category"]) if cat_config else ticket["category"]
                        num = ticket_id.split("-")[-1]
                        closed_name = naming_format.format(
                            prefix=prefix, number=num, ticket_id=ticket_id
                        )

                        view_closed_role_ids = list(set(
                            cat_config.get("view_closed_roles", [])
                            + await bot.permission_service.get_role_ids_for_permission("ticket_view_closed", ticket["category"])
                            + await bot.permission_service.get_role_ids_for_permission("ticket_view_closed")
                        )) if cat_config else []
                        new_overwrites = {
                            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                            interaction.guild.me: discord.PermissionOverwrite(
                                view_channel=True, send_messages=True,
                                read_message_history=True, manage_channels=True, attach_files=True,
                            ),
                        }
                        for role_id in view_closed_role_ids:
                            role = interaction.guild.get_role(role_id)
                            if role:
                                new_overwrites[role] = discord.PermissionOverwrite(
                                    view_channel=True, send_messages=True,
                                    read_message_history=True, attach_files=True,
                                )
                        ok = await safe_channel_edit(
                            interaction.channel,
                            name=closed_name,
                            category=closed_category,
                            overwrites=new_overwrites,
                        )
                        if not ok:
                            logger.error("Failed to move ticket %s to closed category after retries", ticket_id)
                    except Exception as e:
                        logger.error("Failed to move ticket to closed category: %s", e)

        archive_channel_id = config_service.get("archive_channel_id")
        if archive_channel_id and interaction.guild:
            archive_channel = interaction.guild.get_channel(archive_channel_id)
            if archive_channel:
                try:
                    from utils.formatting import make_archive_embed
                    archive_embed = make_archive_embed(
                        updated_ticket, config_service.get_ui(),
                        staff_name=str(interaction.user),
                        response_text=self.response.value,
                    )
                    archive_msg = await archive_channel.send(embed=archive_embed)
                    await audit_service.log(
                        action="TICKET_ARCHIVED",
                        actor_id=interaction.user.id,
                        actor_name=str(interaction.user),
                        ticket_id=ticket_id,
                        category=ticket["category"],
                        channel_id=archive_channel_id,
                        details=f"Ticket {ticket_id} archived to {archive_channel.name}.",
                    )
                except Exception as e:
                    logger.error("Failed to archive ticket %s: %s", ticket_id, e)

        await audit_service.log(
            action="TICKET_CLOSED",
            actor_id=interaction.user.id,
            actor_name=str(interaction.user),
            ticket_id=ticket_id,
            category=ticket["category"],
            details=f"Ticket auto-closed after staff response by {interaction.user}.{dm_status}",
        )

        try:
            await interaction.followup.send(
                msg.get("response.auto_closed", ticket_id=ticket_id) + dm_status,
                ephemeral=True,
            )
        except Exception:
            pass

        if interaction.channel and interaction.channel.id != config_service.get_audit_log().get("channel_id"):
            from utils.formatting import make_ticket_embed
            embed = make_ticket_embed(updated_ticket, config_service.get_ui())
            try:
                await interaction.channel.send(embed=embed)
            except Exception:
                pass


async def _close_ticket_flow(
    interaction: discord.Interaction,
    ticket_id: str,
    reason: str = "",
    label: str = "Closed",
    reason_fa: str = "",
) -> None:
    """Shared flow for closing a ticket from pending buttons (Resolved, Close, Close with Reason)."""
    bot = interaction.client
    msg = interaction.client.messages
    ticket_service = bot.ticket_service
    audit_service = bot.audit_service
    transcript_service = bot.transcript_service
    config_service = bot.config_service

    try:
        ticket = await ticket_service.get_ticket(ticket_id)
    except Exception:
        try:
            await interaction.followup.send(msg.get("errors.ticket_not_found"), ephemeral=True)
        except Exception:
            pass
        return

    was_pending = ticket["status"] == "PENDING"

    already_responded = False
    try:
        await ticket_service.respond_to_ticket(
            ticket_id, interaction.user.id, reason or f"Ticket {label.lower()} by staff."
        )
        updated_ticket = await ticket_service.get_ticket(ticket_id)
    except Exception as e:
        if "already been responded" in str(e).lower() or "already" in str(e).lower():
            logger.warning("Ticket %s already responded, skipping respond step: %s", ticket_id, e)
            already_responded = True
            updated_ticket = ticket
        else:
            logger.error("Failed to respond to ticket %s: %s", ticket_id, e)
            try:
                await interaction.followup.send(msg.get("response.close_failed", error=e), ephemeral=True)
            except Exception:
                pass
            return

    member = interaction.guild.get_member(ticket["user_id"]) if interaction.guild else None
    dm_sent = True
    dm_settings = config_service.get_dm_settings()
    if member and dm_settings.get("enabled") and dm_settings.get("close_dm"):
        label_fa = msg.get_persian(f"labels.{label.lower()}") or label
        dm_fields = [
            (msg.get("dm.field_category"), ticket["category"].title(), True),
        ]
        fa_dm_fields = [
            (msg.get_persian("dm.field_category") or msg.get("dm.field_category"), ticket["category"].title(), True),
        ]
        if reason:
            dm_fields.append((msg.get("dm.field_reason"), reason[:1024], False))
            fa_reason = (reason_fa or reason)[:1024]
            fa_dm_fields.append((msg.get_persian("dm.field_reason") or msg.get("dm.field_reason"), fa_reason, False))
        dm_sent = await msg.send_dual_dm(
            member,
            key="dm.ticket_closed",
            color=8487426,
            fields=dm_fields,
            fa_fields=fa_dm_fields,
            fa_kwargs={"label": label_fa},
            label=label,
            ticket_id=ticket_id,
        )

    dm_status = "" if dm_sent else msg.get("response.dm_note")

    if not dm_sent and interaction.guild:
        await _send_dm_fallback_alert(bot, interaction.guild, ticket["user_id"], ticket_id)

    cat_config = config_service.get_category(ticket["category"])

    try:
        await ticket_service.close_ticket(ticket_id)
        updated_ticket = await ticket_service.get_ticket(ticket_id)
    except Exception as e:
        logger.error("Failed to auto-close ticket %s: %s", ticket_id, e)
        updated_ticket = ticket

    if was_pending:
        pending_msg_id = ticket.get("pending_message_id")
        if pending_msg_id and interaction.guild:
            pending_channel_id = cat_config.get("pending_channel_id") if cat_config else None
            if pending_channel_id:
                pending_channel = interaction.guild.get_channel(pending_channel_id)
                if pending_channel:
                    try:
                        pending_msg = await pending_channel.fetch_message(pending_msg_id)
                        await pending_msg.delete()
                    except Exception as e:
                        logger.warning("Failed to delete pending message %d: %s", pending_msg_id, e)
    else:
        ticket_channel_id = updated_ticket.get("discord_channel_id")
        closed_category_id = cat_config.get("closed_category_id") if cat_config else None
        if closed_category_id and interaction.guild and ticket_channel_id:
            ticket_channel = interaction.guild.get_channel(ticket_channel_id)
            if not ticket_channel:
                logger.error("Cannot find channel %s for ticket %s during close", ticket_channel_id, ticket_id)
            closed_category = interaction.guild.get_channel(closed_category_id)
            if closed_category and isinstance(closed_category, discord.CategoryChannel):
                try:
                    naming_format = config_service.get_closed_naming_format()
                    prefix = cat_config.get("id_prefix", ticket["category"]) if cat_config else ticket["category"]
                    num = ticket_id.split("-")[-1]
                    closed_name = naming_format.format(prefix=prefix, number=num, ticket_id=ticket_id)
                    view_closed_role_ids = list(set(
                        cat_config.get("view_closed_roles", [])
                        + await bot.permission_service.get_role_ids_for_permission("ticket_view_closed", ticket["category"])
                        + await bot.permission_service.get_role_ids_for_permission("ticket_view_closed")
                    )) if cat_config else []
                    new_overwrites = {
                        interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        interaction.guild.me: discord.PermissionOverwrite(
                            view_channel=True, send_messages=True,
                            read_message_history=True, manage_channels=True, attach_files=True,
                        ),
                    }
                    for role_id in view_closed_role_ids:
                        role = interaction.guild.get_role(role_id)
                        if role:
                            new_overwrites[role] = discord.PermissionOverwrite(
                                view_channel=True, send_messages=True,
                                read_message_history=True, attach_files=True,
                            )
                    if ticket_channel:
                        ok = await safe_channel_edit(
                            ticket_channel,
                            name=closed_name,
                            category=closed_category,
                            overwrites=new_overwrites,
                        )
                        if not ok:
                            logger.error("Failed to move ticket %s to closed category after retries", ticket_id)
                except Exception as e:
                    logger.error("Failed to move ticket to closed category: %s", e)

    archive_channel_id = config_service.get("archive_channel_id")
    if archive_channel_id and interaction.guild:
        archive_channel = interaction.guild.get_channel(archive_channel_id)
        if archive_channel:
            try:
                from utils.formatting import make_archive_embed
                archive_embed = make_archive_embed(
                    updated_ticket, config_service.get_ui(),
                    staff_name=str(interaction.user),
                    response_text=reason or f"Ticket {label.lower()} by staff.",
                )
                await archive_channel.send(embed=archive_embed)
                await audit_service.log(
                    action="TICKET_ARCHIVED",
                    actor_id=interaction.user.id,
                    actor_name=str(interaction.user),
                    ticket_id=ticket_id,
                    category=ticket["category"],
                    channel_id=archive_channel_id,
                    details=f"Ticket {ticket_id} archived to {archive_channel.name}.",
                )
            except Exception as e:
                logger.error("Failed to archive ticket %s: %s", ticket_id, e)

    await audit_service.log(
        action="TICKET_CLOSED",
        actor_id=interaction.user.id,
        actor_name=str(interaction.user),
        ticket_id=ticket_id,
        category=ticket["category"],
        details=f"Ticket {label.lower()} by {interaction.user}.{dm_status}",
    )

    try:
        await interaction.followup.send(
            msg.get("close.ticket_closed", ticket_id=ticket_id, label=label.lower()) + dm_status,
            ephemeral=True,
        )
    except Exception:
        pass


class CloseReasonModal(discord.ui.Modal, title="Close Ticket with Reason"):
    """Modal for closing a ticket with a specific reason."""

    reason = discord.ui.TextInput(
        label="Reason for closing",
        placeholder="e.g. Wrong ticket category, issue resolved, etc.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
        custom_id="close_reason_modal_text",
    )

    reason_fa = discord.ui.TextInput(
        label="Persian reason (optional)",
        placeholder="Optional Persian translation for the DM embed...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
        custom_id="close_reason_modal_text_fa",
    )

    def __init__(self, ticket_id: str = "", *, custom_id: str = "close_reason_modal") -> None:
        super().__init__(custom_id=custom_id)
        self.ticket_id = ticket_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer()
        except Exception:
            pass
        bot = interaction.client
        msg = bot.messages
        await _close_ticket_flow(interaction, self.ticket_id, reason=self.reason.value, label=msg.get("close.label_closed"), reason_fa=self.reason_fa.value or "")


class ResolveModal(discord.ui.Modal, title="Resolve Ticket"):
    """Modal for resolving a pending ticket with a response message."""

    response = discord.ui.TextInput(
        label="Response to user",
        placeholder="Type your response. The ticket will be resolved and closed.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=4000,
        custom_id="resolve_modal_text",
    )

    response_fa = discord.ui.TextInput(
        label="Persian response (optional)",
        placeholder="Optional Persian translation for the DM embed...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=4000,
        custom_id="resolve_modal_text_fa",
    )

    def __init__(self, ticket_id: str = "", *, custom_id: str = "resolve_modal") -> None:
        super().__init__(custom_id=custom_id)
        self.ticket_id = ticket_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer()
        except Exception:
            pass
        bot = interaction.client
        msg = bot.messages
        await _close_ticket_flow(interaction, self.ticket_id, reason=self.response.value, label=msg.get("close.label_resolved"), reason_fa=self.response_fa.value or "")


class BanReasonModal(discord.ui.Modal, title="Ban User from Tickets"):
    """Modal for collecting a reason before banning a user from creating tickets."""

    reason = discord.ui.TextInput(
        label="Reason for ban",
        placeholder="e.g. Abusing ticket system, spam tickets, etc.",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500,
        custom_id="ban_reason_modal_text",
    )

    reason_fa = discord.ui.TextInput(
        label="Persian reason (optional)",
        placeholder="Optional Persian translation for the DM embed...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
        custom_id="ban_reason_modal_text_fa",
    )

    def __init__(self, ticket_id: str = "", user_id: int = 0, *, custom_id: str = "ban_reason_modal") -> None:
        super().__init__(custom_id=custom_id)
        self.ticket_id = ticket_id
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer()
        except Exception:
            pass

        bot = interaction.client
        msg = bot.messages
        ticket_service = bot.ticket_service
        config_service = bot.config_service
        audit_service = bot.audit_service

        try:
            ticket = await ticket_service.get_ticket(self.ticket_id)
            if not ticket:
                try:
                    await interaction.followup.send(msg.get("errors.ticket_not_found"), ephemeral=True)
                except Exception:
                    pass
                return

            existing = await ticket_service.check_user_banned(self.user_id)
            if existing:
                try:
                    await interaction.followup.send(
                        msg.get("ban.already_banned"),
                        ephemeral=True,
                    )
                except Exception:
                    pass
                return

            ban_info = await ticket_service.ban_user(
                user_id=self.user_id,
                banned_by=interaction.user.id,
                reason=self.reason.value,
                config=config_service._config,
                count_offense=True,
            )

            member = interaction.guild.get_member(self.user_id) if interaction.guild else None
            if member:
                dm_sent = await msg.send_dual_dm(
                    member,
                    key="dm.ban_notice",
                    color=15158332,
                    fields=[
                        (msg.get("dm.field_duration"), ban_info["display_duration"], True),
                        (msg.get("dm.field_offense"), f"#{ban_info['offense_number']}", True),
                        (msg.get("dm.field_reason"), self.reason.value, False),
                    ],
                    fa_fields=[
                        (msg.get_persian("dm.field_duration") or msg.get("dm.field_duration"), ban_info["display_duration"], True),
                        (msg.get_persian("dm.field_offense") or msg.get("dm.field_offense"), f"#{ban_info['offense_number']}", True),
                        (msg.get_persian("dm.field_reason") or msg.get("dm.field_reason"), self.reason_fa.value or self.reason.value, False),
                    ],
                    guild=interaction.guild.name,
                )
            else:
                dm_sent = False

            dm_note = "" if dm_sent else msg.get("response.dm_note")

            await audit_service.log(
                action="USER_BANNED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                ticket_id=self.ticket_id,
                category=ticket["category"],
                target_id=self.user_id,
                target_name=str(member) if member else str(self.user_id),
                details=f"Banned <@{self.user_id}> for {ban_info['display_duration']} "
                        f"(offense #{ban_info['offense_number']}). Reason: {self.reason.value}{dm_note}",
            )

            archive_channel_id = config_service.get("archive_channel_id")
            archive_channel = interaction.guild.get_channel(archive_channel_id) if interaction.guild else None
            if archive_channel:
                try:
                    from utils.formatting import make_archive_embed
                    updated_ticket = await ticket_service.get_ticket(self.ticket_id)
                    archive_embed = make_archive_embed(
                        updated_ticket, config_service.get_ui(),
                        staff_name=str(interaction.user),
                        response_text=f"User banned: {self.reason.value}",
                    )
                    await archive_channel.send(embed=archive_embed)
                    await audit_service.log(
                        action="TICKET_ARCHIVED",
                        actor_id=interaction.user.id,
                        actor_name=str(interaction.user),
                        ticket_id=self.ticket_id,
                        category=ticket["category"],
                        channel_id=archive_channel_id,
                        details=f"Ticket {self.ticket_id} archived after ban.",
                    )
                except Exception as e:
                    logger.error("Failed to archive ticket %s: %s", self.ticket_id, e)

            await ticket_service.close_ticket(self.ticket_id)

            if interaction.guild:
                pending_msg_id = ticket.get("pending_message_id")
                if pending_msg_id:
                    cat_config = config_service.get_category(ticket["category"])
                    pending_channel_id = cat_config.get("pending_channel_id") if cat_config else None
                    if pending_channel_id:
                        pending_channel = interaction.guild.get_channel(pending_channel_id)
                        if pending_channel:
                            try:
                                pending_msg = await pending_channel.fetch_message(pending_msg_id)
                                await pending_msg.delete()
                            except Exception:
                                pass

            try:
                await interaction.followup.send(
                    msg.get(
                        "ban.ban_success",
                        user_id=self.user_id,
                        duration=ban_info["display_duration"],
                        offense=ban_info["offense_number"],
                        reason=self.reason.value,
                        dm_note=dm_note,
                    ),
                    ephemeral=True,
                )
            except Exception:
                pass

        except Exception as e:
            logger.error("Error in BanReasonModal: %s", e, exc_info=True)
            try:
                await interaction.followup.send(msg.get("ban.ban_failed", error=e), ephemeral=True)
            except Exception:
                pass
