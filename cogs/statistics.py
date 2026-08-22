from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("ticket_bot.cogs.statistics")


def truncate(text: str, length: int) -> str:
    return text if len(text) <= length else text[:length - 3] + "..."


class StatisticsCog(commands.Cog):
    """Statistics commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def statistics_service(self):
        return self.bot.statistics_service

    @property
    def permission_service(self):
        return self.bot.permission_service

    @property
    def config_service(self):
        return self.bot.config_service

    @app_commands.command(name="status", description="View your ticket statistics and recent history")
    async def status_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            await interaction.response.defer(ephemeral=True)

            stats = await self.statistics_service.get_user_stats(interaction.user.id)
            tickets = await self.statistics_service.get_user_tickets(interaction.user.id)

            embed = discord.Embed(
                title="Your Ticket Status",
                color=5814783,
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            embed.add_field(name="Total Tickets", value=str(stats["total"]), inline=True)
            embed.add_field(name="Pending", value=str(stats["pending"]), inline=True)
            embed.add_field(name="Open", value=str(stats["open"]), inline=True)
            embed.add_field(name="Claimed", value=str(stats["claimed"]), inline=True)
            embed.add_field(name="Responded", value=str(stats["responded"]), inline=True)
            embed.add_field(name="Closed", value=str(stats["closed"]), inline=True)
            embed.add_field(name="Deleted", value=str(stats["deleted"]), inline=True)
            embed.add_field(name="Responses Received", value=str(stats["responses_received"]), inline=True)

            if stats["by_category"]:
                cat_text = "\n".join(
                    f"**{cat.title()}:** {count}"
                    for cat, count in stats["by_category"].items()
                )
                embed.add_field(name="By Category", value=cat_text, inline=False)

            if tickets:
                recent_lines = []
                for t in tickets[:10]:
                    status_emoji = {
                        "PENDING": "\u23f3",
                        "OPEN": "\ud83d\udce2",
                        "CLAIMED": "\ud83d\udc64",
                        "RESPONDED": "\u2705",
                        "CLOSED": "\ud83d\udd12",
                        "DELETED": "\ud83d\uddd1\ufe0f",
                    }.get(t["status"], "\u2753")

                    parts = [f"{status_emoji} `{t['ticket_id']}` - {t['category'].title()} - {t['status']}"]
                    cf = t.get("custom_fields", {})
                    for field_key, field_val in cf.items():
                        if field_val:
                            label = field_key.replace("_", " ").title()
                            parts.append(f"   **{label}:** {truncate(str(field_val), 80)}")
                    if t.get("response"):
                        parts.append(f"   \u2192 {truncate(t['response'], 80)}")
                    recent_lines.append("\n".join(parts))

                embed.add_field(
                    name="Recent Tickets",
                    value="\n\n".join(recent_lines) if recent_lines else "None",
                    inline=False,
                )

                if len(tickets) > 10:
                    embed.set_footer(text=f"Showing 10 of {len(tickets)} tickets | IRBW Ticket System")
                else:
                    embed.set_footer(text=msg.get("statistics.title"))
            else:
                embed.set_footer(text=msg.get("statistics.no_history"))

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error("Error in /status: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.followup.send(
                        msg.get("errors.try_again"), ephemeral=True
                    )
                except Exception:
                    pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(StatisticsCog(bot))
