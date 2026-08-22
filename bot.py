from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from database.database import Database
from services.config_service import ConfigService
from services.permission_service import PermissionService
from services.ticket_service import TicketService
from services.transcript_service import TranscriptService
from services.audit_service import AuditService
from services.statistics_service import StatisticsService
from utils import timezone
from utils.messages import MessageService

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
if not DISCORD_TOKEN:
    print("ERROR: DISCORD_TOKEN not found in environment variables.")
    print("Please create a .env file with DISCORD_TOKEN=your_bot_token")
    sys.exit(1)


def setup_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "ticket_bot.log",
        maxBytes=5_242_880,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(logging.WARNING)
    logging.getLogger("discord.ui").setLevel(logging.WARNING)

    app_logger = logging.getLogger("ticket_bot")
    app_logger.setLevel(logging.DEBUG)

    app_console_handler = logging.StreamHandler(sys.stdout)
    app_console_handler.setLevel(logging.DEBUG)
    app_console_handler.setFormatter(console_format)
    app_logger.addHandler(app_console_handler)


logger = logging.getLogger("ticket_bot.main")


class TicketBot(commands.Bot):
    """Main bot class for the IRBW Ticket System."""

    def __init__(self, connector: Optional[aiohttp.TCPConnector] = None) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            connector=connector,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="IRBW Support",
            ),
        )

        self.config_service: ConfigService = ConfigService()
        self.messages: MessageService = MessageService()
        self.db: Optional[Database] = None
        self.permission_service: Optional[PermissionService] = None
        self.ticket_service: Optional[TicketService] = None
        self.transcript_service: Optional[TranscriptService] = None
        self.audit_service: Optional[AuditService] = None
        self.statistics_service: Optional[StatisticsService] = None

    async def setup_hook(self) -> None:
        logger.info("Setting up bot...")

        self.config_service.load()
        timezone.init(self.config_service._config)
        logger.info("Timezone set to: %s", self.config_service._config.get("timezone", "UTC"))

        self.db = Database("tickets.db")
        await self.db.connect()
        logger.info("Database connected.")

        self.permission_service = PermissionService(self.db)
        self.ticket_service = TicketService(self.db)
        self.transcript_service = TranscriptService(self.db)
        self.audit_service = AuditService(self.db)
        self.statistics_service = StatisticsService(self.db)
        self.audit_service.set_refs(self, self.config_service)
        logger.info("Services initialized.")

        cog_modules = [
            "cogs.tickets",
            "cogs.permissions",
            "cogs.admin",
            "cogs.statistics",
            "cogs.commands",
        ]
        for module in cog_modules:
            try:
                await self.load_extension(module)
                logger.info("Loaded extension: %s", module)
            except Exception as e:
                logger.error("Failed to load extension %s: %s", module, e)

        guild_id = self.config_service.get_guild_id()
        if guild_id:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logger.info("Synced %d commands to guild %d.", len(synced), guild_id)
        else:
            synced = await self.tree.sync()
            logger.info("Synced %d commands globally.", len(synced))

        self._register_persistent_views()

        logger.info("Bot setup complete.")

    def _register_persistent_views(self) -> None:
        from ui.panels import TicketPanelButtonView, TicketPanelDropdownView
        from ui.ticket_views import PendingTicketView, ActiveTicketView
        from ui.modals import TicketCreationModal, ResponseModal, CloseReasonModal, ResolveModal, BanReasonModal

        categories = self.config_service.get_categories()
        panel_config = self.config_service.get_ticket_panel()
        panel_type = panel_config.get("type", "buttons")

        if panel_type == "dropdown":
            dropdown_view = TicketPanelDropdownView(categories)
            self.add_view(dropdown_view)
            logger.info(
                "Registered persistent dropdown view with custom_id='ticket_panel_select', "
                "categories=%s",
                list(categories.keys()),
            )
        else:
            button_view = TicketPanelButtonView(categories)
            self.add_view(button_view)
            custom_ids = [f"ticket_panel_{k}" for k in categories.keys()]
            logger.info(
                "Registered persistent button view with custom_ids=%s, categories=%s",
                custom_ids,
                list(categories.keys()),
            )

        self.add_view(PendingTicketView())
        self.add_view(ActiveTicketView())
        logger.info("Registered persistent PendingTicketView and ActiveTicketView")

        for cat_key, cat_config in categories.items():
            modal = TicketCreationModal(
                category=cat_key,
                category_display=cat_config.get("display_name", cat_key.title()),
                fields=cat_config.get("fields"),
                custom_id=f"ticket_modal_{cat_key}",
            )
            self.add_view(modal)
        self.add_view(ResponseModal())
        self.add_view(CloseReasonModal())
        self.add_view(ResolveModal())
        self.add_view(BanReasonModal())
        logger.info("Registered persistent TicketCreationModal, ResponseModal, CloseReasonModal, ResolveModal, and BanReasonModal")

        if panel_config.get("message_id"):
            logger.info(
                "Panel message_id=%s, channel_id=%s, type=%s",
                panel_config["message_id"],
                panel_config.get("channel_id"),
                panel_type,
            )

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (ID: %d)", self.user, self.user.id)
        logger.info("Connected to %d guild(s)", len(self.guilds))

        guild_id = self.config_service.get_guild_id()
        guild = self.get_guild(guild_id)
        if guild:
            logger.info("Operating in guild: %s (ID: %d)", guild.name, guild.id)
        else:
            logger.error(
                "Bot is not in the configured guild (ID: %d). "
                "Please invite the bot to the correct server.",
                guild_id,
            )

    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        if isinstance(error, commands.CommandNotFound):
            return
        logger.error("Command error: %s", error, exc_info=error)

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ) -> None:
        logger.error("App command error in %s: %s", interaction.command, error, exc_info=error)
        if isinstance(error, app_commands.CommandInvokeError) and isinstance(error.original, discord.NotFound):
            return
        if isinstance(error, discord.NotFound):
            return
        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    self.messages.get("errors.generic"),
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    self.messages.get("errors.generic"),
                    ephemeral=True,
                )
        except Exception:
            pass


def _build_connector() -> Optional[aiohttp.TCPConnector]:
    """Build an aiohttp connector with proxy support if configured."""
    from services.config_service import ConfigService
    cfg = ConfigService()
    cfg.load()
    proxy_cfg = cfg.get("proxy", {})
    if not proxy_cfg.get("enabled"):
        return None

    host = proxy_cfg.get("host", "")
    port = proxy_cfg.get("port", 0)
    proxy_type = proxy_cfg.get("type", "http")
    username = proxy_cfg.get("username", "")
    password = proxy_cfg.get("password", "")

    if not host or not port:
        logger.warning("Proxy enabled but host/port not set, skipping proxy.")
        return None

    proxy_url = f"{proxy_type}://{host}:{port}"
    logger.info("Building proxy connector: %s (type=%s, auth=%s)", proxy_url, proxy_type, "yes" if username else "no")

    connector = aiohttp.TCPConnector()
    connector._proxy = proxy_url  # type: ignore
    if username and password:
        connector._proxy_auth = aiohttp.BasicAuth(username, password)  # type: ignore
    return connector


def main() -> None:
    setup_logging()
    logger.info("Starting IRBW Ticket Bot...")

    connector = _build_connector()
    bot = TicketBot(connector=connector)
    bot.run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
