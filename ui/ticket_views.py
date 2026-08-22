from __future__ import annotations

import logging
from typing import Optional

import discord

from .modals import ResponseModal, CloseReasonModal, _close_ticket_flow, ResolveModal
from utils.helpers import safe_channel_edit

logger = logging.getLogger("ticket_bot.ui.ticket_views")


def _extract_ticket_id(interaction: discord.Interaction) -> Optional[str]:
    """Extract ticket_id from the interaction message embed."""
    msg = interaction.client.messages
    if not interaction.message or not interaction.message.embeds:
        return None
    embed = interaction.message.embeds[0]
    for field in embed.fields:
        if field.name in (msg.get("formatting.ticket_id"), "Ticket ID"):
            return field.value
    return None


class PendingTicketView(discord.ui.View):
    """Persistent view for pending ticket messages with Resolved, Ban, Close with Reason, Templates dropdown, and Create Channel buttons."""

    def __init__(self, ticket_id: str = "", category: str = "") -> None:
        super().__init__(timeout=None)

    @discord.ui.select(
        placeholder="Quick close with a template...",
        custom_id="pending_template_select",
        min_values=1,
        max_values=1,
        row=2,
    )
    async def template_select(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
        bot = interaction.client
        msg = bot.messages
        permission_service = bot.permission_service
        config_service = bot.config_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(msg.get("errors.not_identified"), ephemeral=True)
            except Exception:
                pass
            return

        ticket = await bot.ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(msg.get("errors.ticket_not_found"), ephemeral=True)
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_respond", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_resolve"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        cat_config = config_service.get_category(ticket["category"])
        if not cat_config:
            try:
                await interaction.response.send_message("Category not configured.", ephemeral=True)
            except Exception:
                pass
            return

        reasons = cat_config.get("quick_close_reasons", [])
        try:
            index = int(select.values[0])
        except (ValueError, IndexError):
            try:
                await interaction.response.send_message(msg.get("template.invalid_selection"), ephemeral=True)
            except Exception:
                pass
            return

        if index < 0 or index >= len(reasons):
            try:
                await interaction.response.send_message(msg.get("template.not_found"), ephemeral=True)
            except Exception:
                pass
            return

        template = reasons[index]
        template_label = template.get("label", "Unknown")
        template_message = template.get("message", f"Ticket resolved via template: {template_label}.")
        template_message_fa = template.get("message_fa", "")

        try:
            await interaction.response.defer()
        except Exception:
            pass

        await _close_ticket_flow(
            interaction, ticket_id,
            reason=template_message,
            label="Resolved",
            reason_fa=template_message_fa,
        )

    @discord.ui.button(
        label="Resolved",
        style=discord.ButtonStyle.success,
        custom_id="pending_resolved",
        row=0,
    )
    async def resolved_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        permission_service = bot.permission_service
        config_service = bot.config_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(msg.get("errors.not_identified"), ephemeral=True)
            except Exception:
                pass
            return

        ticket = await bot.ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(msg.get("errors.ticket_not_found"), ephemeral=True)
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_respond", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_resolve"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        modal = ResolveModal(ticket_id=ticket_id)
        try:
            await interaction.response.send_modal(modal)
        except Exception:
            pass

    @discord.ui.button(
        label="Ban",
        style=discord.ButtonStyle.danger,
        custom_id="pending_ban",
        row=0,
    )
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        permission_service = bot.permission_service
        config_service = bot.config_service
        ticket_service = bot.ticket_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(msg.get("errors.not_identified"), ephemeral=True)
            except Exception:
                pass
            return

        ticket = await ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(msg.get("errors.ticket_not_found"), ephemeral=True)
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_ban", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_ban"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        existing = await ticket_service.check_user_banned(ticket["user_id"])
        if existing:
            try:
                await interaction.response.send_message(
                    f"<@{ticket['user_id']}> is already banned from creating tickets.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        from ui.modals import BanReasonModal
        modal = BanReasonModal(ticket_id=ticket_id, user_id=ticket["user_id"])
        try:
            await interaction.response.send_modal(modal)
        except Exception:
            pass

    @discord.ui.button(
        label="Close with Reason",
        style=discord.ButtonStyle.secondary,
        custom_id="pending_close_reason",
        row=0,
    )
    async def close_reason_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        permission_service = bot.permission_service
        config_service = bot.config_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(msg.get("errors.not_identified"), ephemeral=True)
            except Exception:
                pass
            return

        ticket = await bot.ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(msg.get("errors.ticket_not_found"), ephemeral=True)
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_close", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_close"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        modal = CloseReasonModal(ticket_id=ticket_id)
        try:
            await interaction.response.send_modal(modal)
        except Exception:
            pass

    @discord.ui.button(
        label="Create Channel",
        style=discord.ButtonStyle.primary,
        custom_id="pending_create_channel",
        row=1,
    )
    async def create_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        permission_service = bot.permission_service
        config_service = bot.config_service
        ticket_service = bot.ticket_service
        audit_service = bot.audit_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(
                    msg.get("errors.not_identified"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        ticket = await ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(
                    msg.get("errors.ticket_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        if ticket["status"] != "PENDING":
            try:
                await interaction.response.send_message(
                    f"This ticket is no longer pending. Current status: {ticket['status']}",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_create", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_create_channel"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        try:
            await interaction.response.defer()
        except Exception:
            pass

        cat_config = config_service.get_category(ticket["category"])
        if not cat_config:
            try:
                await interaction.followup.send(
                    msg.get("move.category_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        open_category_id = cat_config.get("open_category_id")
        if not open_category_id:
            try:
                await interaction.followup.send(
                    msg.get("move.open_not_configured"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        open_category = interaction.guild.get_channel(open_category_id) if interaction.guild else None
        if not open_category or not isinstance(open_category, discord.CategoryChannel):
            try:
                await interaction.followup.send(
                    msg.get("move.open_channel_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        ticket_id = ticket["ticket_id"]
        user = interaction.guild.get_member(ticket["user_id"]) if interaction.guild else None

        permission_overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
                attach_files=True,
            ),
        }

        if user:
            permission_overwrites[user] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            )

        staff_role_ids = cat_config.get("staff_roles", [])
        for role_id in staff_role_ids:
            role = interaction.guild.get_role(role_id)
            if role:
                permission_overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                )

        channel_name = f"{ticket['category']}-{ticket_id.split('-')[-1]}"
        try:
            channel = await open_category.create_text_channel(
                name=channel_name,
                overwrites=permission_overwrites,
                topic=f"Ticket {ticket_id} | {ticket['category'].title()} | User: {ticket['user_id']}",
            )
        except Exception as e:
            logger.error("Failed to create ticket channel: %s", e)
            try:
                await interaction.followup.send(
                    f"Failed to create ticket channel: {e}",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        await ticket_service.open_ticket(ticket_id, channel.id)

        from utils.formatting import make_ticket_embed
        embed = make_ticket_embed(
            await ticket_service.get_ticket(ticket_id),
            config_service.get_ui(),
            title=f"IRBW Support - {ticket_id}",
            description=f"Welcome! Please describe your issue and our team will assist you.",
        )

        try:
            await channel.send(
                content=user.mention if user else "",
                embed=embed,
                view=ActiveTicketView(),
            )
        except Exception as e:
            logger.error("Failed to send welcome message: %s", e)

        pending_msg_id = ticket.get("pending_message_id")
        if pending_msg_id and interaction.guild:
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

        await audit_service.log(
            action="TICKET_OPENED",
            actor_id=interaction.user.id,
            actor_name=str(interaction.user),
            ticket_id=ticket_id,
            category=ticket["category"],
            channel_id=channel.id,
            details=f"Ticket channel created for {ticket_id}.",
        )

        try:
            await interaction.followup.send(
                f"Ticket channel {channel.mention} has been created for **{ticket_id}**.",
                ephemeral=True,
            )
        except Exception:
            pass


class ActiveTicketView(discord.ui.View):
    """Persistent view for active ticket channels with action buttons."""

    def __init__(self, ticket_id: str = "", category: str = "") -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.primary,
        custom_id="active_claim",
        row=0,
    )
    async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        ticket_service = bot.ticket_service
        permission_service = bot.permission_service
        config_service = bot.config_service
        audit_service = bot.audit_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(
                    msg.get("errors.not_identified"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        ticket = await ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(
                    msg.get("errors.ticket_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_claim", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_claim"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        try:
            updated_ticket = await ticket_service.claim_ticket(ticket_id, interaction.user.id)
        except Exception as e:
            try:
                await interaction.response.send_message(
                    f"Failed to claim ticket: {e}",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        await audit_service.log(
            action="TICKET_CLAIMED",
            actor_id=interaction.user.id,
            actor_name=str(interaction.user),
            ticket_id=ticket_id,
            category=ticket["category"],
            details=f"Ticket claimed by {interaction.user}.",
        )

        from utils.formatting import make_ticket_embed
        embed = make_ticket_embed(
            updated_ticket,
            config_service.get_ui(),
            claimed_by=str(interaction.user),
        )
        try:
            await interaction.response.send_message(
                f"{interaction.user.mention} has claimed ticket **{ticket_id}**.",
                embed=embed,
                ephemeral=False,
            )
        except Exception:
            pass

    @discord.ui.button(
        label="Unclaim",
        style=discord.ButtonStyle.secondary,
        custom_id="active_unclaim",
        row=0,
    )
    async def unclaim_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        ticket_service = bot.ticket_service
        permission_service = bot.permission_service
        config_service = bot.config_service
        audit_service = bot.audit_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(
                    msg.get("errors.not_identified"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        ticket = await ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(
                    msg.get("errors.ticket_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_unclaim", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_unclaim"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        try:
            updated_ticket = await ticket_service.unclaim_ticket(ticket_id, interaction.user.id)
        except Exception as e:
            try:
                await interaction.response.send_message(
                    f"Failed to unclaim ticket: {e}",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        await audit_service.log(
            action="TICKET_UNCLAIMED",
            actor_id=interaction.user.id,
            actor_name=str(interaction.user),
            ticket_id=ticket_id,
            category=ticket["category"],
            details=f"Ticket unclaimed by {interaction.user}.",
        )

        try:
            await interaction.response.send_message(
                f"{interaction.user.mention} has unclaimed ticket **{ticket_id}**.",
                ephemeral=False,
            )
        except Exception:
            pass

    @discord.ui.button(
        label="Respond",
        style=discord.ButtonStyle.success,
        custom_id="active_respond",
        row=0,
    )
    async def respond_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        permission_service = bot.permission_service
        config_service = bot.config_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(
                    msg.get("errors.not_identified"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        ticket = await bot.ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(
                    msg.get("errors.ticket_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_respond", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_respond"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        modal = ResponseModal(ticket_id=ticket_id)
        try:
            await interaction.response.send_modal(modal)
        except Exception:
            pass

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        custom_id="active_close",
        row=1,
    )
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        ticket_service = bot.ticket_service
        permission_service = bot.permission_service
        config_service = bot.config_service
        audit_service = bot.audit_service
        transcript_service = bot.transcript_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(
                    msg.get("errors.not_identified"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        ticket = await ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(
                    msg.get("errors.ticket_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_close", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_close"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        try:
            await interaction.response.defer()
        except Exception:
            pass

        try:
            updated_ticket = await ticket_service.close_ticket(ticket_id)
        except Exception as e:
            try:
                await interaction.followup.send(
                    f"Failed to close ticket: {e}",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        member = interaction.guild.get_member(ticket["user_id"]) if interaction.guild else None
        dm_sent = True
        if member:
            dm_sent = await msg.send_dual_dm(
                member,
                key="dm.ticket_closed",
                color=8487426,
                fields=[
                    (msg.get("dm.field_category"), ticket["category"].title(), True),
                ],
                fa_fields=[
                    (msg.get_persian("dm.field_category") or msg.get("dm.field_category"), ticket["category"].title(), True),
                ],
                fa_kwargs={"label": msg.get_persian("labels.closed") or "Closed"},
                label="Closed",
                ticket_id=ticket_id,
            )

        if not dm_sent and interaction.guild:
            from ui.modals import _send_dm_fallback_alert
            await _send_dm_fallback_alert(bot, interaction.guild, ticket["user_id"], ticket_id)

        dm_status = "" if dm_sent else msg.get("response.dm_note_closed")

        try:
            await interaction.followup.send(
                msg.get("active_view.close_success", user=interaction.user.mention, ticket_id=ticket_id) + dm_status,
                ephemeral=False,
            )
        except Exception:
            pass

        cat_config = config_service.get_category(ticket["category"])
        closed_category_id = cat_config.get("closed_category_id") if cat_config else None

        if closed_category_id and interaction.guild:
            closed_category = interaction.guild.get_channel(closed_category_id)
            if closed_category and isinstance(closed_category, discord.CategoryChannel):
                try:
                    naming_format = config_service.get_closed_naming_format()
                    prefix = cat_config.get("id_prefix", ticket["category"]) if cat_config else ticket["category"]
                    num = ticket_id.split("-")[-1]
                    closed_name = naming_format.format(
                        prefix=prefix, number=num, ticket_id=ticket_id
                    )

                    config_view_closed = cat_config.get("view_closed_roles", []) if cat_config else []
                    perm_service = interaction.client.permission_service
                    db_view_closed = await perm_service.get_role_ids_for_permission("ticket_view_closed", ticket["category"])
                    db_view_closed += await perm_service.get_role_ids_for_permission("ticket_view_closed")
                    view_closed_role_ids = list(set(config_view_closed + db_view_closed))
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
                        response_text=updated_ticket.get("response", "No response recorded."),
                    )
                    await archive_channel.send(embed=archive_embed)
                except Exception as e:
                    logger.error("Failed to archive ticket %s: %s", ticket_id, e)

        await audit_service.log(
            action="TICKET_CLOSED",
            actor_id=interaction.user.id,
            actor_name=str(interaction.user),
            ticket_id=ticket_id,
            category=ticket["category"],
            details=f"Ticket closed by {interaction.user}.",
        )

    @discord.ui.button(
        label="Transcript",
        style=discord.ButtonStyle.secondary,
        custom_id="active_transcript",
        row=1,
    )
    async def transcript_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        permission_service = bot.permission_service
        config_service = bot.config_service
        audit_service = bot.audit_service
        transcript_service = bot.transcript_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(
                    msg.get("errors.not_identified"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        ticket = await bot.ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(
                    msg.get("errors.ticket_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_transcript", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_transcript"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        try:
            await interaction.response.defer()
        except Exception:
            pass

        try:
            messages = await bot.db.get_messages(ticket_id)
            claims = await bot.db.get_claims(ticket_id)
            responses = await bot.db.get_responses(ticket_id)
            html_content = await transcript_service.generate_transcript(
                ticket, messages, claims, responses
            )
            filepath = await transcript_service.save_transcript(ticket_id, html_content)

            transcript_config = config_service.get_transcripts()
            transcript_channel_id = transcript_config.get("channel_id")
            if transcript_channel_id and interaction.guild:
                transcript_channel = interaction.guild.get_channel(transcript_channel_id)
                if transcript_channel:
                    await transcript_service.upload_transcript(
                        transcript_channel, filepath, ticket_id
                    )

            await audit_service.log(
                action="TRANSCRIPT_GENERATED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                ticket_id=ticket_id,
                category=ticket["category"],
                details=f"Manual transcript generated for ticket {ticket_id}.",
            )

            import discord as _discord
            file = _discord.File(filepath, filename=f"{ticket_id}_transcript.html")
            await interaction.followup.send(
                f"Transcript generated for **{ticket_id}**.", file=file,
                ephemeral=True,
            )

        except Exception as e:
            logger.error("Failed to generate transcript: %s", e)
            await interaction.followup.send(
                f"Failed to generate transcript: {e}",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Delete",
        style=discord.ButtonStyle.danger,
        custom_id="active_delete",
        row=1,
    )
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        ticket_service = bot.ticket_service
        permission_service = bot.permission_service
        config_service = bot.config_service
        audit_service = bot.audit_service
        transcript_service = bot.transcript_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(
                    msg.get("errors.not_identified"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        ticket = await ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(
                    msg.get("errors.ticket_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_delete", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_delete"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        try:
            await interaction.response.defer()
        except Exception:
            pass

        transcript_config = config_service.get_transcripts()
        if transcript_config.get("channel_id"):
            try:
                messages = await bot.db.get_messages(ticket_id)
                claims = await bot.db.get_claims(ticket_id)
                responses = await bot.db.get_responses(ticket_id)
                html_content = await transcript_service.generate_transcript(
                    ticket, messages, claims, responses
                )
                filepath = await transcript_service.save_transcript(ticket_id, html_content)

                transcript_channel_id = transcript_config.get("channel_id")
                if transcript_channel_id and interaction.guild:
                    transcript_channel = interaction.guild.get_channel(transcript_channel_id)
                    if transcript_channel:
                        await transcript_service.upload_transcript(
                            transcript_channel, filepath, ticket_id
                        )

                await audit_service.log(
                    action="TRANSCRIPT_GENERATED",
                    actor_id=interaction.user.id,
                    actor_name=str(interaction.user),
                    ticket_id=ticket_id,
                    category=ticket["category"],
                    details=f"Transcript generated before deletion for ticket {ticket_id}.",
                )
            except Exception as e:
                logger.error("Failed to generate transcript before deletion: %s", e)

        try:
            await ticket_service.delete_ticket(ticket_id)
        except Exception as e:
            try:
                await interaction.followup.send(
                    f"Failed to delete ticket: {e}",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        await audit_service.log(
            action="TICKET_DELETED",
            actor_id=interaction.user.id,
            actor_name=str(interaction.user),
            ticket_id=ticket_id,
            category=ticket["category"],
            details=f"Ticket deleted by {interaction.user}.",
        )

        try:
            await interaction.followup.send(
                f"Ticket **{ticket_id}** has been deleted.",
                ephemeral=True,
            )
        except Exception:
            pass

        if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
            try:
                await interaction.channel.delete(reason=f"Ticket {ticket_id} deleted by {interaction.user}")
            except Exception as e:
                logger.error("Failed to delete channel: %s", e)

    @discord.ui.button(
        label="Move",
        style=discord.ButtonStyle.secondary,
        custom_id="active_move",
        row=2,
    )
    async def move_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        permission_service = bot.permission_service
        config_service = bot.config_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(
                    msg.get("errors.not_identified"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        ticket = await bot.ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(
                    msg.get("errors.ticket_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        if ticket["status"] in ("CLOSED", "DELETED"):
            try:
                await interaction.response.send_message(
                    f"Cannot move a ticket with status **{ticket['status']}**.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        categories = config_service.get_categories()
        has_perm = await permission_service.check(
            interaction.user, "ticket_move", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_move"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        options = []
        for key, cat_data in categories.items():
            if key == ticket["category"]:
                continue
            display = cat_data.get("display_name", key.title())
            options.append(discord.SelectOption(label=display, value=key, description=f"Move to {display}"))

        if not options:
            try:
                await interaction.response.send_message(
                    msg.get("move.no_categories"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        view = MoveCategoryView(
            ticket_id=ticket_id,
            old_category=ticket["category"],
            options=options,
        )
        try:
            await interaction.response.send_message(
                f"Select a category to move **{ticket_id}** to:",
                view=view,
                ephemeral=True,
            )
        except Exception:
            pass

    @discord.ui.button(
        label="Reopen",
        style=discord.ButtonStyle.success,
        custom_id="active_reopen",
        row=2,
    )
    async def reopen_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        bot = interaction.client
        msg = bot.messages
        ticket_service = bot.ticket_service
        permission_service = bot.permission_service
        config_service = bot.config_service
        audit_service = bot.audit_service

        ticket_id = _extract_ticket_id(interaction)
        if not ticket_id:
            try:
                await interaction.response.send_message(
                    msg.get("errors.not_identified"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        ticket = await ticket_service.get_ticket(ticket_id)
        if not ticket:
            try:
                await interaction.response.send_message(
                    msg.get("errors.ticket_not_found"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        if ticket["status"] == "OPEN" or ticket["status"] == "CLAIMED" or ticket["status"] == "PENDING":
            try:
                await interaction.response.send_message(
                    f"Ticket **{ticket_id}** is already active (status: **{ticket['status']}**).",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        if ticket["status"] == "DELETED":
            try:
                await interaction.response.send_message(
                    f"Cannot reopen ticket **{ticket_id}**: it has been deleted.",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        has_perm = await permission_service.check(
            interaction.user, "ticket_reopen", ticket["category"]
        )
        if not has_perm:
            try:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_reopen"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        try:
            await interaction.response.defer()
        except Exception:
            pass

        try:
            updated_ticket = await ticket_service.reopen_ticket(ticket_id)
        except Exception as e:
            try:
                await interaction.followup.send(f"Failed to reopen ticket: {e}", ephemeral=True)
            except Exception:
                pass
            return

        cat_config = config_service.get_category(ticket["category"])
        if cat_config and interaction.guild and interaction.channel:
            open_category_id = cat_config.get("open_category_id")
            if open_category_id:
                open_category = interaction.guild.get_channel(open_category_id)
                if open_category and isinstance(open_category, discord.CategoryChannel):
                    try:
                        num = ticket_id.split("-")[-1]
                        open_name = f"{ticket['category']}-{num}"
                        staff_role_ids = cat_config.get("staff_roles", [])
                        new_overwrites = {
                            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                            interaction.guild.me: discord.PermissionOverwrite(
                                view_channel=True, send_messages=True,
                                read_message_history=True, manage_channels=True, attach_files=True,
                            ),
                        }
                        ticket_user = interaction.guild.get_member(ticket["user_id"])
                        if ticket_user:
                            new_overwrites[ticket_user] = discord.PermissionOverwrite(
                                view_channel=True, send_messages=True,
                                read_message_history=True, attach_files=True,
                            )
                        for role_id in staff_role_ids:
                            role = interaction.guild.get_role(role_id)
                            if role:
                                new_overwrites[role] = discord.PermissionOverwrite(
                                    view_channel=True, send_messages=True,
                                    read_message_history=True, attach_files=True,
                                )
                        ok = await safe_channel_edit(
                            interaction.channel,
                            name=open_name,
                            category=open_category,
                            overwrites=new_overwrites,
                            topic=f"Ticket {ticket_id} | {ticket['category'].title()} | User: {ticket['user_id']}",
                        )
                        if not ok:
                            logger.error("Failed to reopen channel for ticket %s after retries", ticket_id)
                    except Exception as e:
                        logger.error("Failed to reopen channel: %s", e)

        member = interaction.guild.get_member(ticket["user_id"]) if interaction.guild else None
        if member:
            await msg.send_dual_dm(
                member,
                key="dm.ticket_reopened",
                color=3066993,
                fields=[
                    (msg.get("dm.field_category"), ticket["category"].title(), True),
                ],
                fa_fields=[
                    (msg.get_persian("dm.field_category") or msg.get("dm.field_category"), ticket["category"].title(), True),
                ],
                ticket_id=ticket_id,
            )

        await audit_service.log(
            action="TICKET_REOPENED",
            actor_id=interaction.user.id,
            actor_name=str(interaction.user),
            ticket_id=ticket_id,
            category=ticket["category"],
            details=f"Ticket reopened by {interaction.user}.",
        )

        try:
            await interaction.followup.send(
                f"{interaction.user.mention} has reopened ticket **{ticket_id}**.",
                ephemeral=False,
            )
        except Exception:
            pass


class MoveCategoryView(discord.ui.View):
    """Ephemeral view for selecting a target category when moving a ticket."""

    def __init__(self, ticket_id: str, old_category: str, options: list[discord.SelectOption]) -> None:
        super().__init__(timeout=60)
        self.ticket_id = ticket_id
        self.old_category = old_category
        self.select.options = options

    @discord.ui.select(
        placeholder="Select target category...",
        min_values=1,
        max_values=1,
    )
    async def select(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
        bot = interaction.client
        msg = bot.messages
        ticket_service = bot.ticket_service
        config_service = bot.config_service
        audit_service = bot.audit_service

        new_category = select.values[0]
        if new_category == self.old_category:
            try:
                await interaction.response.send_message(
                    msg.get("move.already_in_category"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        try:
            await interaction.response.defer()
        except Exception:
            pass

        try:
            updated_ticket = await ticket_service.move_ticket(self.ticket_id, new_category)
        except Exception as e:
            try:
                await interaction.followup.send(
                    f"Failed to move ticket: {e}",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        new_cat_config = config_service.get_category(new_category)
        old_cat_config = config_service.get_category(self.old_category)
        guild = interaction.guild

        if updated_ticket["status"] == "PENDING":
            pending_msg_id = updated_ticket.get("pending_message_id")
            if pending_msg_id and guild:
                old_pending_channel_id = old_cat_config.get("pending_channel_id") if old_cat_config else None
                if old_pending_channel_id:
                    old_pending_channel = guild.get_channel(old_pending_channel_id)
                    if old_pending_channel:
                        try:
                            old_msg = await old_pending_channel.fetch_message(pending_msg_id)
                            await old_msg.delete()
                        except Exception:
                            pass

            new_pending_channel_id = new_cat_config.get("pending_channel_id") if new_cat_config else None
            if new_pending_channel_id and guild:
                new_pending_channel = guild.get_channel(new_pending_channel_id)
                if new_pending_channel:
                    from utils.formatting import make_pending_embed
                    embed = make_pending_embed(updated_ticket, config_service.get_ui())
                    new_view = PendingTicketView(ticket_id=self.ticket_id, category=new_category)
                    reasons = new_cat_config.get("quick_close_reasons", [])
                    if reasons:
                        options = []
                        for i, r in enumerate(reasons[:25]):
                            label = r.get("label", f"Template {i+1}")[:25]
                            desc = r.get("message", "")[:100]
                            options.append(discord.SelectOption(label=label, value=str(i), description=desc))
                        new_view.template_select.options = options
                    else:
                        new_view._children.remove(new_view.template_select)
                    try:
                        new_msg = await new_pending_channel.send(embed=embed, view=new_view)
                        await ticket_service.store_pending_message(self.ticket_id, new_msg.id)
                    except Exception as e:
                        logger.error("Failed to send new pending message: %s", e)

        elif updated_ticket.get("discord_channel_id") and guild:
            channel = guild.get_channel(updated_ticket["discord_channel_id"])
            if channel and isinstance(channel, discord.TextChannel):
                new_open_category_id = new_cat_config.get("open_category_id") if new_cat_config else None
                if new_open_category_id:
                    new_open_category = guild.get_channel(new_open_category_id)
                    if new_open_category and isinstance(new_open_category, discord.CategoryChannel):
                        user = guild.get_member(updated_ticket["user_id"])
                        new_staff_role_ids = new_cat_config.get("staff_roles", []) if new_cat_config else []

                        new_overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=False),
                            guild.me: discord.PermissionOverwrite(
                                view_channel=True, send_messages=True,
                                read_message_history=True, manage_channels=True, attach_files=True,
                            ),
                        }
                        if user:
                            new_overwrites[user] = discord.PermissionOverwrite(
                                view_channel=True, send_messages=True,
                                read_message_history=True, attach_files=True,
                            )
                        for role_id in new_staff_role_ids:
                            role = guild.get_role(role_id)
                            if role:
                                new_overwrites[role] = discord.PermissionOverwrite(
                                    view_channel=True, send_messages=True,
                                    read_message_history=True, attach_files=True,
                                )

                        num = self.ticket_id.split("-")[-1]
                        new_name = f"{new_category}-{num}"
                        try:
                            await channel.edit(
                                name=new_name,
                                category=new_open_category,
                                overwrites=new_overwrites,
                                topic=f"Ticket {self.ticket_id} | {new_category.title()} | User: {updated_ticket['user_id']}",
                            )
                        except Exception as e:
                            logger.error("Failed to move channel: %s", e)

        dm_settings = config_service.get_dm_settings()
        if dm_settings.get("enabled") and guild:
            member = guild.get_member(updated_ticket["user_id"])
            if member:
                await msg.send_dual_dm(
                    member,
                    key="dm.ticket_moved",
                    color=5814783,
                    ticket_id=self.ticket_id,
                    category=new_category.title(),
                )

        await audit_service.log(
            action="TICKET_MOVED",
            actor_id=interaction.user.id,
            actor_name=str(interaction.user),
            ticket_id=self.ticket_id,
            category=new_category,
            details=f"Ticket moved from {self.old_category} to {new_category} by {interaction.user}.",
        )

        try:
            await interaction.followup.send(
                f"{interaction.user.mention} has moved ticket **{self.ticket_id}** from **{self.old_category}** to **{new_category}**.",
                ephemeral=False,
            )
        except Exception:
            pass
