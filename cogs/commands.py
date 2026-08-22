from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.formatting import format_duration

logger = logging.getLogger("ticket_bot.cogs.commands")


class CommandsCog(commands.Cog):
    """Command listing and admin statistics commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.ticket_group = app_commands.Group(
            name="ticket",
            description=self.bot.messages.get("cog.ticket_commands"),
        )
        self._register_ticket_commands()

    @property
    def statistics_service(self):
        return self.bot.statistics_service

    @property
    def permission_service(self):
        return self.bot.permission_service

    @property
    def config_service(self):
        return self.bot.config_service

    @property
    def ticket_service(self):
        return self.bot.ticket_service

    @property
    def audit_service(self):
        return self.bot.audit_service

    def _register_ticket_commands(self) -> None:
        @self.ticket_group.command(name="ban", description="Ban a user from creating tickets")
        @app_commands.describe(
            user="The user to ban",
            duration="Ban duration (e.g. 3d, 7d, 14d, 30d, permanent). If omitted, uses offense-based escalation.",
            reason="Reason for the ban",
        )
        async def ticket_ban(
            interaction: discord.Interaction,
            user: discord.Member,
            duration: Optional[str] = None,
            reason: Optional[str] = None,
        ) -> None:
            try:
                msg = interaction.client.messages
                if not interaction.user.guild_permissions.administrator:
                    has_perm = await self.permission_service.check(
                        interaction.user, "ticket_ban", ""
                    )
                    if not has_perm:
                        await interaction.response.send_message(
                            msg.get("permissions.no_permission_ban"),
                            ephemeral=True,
                        )
                        return

                if user.id == interaction.user.id:
                    await interaction.response.send_message(
                        msg.get("ban.cannot_ban_self"),
                        ephemeral=True,
                    )
                    return

                if user.guild_permissions.administrator:
                    await interaction.response.send_message(
                        msg.get("ban.cannot_ban_admin"),
                        ephemeral=True,
                    )
                    return

                existing = await self.ticket_service.check_user_banned(user.id)
                if existing:
                    await interaction.response.send_message(
                        msg.get("ban.already_banned"),
                        ephemeral=True,
                    )
                    return

                await interaction.response.defer()

                ban_info = await self.ticket_service.ban_user(
                    user_id=user.id,
                    banned_by=interaction.user.id,
                    reason=reason or "",
                    duration_str=duration,
                    config=self.config_service._config,
                    count_offense=duration is None,
                )

                dm_fields = [
                    (msg.get("dm.field_duration"), ban_info["display_duration"], True),
                    (msg.get("dm.field_offense"), f"#{ban_info['offense_number']}", True),
                ]
                fa_dm_fields = [
                    (msg.get_persian("dm.field_duration") or msg.get("dm.field_duration"), ban_info["display_duration"], True),
                    (msg.get_persian("dm.field_offense") or msg.get("dm.field_offense"), f"#{ban_info['offense_number']}", True),
                ]
                if reason:
                    dm_fields.append((msg.get("dm.field_reason"), reason[:1024], False))
                    fa_dm_fields.append((msg.get_persian("dm.field_reason") or msg.get("dm.field_reason"), reason[:1024], False))
                if ban_info.get("expires_at"):
                    from utils import timezone as tz
                    exp_dt = datetime.fromisoformat(ban_info["expires_at"])
                    expires_str = f"<t:{int(exp_dt.timestamp())}:R>"
                    dm_fields.append((msg.get("dm.field_expires"), expires_str, True))
                    fa_dm_fields.append((msg.get_persian("dm.field_expires") or msg.get("dm.field_expires"), expires_str, True))
                dm_sent = await msg.send_dual_dm(
                    user,
                    key="dm.ban_notice",
                    color=15158332,
                    fields=dm_fields,
                    fa_fields=fa_dm_fields,
                    guild=interaction.guild.name,
                )

                dm_note = "" if dm_sent else msg.get("response.dm_note")

                await self.audit_service.log(
                    action="USER_BANNED",
                    actor_id=interaction.user.id,
                    actor_name=str(interaction.user),
                    target_id=user.id,
                    target_name=str(user),
                    details=f"Banned {user} from creating tickets for {ban_info['display_duration']} "
                            f"(offense #{ban_info['offense_number']}). Reason: {reason or 'N/A'}.{dm_note}",
                )

                await interaction.followup.send(
                    msg.get(
                        "ban.ban_success",
                        user_id=user.id,
                        duration=ban_info["display_duration"],
                        offense=ban_info["offense_number"],
                        reason=reason or "*No reason provided*",
                        dm_note=dm_note,
                    ),
                    ephemeral=True,
                )

            except Exception as e:
                logger.error("Error in /ticket ban: %s", e)
                if not interaction.response.is_done():
                    try:
                        await interaction.followup.send(
                            msg.get("ban.ban_failed", error=e),
                            ephemeral=True,
                        )
                    except Exception:
                        pass

        @self.ticket_group.command(name="unban", description="Unban a user from creating tickets")
        @app_commands.describe(user="The user to unban")
        async def ticket_unban(
            interaction: discord.Interaction,
            user: discord.Member,
        ) -> None:
            try:
                msg = interaction.client.messages
                if not interaction.user.guild_permissions.administrator:
                    has_perm = await self.permission_service.check(
                        interaction.user, "ticket_ban", ""
                    )
                    if not has_perm:
                        await interaction.response.send_message(
                            msg.get("ban_commands.unban_no_permission"),
                            ephemeral=True,
                        )
                        return

                existing = await self.ticket_service.check_user_banned(user.id)
                if not existing:
                    await interaction.response.send_message(
                        msg.get("ban_commands.not_banned", user=user),
                        ephemeral=True,
                    )
                    return

                removed = await self.ticket_service.unban_user(user.id)

                if removed:
                    dm_sent = await msg.send_dual_dm(
                        user,
                        key="dm.ban_lifted",
                        color=3066993,
                        guild=interaction.guild.name,
                    )

                    dm_note = "" if dm_sent else msg.get("response.dm_note")

                    await self.audit_service.log(
                        action="USER_UNBANNED",
                        actor_id=interaction.user.id,
                        actor_name=str(interaction.user),
                        target_id=user.id,
                        target_name=str(user),
                        details=f"Unbanned {user} from creating tickets.{dm_note}",
                    )

                    await interaction.response.send_message(
                        msg.get("ban_commands.unban_success", user=user) + dm_note,
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        msg.get("ban_commands.unban_failed", user=user),
                        ephemeral=True,
                    )

            except Exception as e:
                logger.error("Error in /ticket unban: %s", e)
                if not interaction.response.is_done():
                    try:
                        await interaction.followup.send(
                            msg.get("ban_commands.unban_error", error=e),
                            ephemeral=True,
                        )
                    except Exception:
                        pass

        @self.ticket_group.command(name="baninfo", description="Check ban status for a user")
        @app_commands.describe(user="The user to check")
        async def ticket_baninfo(
            interaction: discord.Interaction,
            user: discord.User,
        ) -> None:
            try:
                msg = interaction.client.messages
                ban_info = await self.ticket_service.check_user_banned(user.id)
                if not ban_info:
                    await interaction.response.send_message(
                        msg.get("ban_commands.not_banned", user=user),
                        ephemeral=True,
                    )
                    return

                from utils import timezone
                now = timezone.now()
                expires_at = ban_info.get("expires_at")
                permanent = ban_info.get("expires_at") is None

                embed = discord.Embed(
                    title=msg.get("ban_commands.baninfo_title"),
                    description=msg.get("ban_commands.baninfo_description", user=user),
                    color=15158332,
                )
                embed.set_thumbnail(url=user.display_avatar.url)

                embed.add_field(
                    name=msg.get("formatting.offense"),
                    value=f"#{ban_info.get('offense_number', '?')}",
                    inline=True,
                )

                banned_at = ban_info.get("banned_at", "")
                if banned_at:
                    try:
                        banned_dt = datetime.fromisoformat(banned_at)
                        ts = int(banned_dt.timestamp())
                        embed.add_field(name=msg.get("formatting.banned_at"), value=f"<t:{ts}:F>", inline=True)
                    except Exception:
                        embed.add_field(name=msg.get("formatting.banned_at"), value=banned_at, inline=True)

                banned_by_id = ban_info.get("banned_by", 0)
                embed.add_field(name=msg.get("formatting.banned_by"), value=f"<@{banned_by_id}>", inline=True)

                reason = ban_info.get("reason", "")
                embed.add_field(name=msg.get("formatting.reason"), value=reason or "*No reason provided*", inline=False)

                if permanent:
                    embed.add_field(name=msg.get("formatting.duration"), value=f"**{msg.get('formatting.permanent')}**", inline=True)
                    embed.add_field(name=msg.get("formatting.time_left"), value=msg.get("formatting.forever"), inline=True)
                else:
                    try:
                        exp_dt = datetime.fromisoformat(expires_at)
                        exp_ts = int(exp_dt.timestamp())
                        embed.add_field(name=msg.get("formatting.expires"), value=f"<t:{exp_ts}:F>", inline=True)
                        remaining = exp_dt - now
                        if remaining.total_seconds() <= 0:
                            embed.add_field(name=msg.get("formatting.time_left"), value=msg.get("formatting.expired"), inline=True)
                        else:
                            days = remaining.days
                            hours, remainder = divmod(remaining.seconds, 3600)
                            mins = remainder // 60
                            parts = []
                            if days > 0:
                                parts.append(f"{days}d")
                            if hours > 0:
                                parts.append(f"{hours}h")
                            if mins > 0:
                                parts.append(f"{mins}m")
                            if not parts:
                                parts.append("<1m")
                            embed.add_field(name=msg.get("formatting.time_left"), value=" ".join(parts), inline=True)
                    except Exception:
                        embed.add_field(name=msg.get("formatting.expires"), value=expires_at or "Unknown", inline=True)

                embed.set_footer(text=msg.embed_footer("dm.ban_notice"))
                await interaction.response.send_message(embed=embed, ephemeral=True)

            except Exception as e:
                logger.error("Error in /ticket baninfo: %s", e)
                if not interaction.response.is_done():
                    try:
                        await interaction.response.send_message(
                            msg.get("ban_commands.ban_failed", error=e),
                            ephemeral=True,
                        )
                    except Exception:
                        pass

        @self.ticket_group.command(name="banlist", description="List all users banned from creating tickets")
        async def ticket_banlist(
            interaction: discord.Interaction,
        ) -> None:
            try:
                msg = interaction.client.messages
                if not interaction.user.guild_permissions.administrator:
                    has_perm = await self.permission_service.check(
                        interaction.user, "ticket_ban", ""
                    )
                    if not has_perm:
                        await interaction.response.send_message(
                            msg.get("ban_commands.banlist_no_permission"),
                            ephemeral=True,
                        )
                        return

                bans = await self.ticket_service.get_active_bans()
                if not bans:
                    await interaction.response.send_message(
                        msg.get("ban_commands.banlist_empty"),
                        ephemeral=True,
                    )
                    return

                from utils import timezone
                now = timezone.now()

                embed = discord.Embed(
                    title=msg.get("ban_commands.banlist_title"),
                    description=msg.get("ban_commands.banlist_description", count=len(bans)),
                    color=15158332,
                )

                for ban in bans:
                    user_id = ban["user_id"]
                    offense = ban.get("offense_number", "?")
                    reason = ban.get("reason", "N/A")
                    banned_by = ban.get("banned_by", 0)
                    expires_at = ban.get("expires_at")
                    permanent = expires_at is None

                    if permanent:
                        duration_text = msg.get("formatting.permanent")
                        time_left = msg.get("formatting.forever")
                    else:
                        try:
                            exp_dt = datetime.fromisoformat(expires_at)
                            duration_text = f"<t:{int(exp_dt.timestamp())}:R>"
                            remaining = exp_dt - now
                            if remaining.total_seconds() <= 0:
                                time_left = msg.get("formatting.expired")
                            else:
                                days = remaining.days
                                hours, remainder = divmod(remaining.seconds, 3600)
                                mins = remainder // 60
                            parts = []
                            if days > 0:
                                parts.append(f"{days}d")
                            if hours > 0:
                                parts.append(f"{hours}h")
                            if mins > 0:
                                parts.append(f"{mins}m")
                            if not parts:
                                parts.append("<1m")
                            time_left = " ".join(parts)
                        except Exception:
                            duration_text = expires_at or "Unknown"
                            time_left = "Unknown"

                    value_lines = [
                        f"**User:** <@{user_id}>",
                        f"**Offense:** #{offense}",
                        f"**Reason:** {reason}",
                        f"**Banned By:** <@{banned_by}>",
                        f"**Expires:** {duration_text}",
                        f"**Time Left:** {time_left}",
                    ]

                    embed.add_field(
                        name=msg.get("formatting.name_user", user_id=user_id),
                        value="\n".join(value_lines),
                        inline=False,
                    )

                embed.set_footer(text=msg.embed_footer("dm.ban_notice"))
                await interaction.response.send_message(embed=embed, ephemeral=True)

            except Exception as e:
                logger.error("Error in /ticket banlist: %s", e)
                if not interaction.response.is_done():
                    try:
                        await interaction.response.send_message(
                            msg.get("ban_commands.banlist_failed", error=e),
                            ephemeral=True,
                        )
                    except Exception:
                        pass

        @self.ticket_group.command(name="move", description="Move a ticket from one category to another")
        @app_commands.describe(
            ticket_id="The ticket to move (e.g. general-0003)",
            category="The current category",
            to_category="The destination category",
        )
        @app_commands.choices(category=[
            app_commands.Choice(name="General", value="general"),
            app_commands.Choice(name="Scoring", value="scoring"),
            app_commands.Choice(name="Appeal", value="appeal"),
            app_commands.Choice(name="Other", value="other"),
        ])
        @app_commands.choices(to_category=[
            app_commands.Choice(name="General", value="general"),
            app_commands.Choice(name="Scoring", value="scoring"),
            app_commands.Choice(name="Appeal", value="appeal"),
            app_commands.Choice(name="Other", value="other"),
        ])
        async def ticket_move(
            interaction: discord.Interaction,
            ticket_id: str,
            category: app_commands.Choice[str],
            to_category: app_commands.Choice[str],
        ) -> None:
            try:
                await interaction.response.defer(ephemeral=True)

                if not interaction.user.guild_permissions.administrator:
                    has_perm = await self.permission_service.check(
                        interaction.user, "ticket_move", ""
                    )
                    if not has_perm:
                        await interaction.followup.send(
                            msg.get("move.no_permission"),
                            ephemeral=True,
                        )
                        return

                old_category = category.value
                new_category = to_category.value
                categories = self.config_service.get_categories()

                if old_category not in categories:
                    await interaction.followup.send(
                        msg.get("move.invalid_source", category=old_category),
                        ephemeral=True,
                    )
                    return

                if new_category not in categories:
                    await interaction.followup.send(
                        msg.get("move.invalid_destination", category=new_category),
                        ephemeral=True,
                    )
                    return

                if old_category == new_category:
                    await interaction.followup.send(
                        msg.get("move.same_category", category=new_category),
                        ephemeral=True,
                    )
                    return

                try:
                    ticket = await self.ticket_service.get_ticket(ticket_id)
                except Exception:
                    await interaction.followup.send(
                        msg.get("move.ticket_not_found", ticket_id=ticket_id),
                        ephemeral=True,
                    )
                    return

                if ticket["category"] != old_category:
                    await interaction.followup.send(
                        msg.get("move.wrong_category", ticket_id=ticket_id, category=ticket["category"], old_category=old_category),
                        ephemeral=True,
                    )
                    return

                if ticket["status"] in ("CLOSED", "DELETED"):
                    await interaction.followup.send(
                        msg.get("move.cannot_move_closed", ticket_id=ticket_id, status=ticket["status"]),
                        ephemeral=True,
                    )
                    return

                updated_ticket = await self.ticket_service.move_ticket(ticket_id, new_category)

                new_cat_config = self.config_service.get_category(new_category)
                old_cat_config = self.config_service.get_category(old_category)

                if ticket["status"] == "PENDING":
                    pending_msg_id = ticket.get("pending_message_id")
                    if pending_msg_id and interaction.guild:
                        old_pending_channel_id = old_cat_config.get("pending_channel_id") if old_cat_config else None
                        if old_pending_channel_id:
                            old_pending_channel = interaction.guild.get_channel(old_pending_channel_id)
                            if old_pending_channel:
                                try:
                                    old_msg = await old_pending_channel.fetch_message(pending_msg_id)
                                    await old_msg.delete()
                                except Exception:
                                    pass

                    new_pending_channel_id = new_cat_config.get("pending_channel_id") if new_cat_config else None
                    if new_pending_channel_id and interaction.guild:
                        new_pending_channel = interaction.guild.get_channel(new_pending_channel_id)
                        if new_pending_channel:
                            from utils.formatting import make_pending_embed
                            from ui.ticket_views import PendingTicketView
                            embed = make_pending_embed(updated_ticket, self.config_service.get_ui())
                            view = PendingTicketView(ticket_id=ticket_id, category=new_category)
                            reasons = new_cat_config.get("quick_close_reasons", [])
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
                                new_msg = await new_pending_channel.send(embed=embed, view=view)
                                await self.ticket_service.store_pending_message(ticket_id, new_msg.id)
                            except Exception as e:
                                logger.error("Failed to send new pending message: %s", e)

                elif ticket.get("discord_channel_id") and interaction.guild:
                    channel = interaction.guild.get_channel(ticket["discord_channel_id"])
                    if channel and isinstance(channel, discord.TextChannel):
                        new_open_category_id = new_cat_config.get("open_category_id") if new_cat_config else None
                        if new_open_category_id:
                            new_open_category = interaction.guild.get_channel(new_open_category_id)
                            if new_open_category and isinstance(new_open_category, discord.CategoryChannel):
                                user = interaction.guild.get_member(updated_ticket["user_id"])
                                new_staff_role_ids = new_cat_config.get("staff_roles", []) if new_cat_config else []

                                new_overwrites = {
                                    interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                                    interaction.guild.me: discord.PermissionOverwrite(
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
                                    role = interaction.guild.get_role(role_id)
                                    if role:
                                        new_overwrites[role] = discord.PermissionOverwrite(
                                            view_channel=True, send_messages=True,
                                            read_message_history=True, attach_files=True,
                                        )

                                num = ticket_id.split("-")[-1]
                                new_name = f"{new_category}-{num}"
                                try:
                                    await channel.edit(
                                        name=new_name,
                                        category=new_open_category,
                                        overwrites=new_overwrites,
                                        topic=f"Ticket {ticket_id} | {new_category.title()} | User: {updated_ticket['user_id']}",
                                    )
                                except Exception as e:
                                    logger.error("Failed to move channel: %s", e)

                dm_settings = self.config_service.get_dm_settings()
                if dm_settings.get("enabled"):
                    member = interaction.guild.get_member(updated_ticket["user_id"]) if interaction.guild else None
                    if member:
                        try:
                            await msg.send_dual_dm(
                                member,
                                key="dm.ticket_moved",
                                color=5814783,
                                ticket_id=ticket_id,
                                category=new_category.title(),
                            )
                        except Exception:
                            pass

                await self.audit_service.log(
                    action="TICKET_MOVED",
                    actor_id=interaction.user.id,
                    actor_name=str(interaction.user),
                    ticket_id=ticket_id,
                    category=new_category,
                    details=f"Ticket moved from {old_category} to {new_category} by {interaction.user}.",
                )

                await interaction.followup.send(
                    msg.get("move.success", ticket_id=ticket_id, old_category=old_category, new_category=new_category),
                    ephemeral=True,
                )

            except Exception as e:
                logger.error("Error in /ticket move: %s", e)
                if not interaction.response.is_done():
                    try:
                        await interaction.followup.send(
                            msg.get("move.move_failed", error=e),
                            ephemeral=True,
                        )
                    except Exception:
                        pass

    @app_commands.command(name="commands", description="View all available bot commands")
    async def commands_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_admin_command"),
                    ephemeral=True,
                )
                return

            view = CommandsNavigationView(self.bot)
            embed = view.get_user_commands_embed()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error("Error in /commands: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        msg.get("errors.try_again"),
                        ephemeral=True,
                    )
                except Exception:
                    pass

    def _has_root_role(self, member: discord.Member) -> bool:
        """Check if the member has any of the configured root roles."""
        root_role_ids = self.config_service.get("root_role_ids", [])
        if not root_role_ids:
            return False
        member_role_ids = {r.id for r in member.roles}
        return bool(member_role_ids & set(root_role_ids))

    @app_commands.command(name="purge", description="Delete all tickets (channels + DB records)")
    async def purge_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            if not self._has_root_role(interaction.user):
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_purge"),
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                msg.get("purge.confirm"),
                ephemeral=True,
            )

            def check(m: discord.Message) -> bool:
                return m.author.id == interaction.user.id and m.channel == interaction.channel

            try:
                confirm_msg = await self.bot.wait_for("message", check=check, timeout=30.0)
                if confirm_msg.content.strip() != "CONFIRM PURGE":
                    await interaction.followup.send(msg.get("purge.cancelled"), ephemeral=True)
                    return
                try:
                    await confirm_msg.delete()
                except Exception:
                    pass
            except Exception:
                await interaction.followup.send(msg.get("purge.cancelled_timeout"), ephemeral=True)
                return

            await interaction.followup.send(msg.get("purge.purging"), ephemeral=True)

            all_tickets = await self.bot.db.get_all_tickets()
            deleted_count = 0
            channel_errors = 0

            for ticket in all_tickets:
                channel_id = ticket.get("discord_channel_id")
                if channel_id and interaction.guild:
                    channel = interaction.guild.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.delete(reason="Ticket purge")
                        except Exception:
                            channel_errors += 1

                pending_msg_id = ticket.get("pending_message_id")
                if pending_msg_id and interaction.guild:
                    cat_config = self.config_service.get_category(ticket["category"])
                    if cat_config:
                        pending_channel = interaction.guild.get_channel(cat_config.get("pending_channel_id", 0))
                        if pending_channel:
                            try:
                                pending_msg = await pending_channel.fetch_message(pending_msg_id)
                                await pending_msg.delete()
                            except Exception:
                                pass

                try:
                    await self.ticket_service.delete_ticket(ticket["ticket_id"])
                    deleted_count += 1
                except Exception:
                    pass

            await self.audit_service.log(
                action="TICKETS_PURGED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                details=f"Purged {deleted_count} tickets. {channel_errors} channel deletion errors.",
            )

            await interaction.followup.send(
                msg.get("purge.complete", count=deleted_count)
                + (f"\n⚠️ {channel_errors} channels could not be deleted." if channel_errors else ""),
                ephemeral=True,
            )

        except Exception as e:
            logger.error("Error in /purge: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.followup.send(msg.get("purge.purge_failed", error=e), ephemeral=True)
                except Exception:
                    pass

    @app_commands.command(name="purgeall", description="Delete the entire tickets database")
    async def purgeall_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            if not self._has_root_role(interaction.user):
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_purge"),
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                msg.get("purgeall.confirm"),
                ephemeral=True,
            )

            def check(m: discord.Message) -> bool:
                return m.author.id == interaction.user.id and m.channel == interaction.channel

            try:
                confirm_msg = await self.bot.wait_for("message", check=check, timeout=30.0)
                if confirm_msg.content.strip() != "CONFIRM PURGEALL":
                    await interaction.followup.send(msg.get("purgeall.cancelled"), ephemeral=True)
                    return
                try:
                    await confirm_msg.delete()
                except Exception:
                    pass
            except Exception:
                await interaction.followup.send(msg.get("purgeall.cancelled_timeout"), ephemeral=True)
                return

            await interaction.followup.send(msg.get("purgeall.deleting"), ephemeral=True)

            all_tickets = await self.bot.db.get_all_tickets()
            channel_errors = 0

            for ticket in all_tickets:
                channel_id = ticket.get("discord_channel_id")
                if channel_id and interaction.guild:
                    channel = interaction.guild.get_channel(channel_id)
                    if channel:
                        try:
                            await channel.delete(reason="Ticket purgeall")
                        except Exception:
                            channel_errors += 1

                pending_msg_id = ticket.get("pending_message_id")
                if pending_msg_id and interaction.guild:
                    cat_config = self.config_service.get_category(ticket["category"])
                    if cat_config:
                        pending_channel = interaction.guild.get_channel(cat_config.get("pending_channel_id", 0))
                        if pending_channel:
                            try:
                                purge_msg = await pending_channel.fetch_message(pending_msg_id)
                                await purge_msg.delete()
                            except Exception:
                                pass

            import os
            db_path = self.bot.db.db_path
            await self.bot.db.close()

            try:
                os.remove(db_path)
                db_deleted = True
            except Exception as e:
                logger.error("Failed to delete database file: %s", e)
                db_deleted = False

            await self.audit_service.log(
                action="DATABASE_PURGED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                details=f"Purged entire database ({len(all_tickets)} tickets, {channel_errors} channel errors).",
            )

            if db_deleted:
                await interaction.followup.send(
                    msg.get("purgeall.complete", count=len(all_tickets)),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    msg.get("purgeall.db_delete_failed"),
                    ephemeral=True,
                )

        except Exception as e:
            logger.error("Error in /purgeall: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.followup.send(msg.get("purgeall.purge_failed", error=e), ephemeral=True)
                except Exception:
                    pass

    @app_commands.command(name="adminstats", description="View administrator statistics dashboard")
    async def adminstats_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            if not interaction.user.guild_permissions.administrator:
                has_perm = await self.permission_service.check(
                    interaction.user, "adminstats", ""
                )
                if not has_perm:
                    await interaction.response.send_message(
                        msg.get("permissions.no_permission_admin_stats"),
                        ephemeral=True,
                    )
                    return

            await interaction.response.defer()

            stats = await self.statistics_service.get_server_stats()
            cat_stats = await self.statistics_service.get_category_stats()

            embed = discord.Embed(
                title=msg.get("admin.admin_stats_title"),
                color=5814783,
            )

            embed.add_field(name=msg.get("admin.total_tickets"), value=str(stats["total"]), inline=True)
            embed.add_field(name=msg.get("admin.today"), value=str(stats["today"]), inline=True)
            embed.add_field(name=msg.get("admin.this_week"), value=str(stats["this_week"]), inline=True)
            embed.add_field(name=msg.get("admin.this_month"), value=str(stats["this_month"]), inline=True)
            embed.add_field(name=msg.get("admin.pending"), value=str(stats["pending"]), inline=True)
            embed.add_field(name=msg.get("admin.open"), value=str(stats["open"]), inline=True)
            embed.add_field(name=msg.get("admin.claimed"), value=str(stats["claimed"]), inline=True)
            embed.add_field(name=msg.get("admin.responded"), value=str(stats["responded"]), inline=True)
            embed.add_field(name=msg.get("admin.closed"), value=str(stats["closed"]), inline=True)
            embed.add_field(name=msg.get("admin.deleted"), value=str(stats["deleted"]), inline=True)

            if stats.get("avg_response_time"):
                embed.add_field(
                    name=msg.get("admin.avg_response_time"),
                    value=format_duration(stats["avg_response_time"]),
                    inline=True,
                )
            if stats.get("avg_resolution_time"):
                embed.add_field(
                    name=msg.get("admin.avg_resolution_time"),
                    value=format_duration(stats["avg_resolution_time"]),
                    inline=True,
                )

            if stats.get("category_distribution"):
                cat_text = "\n".join(
                    f"**{cat.title()}:** {count}"
                    for cat, count in stats["category_distribution"].items()
                )
                embed.add_field(name=msg.get("admin.category_distribution"), value=cat_text, inline=False)

            if stats.get("staff_responds"):
                staff_text = "\n".join(
                    f"<@{sid}>: {count} responses"
                    for sid, count in sorted(
                        stats["staff_responds"].items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:10]
                )
                embed.add_field(name=msg.get("admin.top_responders"), value=staff_text or msg.get("admin.none"), inline=False)

            if stats.get("staff_claims"):
                claims_by_total: dict[str, int] = {}
                for sid, actions in stats["staff_claims"].items():
                    claims_by_total[sid] = sum(
                        v for k, v in actions.items() if k in ("CLAIM", "OVERRIDE")
                    )
                claims_text = "\n".join(
                    f"<@{sid}>: {count} claims"
                    for sid, count in sorted(
                        claims_by_total.items(),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:10]
                )
                embed.add_field(name=msg.get("admin.top_claimers"), value=claims_text or msg.get("admin.none"), inline=False)

            embed.set_footer(text=msg.get("commands.admin_stats_title"))
            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error("Error in /adminstats: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.followup.send(
                        msg.get("errors.try_again"),
                        ephemeral=True,
                    )
                except Exception:
                    pass


class CommandsNavigationView(discord.ui.View):
    """Navigation view for the /commands listing."""

    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(timeout=120)
        self.bot = bot
        self.current_page = "user"

    def get_user_commands_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="IRBW Bot Commands",
            description="Use the dropdown below to navigate command categories.",
            color=5814783,
        )
        embed.add_field(
            name="User Commands",
            value=(
                "`/status` - View your ticket statistics and recent history\n"
                "`/commands` - View all available commands\n"
            ),
            inline=False,
        )
        embed.set_footer(text="Page: User Commands")
        return embed

    def get_staff_commands_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="IRBW Bot Commands",
            description="Use the dropdown below to navigate command categories.",
            color=10181046,
        )
        embed.add_field(
            name="Staff Commands (in ticket channels)",
            value=(
                "`/response` - Send a response (auto-closes ticket)\n"
                "`/add` - Add a user or role to a ticket\n"
                "`/claim` - Claim the current ticket\n"
                "`/unclaim` - Unclaim the current ticket\n"
                "`/delete` - Delete the current ticket\n"
                "`/transcript` - Generate a transcript\n"
            ),
            inline=False,
        )
        embed.add_field(
            name="Pending Ticket Buttons",
            value=(
                "**Resolved** - Mark ticket as resolved and close\n"
                "**Ban** - Ban user (offense-based) and close\n"
                "**Close with Reason** - Close with explanation\n"
                "**Create Channel** - Open ticket channel"
            ),
            inline=False,
        )
        embed.add_field(
            name="Active Ticket Buttons",
            value=(
                "**Claim** | **Unclaim** | **Respond**\n"
                "**Close** | **Transcript** | **Delete**"
            ),
            inline=False,
        )
        embed.add_field(
            name="Ticket Management",
            value=(
                "`/ticket ban @user [duration] [reason]` - Ban user\n"
                "`/ticket unban @user` - Unban user\n"
                "`/ticket baninfo @user` - Check ban details\n"
                "`/ticket banlist` - List all banned users\n"
                "`/ticket move <id> <from> <to>` - Move ticket between categories\n"
                "Durations: `3d`, `7d`, `14d`, `30d`, `permanent`"
            ),
            inline=False,
        )
        embed.set_footer(text="Page: Staff Commands | Permission-controlled")
        return embed

    def get_admin_commands_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="IRBW Bot Commands",
            description="Use the dropdown below to navigate command categories.",
            color=16746496,
        )
        embed.add_field(
            name="Administration Commands",
            value=(
                "`/reload` - Hot-reload bot configuration\n"
                "`/adminhelp` - View complete admin documentation\n"
                "`/adminstats` - View admin statistics dashboard\n"
                "`/permission list` - List all configured permissions\n"
                "`/permission add` - Add a permission to a role\n"
                "`/permission remove` - Remove a permission from a role\n"
                "`/deploy` - Deploy or update the ticket panel\n"
                "`/ticket ban @user [duration] [reason]` - Ban user from tickets\n"
                "`/ticket unban @user` - Unban user from tickets\n"
                "`/ticket baninfo @user` - Check ban details\n"
                "`/ticket banlist` - List all banned users\n"
                "`/ticket move <id> <from> <to>` - Move ticket between categories\n"
                "`/purge` - Delete all tickets (root role)\n"
                "`/purgeall` - Delete tickets.db (root role)\n"
                "`/commands` - View all available commands\n"
            ),
            inline=False,
        )
        embed.set_footer(text="Page: Admin Commands | Administrator required")
        return embed

    @discord.ui.select(
        placeholder="Navigate command categories...",
        options=[
            discord.SelectOption(label="User Commands", value="user", emoji="\ud83d\udc64"),
            discord.SelectOption(label="Staff Commands", value="staff", emoji="\ud83d\udcbc"),
            discord.SelectOption(label="Admin Commands", value="admin", emoji="\u2699\ufe0f"),
        ],
        custom_id="commands_nav",
    )
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.Select) -> None:
        page = select.values[0]
        if page == "user":
            embed = self.get_user_commands_embed()
        elif page == "staff":
            embed = self.get_staff_commands_embed()
        else:
            embed = self.get_admin_commands_embed()
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception:
            pass


async def setup(bot: commands.Bot) -> None:
    cog = CommandsCog(bot)
    bot.tree.add_command(cog.ticket_group)
    await bot.add_cog(cog)
