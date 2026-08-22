from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.errors import TicketNotFoundError, PermissionDeniedError
from utils.formatting import make_ticket_embed
from ui.modals import ResponseModal

logger = logging.getLogger("ticket_bot.cogs.tickets")


class TicketsCog(commands.Cog):
    """Ticket management commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def config_service(self):
        return self.bot.config_service

    @property
    def ticket_service(self):
        return self.bot.ticket_service

    @property
    def permission_service(self):
        return self.bot.permission_service

    @property
    def audit_service(self):
        return self.bot.audit_service

    @property
    def transcript_service(self):
        return self.bot.transcript_service

    async def _get_ticket_from_context(self, interaction: discord.Interaction) -> dict:
        """Get the ticket associated with the current channel."""
        if not interaction.channel:
            raise TicketNotFoundError()
        ticket = await self.ticket_service.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            raise TicketNotFoundError()
        return ticket

    async def _check_permission(
        self, interaction: discord.Interaction, permission_key: str, category: str
    ) -> bool:
        """Check if the user has the required permission."""
        has_perm = await self.permission_service.check(
            interaction.user, permission_key, category
        )
        if not has_perm:
            raise PermissionDeniedError()
        return True

    @app_commands.command(name="response", description="Send a response to the current ticket")
    async def response_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            ticket = await self._get_ticket_from_context(interaction)
            await self._check_permission(interaction, "ticket_respond", ticket["category"])

            modal = ResponseModal(ticket_id=ticket["ticket_id"])
            await interaction.response.send_modal(modal)
        except TicketNotFoundError:
            await interaction.response.send_message(
                msg.get("permissions.not_ticket_channel"),
                ephemeral=True,
            )
        except PermissionDeniedError:
            await interaction.response.send_message(
                msg.get("permissions.no_permission_respond"),
                ephemeral=True,
            )
        except Exception as e:
            logger.error("Error in /response: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        msg.get("errors.try_again"),
                        ephemeral=True,
                    )
                except Exception:
                    pass

    @app_commands.command(name="add", description="Add a user or role to the current ticket")
    @app_commands.describe(user="The user to add", role="The role to add")
    async def add_command(
        self,
        interaction: discord.Interaction,
        user: Optional[discord.Member] = None,
        role: Optional[discord.Role] = None,
    ) -> None:
        try:
            msg = interaction.client.messages
            ticket = await self._get_ticket_from_context(interaction)

            if user:
                await self._check_permission(interaction, "ticket_add_user", ticket["category"])
                if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
                    await interaction.response.send_message(
                        msg.get("permissions.ticket_channel_only"),
                        ephemeral=True,
                    )
                    return

                await interaction.channel.set_permissions(
                    user,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                )
                await self.audit_service.log(
                    action="USER_ADDED",
                    actor_id=interaction.user.id,
                    actor_name=str(interaction.user),
                    target_id=user.id,
                    target_name=str(user),
                    ticket_id=ticket["ticket_id"],
                    category=ticket["category"],
                    channel_id=interaction.channel.id,
                    details=f"Added user {user} to ticket {ticket['ticket_id']}.",
                )
                await interaction.response.send_message(
                    msg.get("ticket_commands.user_added", user=user.mention), ephemeral=False
                )

            elif role:
                await self._check_permission(interaction, "ticket_add_role", ticket["category"])
                if not interaction.channel or not isinstance(interaction.channel, discord.TextChannel):
                    await interaction.response.send_message(
                        msg.get("permissions.ticket_channel_only"),
                        ephemeral=True,
                    )
                    return

                await interaction.channel.set_permissions(
                    role,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                )
                await self.audit_service.log(
                    action="ROLE_ADDED",
                    actor_id=interaction.user.id,
                    actor_name=str(interaction.user),
                    target_id=role.id,
                    target_name=str(role),
                    ticket_id=ticket["ticket_id"],
                    category=ticket["category"],
                    channel_id=interaction.channel.id,
                    details=f"Added role {role} to ticket {ticket['ticket_id']}.",
                )
                await interaction.response.send_message(
                    msg.get("ticket_commands.role_added", role=role.mention), ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    msg.get("ticket_commands.no_user_or_role"),
                    ephemeral=True,
                )

        except TicketNotFoundError:
            await interaction.response.send_message(
                msg.get("permissions.not_ticket_channel"),
                ephemeral=True,
            )
        except PermissionDeniedError:
            await interaction.response.send_message(
                msg.get("permissions.no_permission_add"),
                ephemeral=True,
            )
        except Exception as e:
            logger.error("Error in /add: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        msg.get("errors.try_again"),
                        ephemeral=True,
                    )
                except Exception:
                    pass

    @app_commands.command(name="claim", description="Claim the current ticket")
    async def claim_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            ticket = await self._get_ticket_from_context(interaction)
            await self._check_permission(interaction, "ticket_claim", ticket["category"])

            updated_ticket = await self.ticket_service.claim_ticket(
                ticket["ticket_id"], interaction.user.id
            )

            await self.audit_service.log(
                action="TICKET_CLAIMED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                ticket_id=ticket["ticket_id"],
                category=ticket["category"],
                channel_id=interaction.channel.id if interaction.channel else None,
                details=f"Ticket claimed by {interaction.user}.",
            )

            embed = make_ticket_embed(
                updated_ticket,
                self.config_service.get_ui(),
                claimed_by=str(interaction.user),
            )
            await interaction.response.send_message(
                msg.get("ticket_commands.claim_success", ticket_id=ticket["ticket_id"]), embed=embed,
                ephemeral=True,
            )

        except TicketNotFoundError:
            await interaction.response.send_message(
                msg.get("permissions.not_ticket_channel"),
                ephemeral=True,
            )
        except PermissionDeniedError:
            await interaction.response.send_message(
                msg.get("permissions.no_permission_claim"),
                ephemeral=True,
            )
        except Exception as e:
            logger.error("Error in /claim: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        msg.get("errors.try_again"),
                        ephemeral=True,
                    )
                except Exception:
                    pass

    @app_commands.command(name="unclaim", description="Unclaim the current ticket")
    async def unclaim_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            ticket = await self._get_ticket_from_context(interaction)
            await self._check_permission(interaction, "ticket_unclaim", ticket["category"])

            updated_ticket = await self.ticket_service.unclaim_ticket(
                ticket["ticket_id"], interaction.user.id
            )

            await self.audit_service.log(
                action="TICKET_UNCLAIMED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                ticket_id=ticket["ticket_id"],
                category=ticket["category"],
                channel_id=interaction.channel.id if interaction.channel else None,
                details=f"Ticket unclaimed by {interaction.user}.",
            )

            await interaction.response.send_message(
                msg.get("ticket_commands.unclaim_success", ticket_id=ticket["ticket_id"]),
                ephemeral=True,
            )

        except TicketNotFoundError:
            await interaction.response.send_message(
                msg.get("permissions.not_ticket_channel"),
                ephemeral=True,
            )
        except PermissionDeniedError:
            await interaction.response.send_message(
                msg.get("permissions.no_permission_unclaim"),
                ephemeral=True,
            )
        except Exception as e:
            logger.error("Error in /unclaim: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        msg.get("errors.try_again"),
                        ephemeral=True,
                    )
                except Exception:
                    pass

    @app_commands.command(name="delete", description="Delete the current ticket")
    async def delete_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            ticket = await self._get_ticket_from_context(interaction)
            await self._check_permission(interaction, "ticket_delete", ticket["category"])

            transcript_config = self.config_service.get_transcripts()
            if transcript_config.get("channel_id"):
                try:
                    messages = await self.bot.db.get_messages(ticket["ticket_id"])
                    claims = await self.bot.db.get_claims(ticket["ticket_id"])
                    responses = await self.bot.db.get_responses(ticket["ticket_id"])
                    html_content = await self.transcript_service.generate_transcript(
                        ticket, messages, claims, responses
                    )
                    filepath = await self.transcript_service.save_transcript(
                        ticket["ticket_id"], html_content
                    )
                    transcript_channel_id = transcript_config.get("channel_id")
                    if transcript_channel_id and interaction.guild:
                        transcript_channel = interaction.guild.get_channel(transcript_channel_id)
                        if transcript_channel:
                            await self.transcript_service.upload_transcript(
                                transcript_channel, filepath, ticket["ticket_id"]
                            )
                    await self.audit_service.log(
                        action="TRANSCRIPT_GENERATED",
                        actor_id=interaction.user.id,
                        actor_name=str(interaction.user),
                        ticket_id=ticket["ticket_id"],
                        category=ticket["category"],
                        details=f"Transcript generated before deletion for ticket {ticket['ticket_id']}.",
                    )
                except Exception as e:
                    logger.error("Failed to generate transcript before deletion: %s", e)

            await self.ticket_service.delete_ticket(ticket["ticket_id"])

            await self.audit_service.log(
                action="TICKET_DELETED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                ticket_id=ticket["ticket_id"],
                category=ticket["category"],
                channel_id=interaction.channel.id if interaction.channel else None,
                details=f"Ticket deleted by {interaction.user}.",
            )

            await interaction.response.send_message(
                msg.get("ticket_commands.delete_success", ticket_id=ticket["ticket_id"]),
                ephemeral=True,
            )

            if interaction.channel and isinstance(interaction.channel, discord.TextChannel):
                try:
                    await interaction.channel.delete(reason=f"Ticket {ticket['ticket_id']} deleted by {interaction.user}")
                except Exception as e:
                    logger.error("Failed to delete channel: %s", e)

        except TicketNotFoundError:
            await interaction.response.send_message(
                msg.get("permissions.not_ticket_channel"),
                ephemeral=True,
            )
        except PermissionDeniedError:
            await interaction.response.send_message(
                msg.get("permissions.no_permission_delete"),
                ephemeral=True,
            )
        except Exception as e:
            logger.error("Error in /delete: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        msg.get("errors.try_again"),
                        ephemeral=True,
                    )
                except Exception:
                    pass

    @app_commands.command(name="transcript", description="Generate a transcript for the current ticket")
    async def transcript_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            ticket = await self._get_ticket_from_context(interaction)
            await self._check_permission(interaction, "ticket_transcript", ticket["category"])

            await interaction.response.defer()

            messages = await self.bot.db.get_messages(ticket["ticket_id"])
            claims = await self.bot.db.get_claims(ticket["ticket_id"])
            responses = await self.bot.db.get_responses(ticket["ticket_id"])

            html_content = await self.transcript_service.generate_transcript(
                ticket, messages, claims, responses
            )
            filepath = await self.transcript_service.save_transcript(
                ticket["ticket_id"], html_content
            )

            transcript_config = self.config_service.get_transcripts()
            transcript_channel_id = transcript_config.get("channel_id")
            if transcript_channel_id and interaction.guild:
                transcript_channel = interaction.guild.get_channel(transcript_channel_id)
                if transcript_channel:
                    await self.transcript_service.upload_transcript(
                        transcript_channel, filepath, ticket["ticket_id"]
                    )

            await self.audit_service.log(
                action="TRANSCRIPT_GENERATED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                ticket_id=ticket["ticket_id"],
                category=ticket["category"],
                details=f"Manual transcript generated for ticket {ticket['ticket_id']}.",
            )

            import discord as discord_file
            file = discord_file.File(filepath, filename=f"{ticket['ticket_id']}_transcript.html")
            await interaction.followup.send(
                msg.get("ticket_commands.transcript_success", ticket_id=ticket["ticket_id"]), file=file,
                ephemeral=True,
            )

        except TicketNotFoundError:
            await interaction.followup.send(
                msg.get("permissions.not_ticket_channel"),
                ephemeral=True,
            )
        except PermissionDeniedError:
            await interaction.followup.send(
                msg.get("permissions.no_permission_transcript"),
                ephemeral=True,
            )
        except Exception as e:
            logger.error("Error in /transcript: %s", e)
            try:
                await interaction.followup.send(
                    msg.get("errors.try_again"),
                    ephemeral=True,
                )
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if not message.guild:
            return

        ticket = await self.ticket_service.get_ticket_by_channel(message.channel.id)
        if ticket:
            await self.bot.db.add_message(
                message_id=message.id,
                ticket_id=ticket["ticket_id"],
                author_id=message.author.id,
                author_name=str(message.author),
                content=message.content,
                attachments=str([
                    {"url": a.url, "filename": a.filename}
                    for a in message.attachments
                ]) if message.attachments else "[]",
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TicketsCog(bot))
