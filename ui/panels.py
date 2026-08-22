from __future__ import annotations

import logging
from typing import Any

import discord

from .modals import TicketCreationModal
from utils import timezone

logger = logging.getLogger("ticket_bot.ui.panels")

BUTTON_STYLES = [
    discord.ButtonStyle.primary,
    discord.ButtonStyle.secondary,
    discord.ButtonStyle.success,
    discord.ButtonStyle.danger,
]


class TicketPanelButtonView(discord.ui.View):
    """Persistent view for button-based ticket panel with dynamic category buttons."""

    def __init__(self, categories: dict[str, Any] | None = None) -> None:
        super().__init__(timeout=None)
        if categories:
            self._add_dynamic_buttons(categories)

    def _add_dynamic_buttons(self, categories: dict[str, Any]) -> None:
        for i, (key, cat_config) in enumerate(categories.items()):
            style = BUTTON_STYLES[i % len(BUTTON_STYLES)]
            display = cat_config.get("display_name", key.title())
            button = discord.ui.Button(
                label=display,
                style=style,
                custom_id=f"ticket_panel_{key}",
                row=i // 4,
            )
            button.callback = self._make_callback(key)
            self.add_item(button)

    def _make_callback(self, category_key: str):
        async def callback(interaction: discord.Interaction) -> None:
            await _handle_ticket_category(interaction, category_key)
        return callback

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: Any) -> None:
        logger.error("TicketPanelButtonView error on %s: %s", item, error, exc_info=True)
        msg = interaction.client.messages
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    msg.get("panels.generic_error"),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    msg.get("panels.generic_error"),
                    ephemeral=True,
                )
        except Exception:
            pass


async def _handle_ticket_category(interaction: discord.Interaction, category: str) -> None:
    """Shared handler for both button and dropdown ticket creation."""
    logger.debug("[STEP] _handle_ticket_category called: category=%s user=%s", category, interaction.user)
    msg = interaction.client.messages
    try:
        bot = interaction.client
        config_service = bot.config_service
        ticket_service = bot.ticket_service
        permission_service = bot.permission_service
        logger.debug("[STEP] Got services from bot")

        ban = await ticket_service.check_user_banned(interaction.user.id)
        if ban:
            reason_text = f"\n**Reason:** {ban['reason']}" if ban.get("reason") else ""
            if ban.get("expires_at"):
                import datetime
                try:
                    expires_dt = datetime.datetime.fromisoformat(ban["expires_at"])
                    remaining = expires_dt - timezone.now()
                    from services.ticket_service import format_duration_display
                    remaining_str = format_duration_display(remaining)
                    time_text = f"**Expires in:** {remaining_str}"
                except Exception:
                    time_text = f"**Expires:** {ban['expires_at']}"
            else:
                time_text = "**Duration:** Permanent"
            try:
                await interaction.response.send_message(
                    f"\u26a0\ufe0f You are banned from creating tickets.{reason_text}\n{time_text}\n"
                    f"**Offense #{ban.get('offense_number', '?')}**",
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        cat_config = config_service.get_category(category)
        if not cat_config:
            logger.warning("[STEP] Category '%s' not found in config", category)
            try:
                await interaction.response.send_message(
                    msg.get("ticket_creation.category_not_available"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return
        logger.debug("[STEP] Got category config: %s", cat_config.get("display_name"))

        create_mode = config_service.get("ticket_create_mode", "roles")
        logger.debug("[STEP] ticket_create_mode=%s", create_mode)

        if create_mode == "everyone":
            pass
        else:
            logger.debug("[STEP] Checking permission: user=%s, key=ticket_create, category=%s", interaction.user, category)
            has_perm = await permission_service.check(
                interaction.user, "ticket_create", category
            )
            logger.debug("[STEP] Permission check result: %s", has_perm)
            if not has_perm:
                try:
                    await interaction.response.send_message(
                        msg.get("ticket_creation.no_permission"),
                        ephemeral=True,
                    )
                except Exception:
                    pass
                return

        max_tickets = config_service.get_max_open_tickets()
        active_count = await ticket_service.count_active_tickets(interaction.user.id)
        logger.debug("[STEP] Active tickets: %d / %d", active_count, max_tickets)
        if active_count >= max_tickets:
            try:
                await interaction.response.send_message(
                    msg.get("ticket_creation.max_tickets_reached", max=max_tickets),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        pending_count = await ticket_service.count_pending_tickets(interaction.user.id, category)
        logger.debug("[STEP] Pending tickets: %d", pending_count)
        if pending_count > 0:
            try:
                await interaction.response.send_message(
                    msg.get("ticket_creation.already_pending"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        modal = TicketCreationModal(
            category=category,
            category_display=cat_config["display_name"],
            fields=cat_config.get("fields"),
            custom_id=f"ticket_modal_{category}",
        )
        logger.debug("[STEP] Sending modal with custom_id=%s...", f"ticket_modal_{category}")
        try:
            await interaction.response.send_modal(modal)
        except Exception:
            pass
        logger.debug("[STEP] Modal sent successfully")
    except Exception as e:
        logger.error("Error in _handle_ticket_category (%s): %s", category, e, exc_info=True)
        import traceback
        traceback.print_exc()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    msg.get("panels.generic_error"),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    msg.get("panels.generic_error"),
                    ephemeral=True,
                )
        except Exception:
            pass


class TicketPanelDropdownView(discord.ui.View):
    """Persistent view for dropdown-based ticket panel."""

    def __init__(self, categories: dict[str, Any]) -> None:
        super().__init__(timeout=None)
        options = []
        for key, cat_config in categories.items():
            options.append(
                discord.SelectOption(
                    label=cat_config.get("display_name", key.title()),
                    value=key,
                    description=f"Open a {cat_config.get('display_name', key)} support ticket",
                )
            )
        if not options:
            options.append(discord.SelectOption(label="No categories available", value="none"))
        select = TicketCategorySelect(options=options, categories=categories)
        self.add_item(select)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: Any) -> None:
        logger.error("TicketPanelDropdownView error on %s: %s", item, error, exc_info=True)
        msg = interaction.client.messages
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    msg.get("panels.generic_error"),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    msg.get("panels.generic_error"),
                    ephemeral=True,
                )
        except Exception:
            pass


class TicketCategorySelect(discord.ui.Select):
    """Select menu for ticket category selection."""

    def __init__(self, options: list[discord.SelectOption], categories: dict[str, Any]) -> None:
        super().__init__(
            placeholder="Select a ticket category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_panel_select",
        )
        self.categories = categories

    async def callback(self, interaction: discord.Interaction) -> None:
        logger.info("TicketCategorySelect.callback fired for user %s, values=%s", interaction.user, self.values)
        msg = interaction.client.messages
        category = self.values[0]
        if category == "none":
            try:
                await interaction.response.send_message(
                    msg.get("ticket_creation.no_categories"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return

        await _handle_ticket_category(interaction, category)
