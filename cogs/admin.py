from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.errors import ConfigurationError

logger = logging.getLogger("ticket_bot.cogs.admin")


class AdminHelpNavigationView(discord.ui.View):
    """Navigation view for the /adminhelp pages."""

    def __init__(self) -> None:
        super().__init__(timeout=180)
        self.current_page = "setup"

    def _get_page(self, page: str, config_service) -> discord.Embed:
        if page == "setup":
            return self._setup_page()
        elif page == "categories":
            return self._categories_page()
        elif page == "permissions":
            return self._permissions_page()
        elif page == "panel":
            return self._panel_page()
        elif page == "features":
            return self._features_page()
        elif page == "troubleshooting":
            return self._troubleshooting_page()
        return self._setup_page()

    def _setup_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Initial Setup",
            description="Step-by-step guide to get the bot running.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Step 1: Create `.env`",
            value="```bash\ncp .env.example .env\n```\n"
            "Add your bot token:\n```env\nDISCORD_TOKEN=your_bot_token_here\n```",
            inline=False,
        )
        embed.add_field(
            name="Step 2: Configure `config.json`",
            value="At minimum, set your server ID:\n```json\n"
            '{\n  "guild_id": 123456789012345678,\n  ...\n}\n```\n'
            "Replace `123456789012345678` with your actual Discord server (guild) ID.\n"
            "Right-click your server icon > Copy Server ID to get it.",
            inline=False,
        )
        embed.add_field(
            name="Step 3: Start the bot",
            value="```bash\npython bot.py\n```\n"
            "The bot will validate your config on startup.",
            inline=False,
        )
        embed.add_field(
            name="Step 4: Sync commands",
            value="Commands auto-sync on startup. If they don't appear:\n"
            "Use `/reload` to resync.",
            inline=False,
        )
        embed.set_footer(text="Page 1 of 6 | Use the dropdown to navigate")
        return embed

    def _categories_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Category Configuration",
            description="How to set up ticket categories in `config.json`.",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Adding a Category",
            value="Edit `config.json` and add to the `categories` object:\n```json\n"
            '"my_category": {\n'
            '  "display_name": "My Category",\n'
            '  "id_prefix": "mycat",\n'
            '  "pending_channel_id": 0,\n'
            '  "open_category_id": 0,\n'
            '  "closed_category_id": 0,\n'
            '  "staff_roles": [],\n'
            '  "respond_roles": [],\n'
            '  "claim_roles": [],\n'
            '  "delete_roles": [],\n'
            '  "add_roles": [],\n'
            '  "view_open_roles": [],\n'
            '  "view_closed_roles": [],\n'
            '  "override_roles": []\n'
            "}\n```\n"
            "Then run `/reload` to apply.",
            inline=False,
        )
        embed.add_field(
            name="Field Reference",
            value=(
                "`display_name` - Shown in the panel and embeds\n"
                "`id_prefix` - Used in ticket IDs (e.g. `mycat-0001`)\n"
                "`pending_channel_id` - Channel where pending tickets appear\n"
                "`open_category_id` - Discord category for open ticket channels\n"
                "`closed_category_id` - Discord category for closed ticket channels\n"
                "`staff_roles` - Roles that get default access to this category\n"
                "`respond_roles` - Roles that can use `/response` in this category\n"
                "`claim_roles` - Roles that can claim tickets in this category\n"
                "`delete_roles` - Roles that can delete tickets in this category\n"
                "`add_roles` - Roles that can add users/roles to tickets\n"
                "`view_open_roles` - Roles that can see open ticket channels\n"
                "`view_closed_roles` - Roles that can see closed ticket channels\n"
                "`override_roles` - Roles that can override claims"
            ),
            inline=False,
        )
        embed.add_field(
            name="Getting Channel/Category IDs",
            value="Enable Developer Mode in Discord (Settings > Advanced > Developer Mode).\n"
            "Right-click any channel/category > Copy ID.",
            inline=False,
        )
        embed.add_field(
            name="Example: General Category",
            value='```json\n"general": {\n'
            '  "display_name": "General",\n'
            '  "id_prefix": "general",\n'
            '  "pending_channel_id": 1234567890123,\n'
            '  "open_category_id": 1234567890124,\n'
            '  "closed_category_id": 1234567890125,\n'
            '  "staff_roles": [1234567890126]\n'
            '}\n```',
            inline=False,
        )
        embed.set_footer(text="Page 2 of 6 | Use the dropdown to navigate")
        return embed

    def _permissions_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Permission System",
            description="How to configure who can do what.",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="Using Slash Commands",
            value="Use `/permission add` and `/permission remove`.\n\n"
            "1. Run `/permission add role:@YourRole`\n"
            "2. Select a permission from the dropdown (e.g. `ticket_respond`)\n"
            "3. Select a category scope (Global or specific category)\n"
            "4. Click **Confirm**\n\n"
            "Run `/permission list` to see all keys and current assignments.",
            inline=False,
        )
        embed.add_field(
            name="Permission Keys Reference",
            value=(
                "`ticket_create` - Open new tickets\n"
                "`ticket_view_open` - See open ticket channels\n"
                "`ticket_respond` - Send responses via DM\n"
                "`ticket_claim` / `ticket_unclaim` - Claim/unclaim tickets\n"
                "`ticket_add_user` / `ticket_add_role` - Add users/roles\n"
                "`ticket_delete` - Delete tickets\n"
                "`ticket_close` - Close open tickets\n"
                "`ticket_reopen` - Reopen closed tickets\n"
                "`ticket_transcript` - Generate transcripts\n"
                "`ticket_ban` - Ban users from creating tickets\n"
                "`ticket_move` - Move tickets between categories\n"
                "`adminstats` - View admin statistics\n"
                "`adminhelp` - View this help\n"
                "`reload` - Reload configuration\n"
                "`permission_add` / `permission_remove` - Manage permissions"
            ),
            inline=False,
        )
        embed.add_field(
            name="Category-Specific Example",
            value="Give Moderators permission to respond to General tickets only:\n"
            "```\n/permission add role:@Moderator\n```\n"
            "Then select `ticket_respond` and `General` from the dropdowns.",
            inline=False,
        )
        embed.add_field(
            name="Global Permission Example",
            value="Give all Staff the ability to claim any ticket:\n"
            "```\n/permission add role:@Staff\n```\n"
            "Then select `ticket_claim` and `Global` from the dropdowns.",
            inline=False,
        )
        embed.add_field(
            name="Important Notes",
            value=(
                "- Server administrators bypass most permission checks\n"
                "- The guild owner always has full access\n"
                "- `staff_roles` in category config provides default access\n"
                "- DB permissions override config defaults\n"
                "- After adding/removing permissions, no reload is needed"
            ),
            inline=False,
        )
        embed.set_footer(text="Page 3 of 6 | Use the dropdown to navigate")
        return embed

    def _panel_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Ticket Panel",
            description="How to set up and deploy the ticket creation panel.",
            color=discord.Color.purple(),
        )
        embed.add_field(
            name="Panel Configuration",
            value='Edit `config.json`:\n```json\n"ticket_panel": {\n'
            '  "channel_id": 1234567890123,\n'
            '  "type": "buttons",\n'
            '  "embed": {\n'
            '    "title": "IRBW Support",\n'
            '    "description": "Need help? Select a category below to open a support ticket.",\n'
            '    "color": 5814783,\n'
            '    "footer": { "text": "IRBW Ticket System" }\n'
            '  }\n'
            '}\n```\n'
            "`type` can be `\"buttons\"` or `\"dropdown\"`.",
            inline=False,
        )
        embed.add_field(
            name="Deploying the Panel",
            value=(
                "Option A - With channel in config:\n"
                "```\n/deploy\n```\n\n"
                "Option B - Specify channel directly:\n"
                "```\n/deploy channel:#support\n```\n\n"
                "This creates the panel message with buttons or dropdown.\n"
                "The bot stores the message ID for restart recovery."
            ),
            inline=False,
        )
        embed.add_field(
            name="After Deploying",
            value="Run `/reload` if you change the panel type or embed settings.\n"
            "Use `/deploy` again to update the panel.\n"
            "The old panel message is automatically deleted.",
            inline=False,
        )
        embed.set_footer(text="Page 4 of 6 | Use the dropdown to navigate")
        return embed

    def _features_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Features & Channel Setup",
            description="Transcripts, audit logs, and other features.",
            color=discord.Color.teal(),
        )
        embed.add_field(
            name="Transcripts",
            value='Enable in `config.json`:\n```json\n"transcripts": {\n'
            '  "enabled": true,\n'
            '  "channel_id": 1234567890123\n'
            '}\n```\n'
            "Set `channel_id` to a channel where transcripts are uploaded.\n"
            "HTML transcripts are saved in the `transcripts/` folder.",
            inline=False,
        )
        embed.add_field(
            name="Audit Logs",
            value='Enable in `config.json`:\n```json\n"audit_log": {\n'
            '  "enabled": true,\n'
            '  "channel_id": 1234567890123\n'
            '}\n```\n'
            "All staff actions are logged to this channel and the database.",
            inline=False,
        )
        embed.add_field(
            name="Ticket Limits",
            value='```json\n"max_open_tickets": 1\n```\n'
            "Controls how many active tickets a user can have at once.",
            inline=False,
        )
        embed.add_field(
            name="DM Notifications",
            value='```json\n"dm_settings": {\n'
            '  "enabled": true,\n'
            '  "close_dm": true\n'
            '}\n```\n'
            "Users get DM'd when ticket closes.",
            inline=False,
        )
        embed.add_field(
            name="Closed Ticket Naming",
            value='```json\n"closed_naming_format": "closed-{prefix}-{number}"\n```\n'
            "Placeholders: `{prefix}` (category prefix), `{number}`, `{ticket_id}`",
            inline=False,
        )
        embed.set_footer(text="Page 5 of 6 | Use the dropdown to navigate")
        return embed

    def _troubleshooting_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Troubleshooting",
            description="Common issues and how to fix them.",
            color=discord.Color.red(),
        )
        embed.add_field(
            name="Commands not appearing",
            value=(
                "1. Ensure bot has `Use Application Commands` permission\n"
                "2. Wait up to 1 hour for global command cache\n"
                "3. Try `/reload` to resync\n"
                "4. Check the bot log for errors on startup"
            ),
            inline=False,
        )
        embed.add_field(
            name="Panel buttons not working",
            value=(
                "1. Verify `channel_id` in `ticket_panel` is correct\n"
                "2. Run `/deploy` to recreate the panel\n"
                "3. Ensure bot has Send Messages + Embed Links in that channel\n"
                "4. Check categories in config have valid channel IDs"
            ),
            inline=False,
        )
        embed.add_field(
            name="Ticket channel not created",
            value=(
                "1. Check `open_category_id` is a valid category ID (not channel)\n"
                "2. Ensure bot has Manage Channels permission in that category\n"
                "3. Check bot role is above the everyone role in that category"
            ),
            inline=False,
        )
        embed.add_field(
            name="DMs not received by user",
            value=(
                "1. User may have DMs disabled for this server\n"
                "2. Check bot log for `discord.Forbidden` errors\n"
                "3. Staff will see a warning if DM fails"
            ),
            inline=False,
        )
        embed.add_field(
            name="Config changes not taking effect",
            value=(
                "1. Run `/reload` after editing `config.json`\n"
                "2. If reload fails, check JSON syntax\n"
                "3. Bot retains old config if new one is invalid\n"
                "4. Some changes (like panel type) require `/deploy`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Database backup",
            value="Copy `tickets.db` to back up all ticket history:\n"
            "```bash\ncp tickets.db tickets_backup_$(date +%Y%m%d).db\n```",
            inline=False,
        )
        embed.set_footer(text="Page 6 of 6 | Use the dropdown to navigate")
        return embed


class AdminHelpPageSelect(discord.ui.Select):
    """Dropdown for navigating admin help pages."""

    def __init__(self) -> None:
        options = [
            discord.SelectOption(label="Initial Setup", value="setup", description="Getting started guide", emoji="\u2699\ufe0f"),
            discord.SelectOption(label="Categories", value="categories", description="Configure ticket categories", emoji="\ud83d\udcc1"),
            discord.SelectOption(label="Permissions", value="permissions", description="Permission system guide", emoji="\ud83d\udd11"),
            discord.SelectOption(label="Panel", value="panel", description="Ticket panel setup", emoji="\ud83c\udfab"),
            discord.SelectOption(label="Features", value="features", description="Transcripts, audit logs, etc.", emoji="\u2b50"),
            discord.SelectOption(label="Troubleshooting", value="troubleshooting", description="Common issues and fixes", emoji="\ud83d\udd27"),
        ]
        super().__init__(
            placeholder="Navigate help pages...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="adminhelp_nav",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        page = self.values[0]
        view: AdminHelpNavigationView = self.view  # type: ignore
        view.current_page = page

        config_service = None
        if hasattr(interaction.client, "config_service"):
            config_service = interaction.client.config_service

        embed = view._get_page(page, config_service)
        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            pass


class AdminHelpNavigationView(discord.ui.View):
    """Navigation view for the /adminhelp pages."""

    def __init__(self) -> None:
        super().__init__(timeout=180)
        self.current_page = "setup"
        self.add_item(AdminHelpPageSelect())

    def _get_page(self, page: str, config_service=None) -> discord.Embed:
        if page == "setup":
            return self._setup_page()
        elif page == "categories":
            return self._categories_page()
        elif page == "permissions":
            return self._permissions_page()
        elif page == "panel":
            return self._panel_page()
        elif page == "features":
            return self._features_page()
        elif page == "troubleshooting":
            return self._troubleshooting_page()
        return self._setup_page()

    def _setup_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Initial Setup",
            description="Step-by-step guide to get the bot running.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Step 1: Create `.env`",
            value="```bash\ncp .env.example .env\n```\n"
            "Add your bot token:\n```env\nDISCORD_TOKEN=your_bot_token_here\n```",
            inline=False,
        )
        embed.add_field(
            name="Step 2: Configure `config.json`",
            value="At minimum, set your server ID:\n```json\n"
            '{\n  "guild_id": 123456789012345678\n}\n```\n'
            "Replace `123456789012345678` with your actual Discord server ID.\n"
            "Right-click your server icon > Copy Server ID.",
            inline=False,
        )
        embed.add_field(
            name="Step 3: Start the bot",
            value="```bash\npython bot.py\n```\n"
            "The bot validates your config and syncs commands on startup.",
            inline=False,
        )
        embed.add_field(
            name="Step 4: Deploy the panel",
            value="```\n/deploy channel:#your-channel\n```\n"
            "This creates the ticket creation panel in the specified channel.",
            inline=False,
        )
        embed.set_footer(text="Page 1 of 6 | Use the dropdown to navigate")
        return embed

    def _categories_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Category Configuration",
            description="How to set up ticket categories in `config.json`.",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Adding a Category",
            value='Edit `config.json` and add to `categories`:\n```json\n'
            '"general": {\n'
            '  "display_name": "General",\n'
            '  "id_prefix": "general",\n'
            '  "pending_channel_id": 1234567890123,\n'
            '  "open_category_id": 1234567890124,\n'
            '  "closed_category_id": 1234567890125,\n'
            '  "staff_roles": [1234567890126]\n'
            '}\n```\nThen run `/reload` to apply.',
            inline=False,
        )
        embed.add_field(
            name="Field Reference",
            value=(
                "`display_name` - Shown in the panel and embeds\n"
                "`id_prefix` - Ticket ID prefix (e.g. `general-0001`)\n"
                "`pending_channel_id` - Where pending tickets appear\n"
                "`open_category_id` - Discord category for open ticket channels\n"
                "`closed_category_id` - Discord category for closed tickets\n"
                "`staff_roles` - Roles with default access to this category\n"
                "`respond_roles` - Roles that can respond\n"
                "`claim_roles` - Roles that can claim tickets\n"
                "`delete_roles` - Roles that can delete tickets\n"
                "`add_roles` - Roles that can add users/roles\n"
                "`view_open_roles` - Roles that see open channels\n"
                "`view_closed_roles` - Roles that see closed channels\n"
                "`override_roles` - Roles that can override claims"
            ),
            inline=False,
        )
        embed.add_field(
            name="Getting IDs",
            value="Enable Developer Mode: Settings > Advanced > Developer Mode.\n"
            "Right-click any channel/category > Copy ID.",
            inline=False,
        )
        embed.set_footer(text="Page 2 of 6 | Use the dropdown to navigate")
        return embed

    def _permissions_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Permission System",
            description="How to configure who can do what.",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="Adding a Permission",
            value=(
                "1. Run `/permission add role:@YourRole`\n"
                "2. Select a permission key from the dropdown\n"
                "3. Select a category scope (Global or specific)\n"
                "4. Click **Confirm**"
            ),
            inline=False,
        )
        embed.add_field(
            name="Removing a Permission",
            value=(
                "1. Run `/permission remove role:@YourRole`\n"
                "2. Select the permission key and category\n"
                "3. Click **Confirm**"
            ),
            inline=False,
        )
        embed.add_field(
            name="Viewing All Permissions",
            value="```\n/permission list\n```\n"
            "Shows all 25 permission keys and which roles have them.\n"
            "Keys with no roles show as *Not configured*.",
            inline=False,
        )
        embed.add_field(
            name="Permission Keys",
            value=(
                "**Ticket Operations:**\n"
                "`ticket_create` | `ticket_view_open` | `ticket_respond`\n"
                "`ticket_claim` | `ticket_unclaim` | `ticket_add_user` | `ticket_add_role`\n"
                "`ticket_delete` | `ticket_close` | `ticket_reopen` | `ticket_transcript`\n"
                "`ticket_ban` | `ticket_move` | `ticket_purge` | `ticket_purge_all`\n\n"
                "**Admin Operations:**\n"
                "`adminstats` | `adminhelp` | `reload` | `config`\n"
                "`permission_list` | `permission_add` | `permission_remove`\n\n"
                "**General:**\n"
                "`stats` | `commands`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Example: Moderate General Only",
            value="```\n/permission add role:@Moderator\n```\n"
            "Select `ticket_respond` + `General` category.\n"
            "Moderators can now respond to General tickets but not Appeals.",
            inline=False,
        )
        embed.set_footer(text="Page 3 of 6 | Use the dropdown to navigate")
        return embed

    def _panel_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Ticket Panel",
            description="How to set up and deploy the ticket creation panel.",
            color=discord.Color.purple(),
        )
        embed.add_field(
            name="Panel Config",
            value='```json\n"ticket_panel": {\n'
            '  "channel_id": 1234567890123,\n'
            '  "type": "buttons",\n'
            '  "embed": {\n'
            '    "title": "IRBW Support",\n'
            '    "description": "Need help? Select a category below.",\n'
            '    "color": 5814783\n'
            '  }\n'
            '}\n```\n'
            '`type`: `"buttons"` or `"dropdown"`',
            inline=False,
        )
        embed.add_field(
            name="Deploying",
            value=(
                "**With channel in config:**\n```\n/deploy\n```\n\n"
                "**With channel argument:**\n```\n/deploy channel:#support\n```"
            ),
            inline=False,
        )
        embed.add_field(
            name="Updating",
            value="Run `/deploy` again to replace the old panel.\n"
            "The old message is automatically deleted.\n"
            "Bot stores the message ID for restart recovery.",
            inline=False,
        )
        embed.set_footer(text="Page 4 of 6 | Use the dropdown to navigate")
        return embed

    def _features_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Features & Channels",
            description="Transcripts, audit logs, limits, and DMs.",
            color=discord.Color.teal(),
        )
        embed.add_field(
            name="Transcripts",
            value='```json\n"transcripts": {\n'
            '  "enabled": true,\n'
            '  "channel_id": 1234567890123\n'
            '}\n```\n'
            "HTML transcripts auto-generate when tickets close/respond.\n"
            "Also saved in `transcripts/` folder.",
            inline=False,
        )
        embed.add_field(
            name="Audit Logs",
            value='```json\n"audit_log": {\n'
            '  "enabled": true,\n'
            '  "channel_id": 1234567890123\n'
            '}\n```\n'
            "All actions logged to channel + database.",
            inline=False,
        )
        embed.add_field(
            name="Archive Channel",
            value='```json\n"archive_channel_id": 1234567890123\n```\n'
            "Resolved tickets are archived here with transcript.\n"
            "Staff response triggers auto-close + archive.",
            inline=False,
        )
        embed.add_field(
            name="Ticket Limits",
            value='```json\n"max_open_tickets": 1\n```\n'
            "Max active tickets per user. Default: 1.",
            inline=False,
        )
        embed.add_field(
            name="DM Settings",
            value='```json\n"dm_settings": {\n'
            '  "enabled": true,\n'
            '  "close_dm": true\n'
            '}\n```\n'
            "Users get DM'd when ticket closes.",
            inline=False,
        )
        embed.add_field(
            name="Closed Naming",
            value='```json\n"closed_naming_format": "closed-{prefix}-{number}"\n```\n'
            "Placeholders: `{prefix}`, `{number}`, `{ticket_id}`\n"
            "Closed channels are restricted to `view_closed_roles` only.",
            inline=False,
        )
        embed.add_field(
            name="Ticket Bans",
            value='```json\n"ticket_ban": {\n'
            '  "enabled": true,\n'
            '  "offense_durations": {\n'
            '    "1": "3d", "2": "7d", "3": "14d", "4": "30d", "5": "permanent"\n'
            '  }\n'
            '}\n```\n'
            "Offense-based escalation when banning from pending tickets.\n"
            "Custom duration bans via `/ticket ban` do **not** count as offenses.",
            inline=False,
        )
        embed.add_field(
            name="Root Role",
            value='```json\n"root_role_ids": [1234567890123]\n```\n'
            "Roles that can use `/purge` and `/purgeall`.\n"
            "These commands require confirmation.",
            inline=False,
        )
        embed.set_footer(text="Page 5 of 6 | Use the dropdown to navigate")
        return embed

    def _troubleshooting_page(self) -> discord.Embed:
        embed = discord.Embed(
            title="Admin Help - Troubleshooting",
            description="Common issues and fixes.",
            color=discord.Color.red(),
        )
        embed.add_field(
            name="Commands not appearing",
            value=(
                "1. Bot needs `Use Application Commands` permission\n"
                "2. Run `/reload` to resync\n"
                "3. Check startup logs for errors\n"
                "4. Global commands may take up to 1 hour to propagate"
            ),
            inline=False,
        )
        embed.add_field(
            name="Panel not working",
            value=(
                "1. Check `channel_id` is valid in config\n"
                "2. Re-deploy with `/deploy`\n"
                "3. Bot needs Send Messages + Embed Links in panel channel\n"
                "4. Categories must have valid channel IDs"
            ),
            inline=False,
        )
        embed.add_field(
            name="Channel creation fails",
            value=(
                "1. `open_category_id` must be a category, not a channel\n"
                "2. Bot needs Manage Channels in that category\n"
                "3. Bot role must be above @everyone in that category"
            ),
            inline=False,
        )
        embed.add_field(
            name="DMs not delivered",
            value=(
                "1. User may have DMs disabled\n"
                "2. Staff sees a warning if DM fails\n"
                "3. Check logs for `discord.Forbidden`"
            ),
            inline=False,
        )
        embed.add_field(
            name="Config changes not applied",
            value=(
                "1. Run `/reload` after editing `config.json`\n"
                "2. Panel changes need `/deploy`\n"
                "3. Invalid JSON = old config retained\n"
                "4. Check logs for validation errors"
            ),
            inline=False,
        )
        embed.add_field(
            name="Database Backup",
            value="```bash\ncp tickets.db tickets_backup_$(date +%Y%m%d).db\n```",
            inline=False,
        )
        embed.set_footer(text="Page 6 of 6 | Use the dropdown to navigate")
        return embed


class AdminCog(commands.Cog):
    """Administrative commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @property
    def config_service(self):
        return self.bot.config_service

    @property
    def permission_service(self):
        return self.bot.permission_service

    @property
    def audit_service(self):
        return self.bot.audit_service

    @app_commands.command(name="reload", description="Hot-reload bot configuration from config.json")
    async def reload_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_reload"),
                    ephemeral=True,
                )
                return

            await interaction.response.defer()

            old_config = self.config_service.config.copy()
            try:
                self.config_service.load()
            except ConfigurationError as e:
                self.config_service._config = old_config
                self.config_service._loaded = True
                await interaction.followup.send(
                    msg.get("admin.reload_failed", error=e),
                    ephemeral=True,
                )
                return

            await self.audit_service.log(
                action="CONFIG_RELOADED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                details="Configuration reloaded successfully.",
            )

            await interaction.followup.send(
                msg.get("admin.reload_success"),
                ephemeral=True,
            )

        except Exception as e:
            logger.error("Error in /reload: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        f"Failed to reload configuration: {e}",
                        ephemeral=True,
                    )
                except Exception:
                    pass

    @app_commands.command(name="adminhelp", description="View complete admin documentation with configuration guide")
    async def adminhelp_command(self, interaction: discord.Interaction) -> None:
        try:
            msg = interaction.client.messages
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_admin_command"),
                    ephemeral=True,
                )
                return

            view = AdminHelpNavigationView()
            embed = view._get_page("setup")
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            logger.error("Error in /adminhelp: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        msg.get("errors.try_again"),
                        ephemeral=True,
                    )
                except Exception:
                    pass

    @app_commands.command(name="deploy", description="Deploy or update the ticket panel")
    @app_commands.describe(
        channel="The channel to deploy the panel in",
        type="Panel type: buttons or dropdown (overrides config)",
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="Buttons", value="buttons"),
        app_commands.Choice(name="Dropdown", value="dropdown"),
    ])
    async def deploy_command(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        type: Optional[app_commands.Choice[str]] = None,
    ) -> None:
        try:
            msg = interaction.client.messages
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_deploy"),
                    ephemeral=True,
                )
                return

            await interaction.response.defer()

            panel_config = self.config_service.get_ticket_panel()
            target_channel = channel
            if not target_channel:
                panel_channel_id = panel_config.get("channel_id")
                if panel_channel_id:
                    target_channel = interaction.guild.get_channel(panel_channel_id)
                if not target_channel:
                    await interaction.followup.send(
                        msg.get("admin.deploy_no_channel"),
                        ephemeral=True,
                    )
                    return

            categories = self.config_service.get_categories()
            panel_type = type.value if type else panel_config.get("type", "buttons")

            self.config_service._config.setdefault("ticket_panel", {})["type"] = panel_type
            self.config_service._save()

            embed_config = panel_config.get("embed", {})
            embed = discord.Embed(
                title=embed_config.get("title", "IRBW Support"),
                description=embed_config.get("description", "Need help? Select a category below to open a support ticket."),
                color=embed_config.get("color", 5814783),
            )
            footer = embed_config.get("footer", {})
            if footer.get("text"):
                embed.set_footer(text=footer["text"])

            if panel_type == "dropdown":
                from ui.panels import TicketPanelDropdownView
                view = TicketPanelDropdownView(categories)
            else:
                from ui.panels import TicketPanelButtonView
                view = TicketPanelButtonView(categories)

            old_message_id = panel_config.get("message_id")
            if old_message_id:
                try:
                    old_channel_id = panel_config.get("channel_id")
                    if old_channel_id:
                        old_channel = interaction.guild.get_channel(old_channel_id)
                        if old_channel:
                            old_msg = await old_channel.fetch_message(old_message_id)
                            try:
                                await old_msg.delete()
                            except Exception:
                                pass
                except Exception:
                    pass

            try:
                message = await target_channel.send(embed=embed, view=view)
            except Exception as e:
                logger.error("Failed to send panel message: %s", e)
                try:
                    await interaction.followup.send(
                        msg.get("admin.deploy_failed", error=e),
                        ephemeral=True,
                    )
                except Exception:
                    pass
                return
            self.config_service.set_panel_message_id(message.id)

            self.config_service._config.setdefault("ticket_panel", {})["channel_id"] = target_channel.id
            self.config_service._save()

            await self.audit_service.log(
                action="PANEL_DEPLOYED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                channel_id=target_channel.id,
                details=f"Ticket panel deployed to {target_channel.mention} (type: {panel_type}).",
            )

            await interaction.followup.send(
                msg.get("admin.deploy_success", channel=target_channel.mention, panel_type=panel_type),
                ephemeral=True,
            )

        except Exception as e:
            logger.error("Error in /deploy: %s", e, exc_info=True)
            msg = interaction.client.messages
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        msg.get("admin.deploy_failed_generic", error=e),
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        msg.get("admin.deploy_failed_generic", error=e),
                        ephemeral=True,
                    )
            except Exception:
                pass

    @app_commands.command(name="config", description="View or change bot configuration")
    @app_commands.describe(setting="The setting to view or change")
    @app_commands.choices(setting=[
        app_commands.Choice(name="View All", value="view_all"),
        app_commands.Choice(name="Max Open Tickets", value="max_open_tickets"),
        app_commands.Choice(name="Ticket Create Mode (everyone/roles)", value="ticket_create_mode"),
        app_commands.Choice(name="Panel Type (buttons/dropdown)", value="panel_type"),
        app_commands.Choice(name="Panel Embed Title", value="panel_title"),
        app_commands.Choice(name="Panel Embed Description", value="panel_description"),
        app_commands.Choice(name="Transcript Channel", value="transcript_channel"),
        app_commands.Choice(name="Audit Log Enabled", value="audit_log_enabled"),
        app_commands.Choice(name="Audit Log Channel", value="audit_log_channel"),
        app_commands.Choice(name="Closed Naming Format", value="closed_naming_format"),
    ])
    @app_commands.describe(value="New value for the setting")
    async def config_command(
        self,
        interaction: discord.Interaction,
        setting: app_commands.Choice[str],
        value: Optional[str] = None,
    ) -> None:
        try:
            msg = interaction.client.messages
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    msg.get("permissions.no_permission_config"),
                    ephemeral=True,
                )
                return

            cfg = self.config_service._config
            key = setting.value

            if value is None:
                current_values = {
                    "view_all": None,
                    "max_open_tickets": cfg.get("max_open_tickets", 1),
                    "ticket_create_mode": cfg.get("ticket_create_mode", "roles"),
                    "panel_type": cfg.get("ticket_panel", {}).get("type", "buttons"),
                    "panel_title": cfg.get("ticket_panel", {}).get("embed", {}).get("title", "IRBW Support"),
                    "panel_description": cfg.get("ticket_panel", {}).get("embed", {}).get("description", ""),
                    "transcript_channel": cfg.get("transcripts", {}).get("channel_id", 0),
                    "audit_log_enabled": cfg.get("audit_log", {}).get("enabled", True),
                    "audit_log_channel": cfg.get("audit_log", {}).get("channel_id", 0),
                    "closed_naming_format": cfg.get("closed_naming_format", "closed-{prefix}-{number}"),
                }

                if key == "view_all":
                    embed = discord.Embed(
                        title="Bot Configuration",
                        color=discord.Color.blurple(),
                    )
                    embed.add_field(name="Guild ID", value=str(cfg.get("guild_id", 0)), inline=True)
                    embed.add_field(name="Ticket Create Mode", value=cfg.get("ticket_create_mode", "roles"), inline=True)
                    embed.add_field(name="Max Open Tickets", value=str(cfg.get("max_open_tickets", 1)), inline=True)
                    panel = cfg.get("ticket_panel", {})
                    embed.add_field(name="Panel Type", value=panel.get("type", "buttons"), inline=True)
                    embed.add_field(name="Panel Channel", value=f"<#{panel.get('channel_id', 0)}>" if panel.get("channel_id") else "Not set", inline=True)
                    transcripts = cfg.get("transcripts", {})
                    embed.add_field(name="Transcript Channel", value=f"<#{transcripts.get('channel_id', 0)}>" if transcripts.get("channel_id") else "Not set", inline=True)
                    audit = cfg.get("audit_log", {})
                    embed.add_field(name="Audit Log", value="Enabled" if audit.get("enabled") else "Disabled", inline=True)
                    embed.add_field(name="Audit Channel", value=f"<#{audit.get('channel_id', 0)}>" if audit.get("channel_id") else "Not set", inline=True)
                    dm = cfg.get("dm_settings", {})
                    embed.add_field(name="DM Enabled", value="Enabled" if dm.get("enabled") else "Disabled", inline=True)
                    embed.add_field(name="DM Close", value=dm.get("close_dm", True), inline=True)
                    embed.add_field(name="Closed Format", value=f"`{cfg.get('closed_naming_format', 'closed-{prefix}-{number}')}`", inline=True)
                    cats = cfg.get("categories", {})
                    cat_list = "\n".join(f"**{c.get('display_name', k)}** (`{k}`)" for k, c in cats.items()) or "None"
                    embed.add_field(name="Categories", value=cat_list, inline=False)
                    embed.set_footer(text="Use /config setting:<name> value:<new_value> to change a setting")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                current = current_values.get(key, "Unknown")
                await interaction.response.send_message(
                    f"**{setting.name}**: `{current}`\n\n"
                    f"Use `/config setting:{setting.name} value:<new_value>` to change it.",
                    ephemeral=True,
                )
                return

            if key == "max_open_tickets":
                try:
                    num = int(value)
                    if num < 1:
                        raise ValueError
                except ValueError:
                    await interaction.response.send_message(msg.get("admin.invalid_integer"), ephemeral=True)
                    return
                cfg[key] = num

            elif key == "ticket_create_mode":
                if value.lower() not in ("everyone", "roles"):
                    await interaction.response.send_message(msg.get("admin.invalid_ticket_mode"), ephemeral=True)
                    return
                cfg["ticket_create_mode"] = value.lower()

            elif key == "panel_type":
                if value.lower() not in ("buttons", "dropdown"):
                    await interaction.response.send_message(msg.get("admin.invalid_ticket_type"), ephemeral=True)
                    return
                cfg.setdefault("ticket_panel", {})["type"] = value.lower()

            elif key == "panel_title":
                cfg.setdefault("ticket_panel", {}).setdefault("embed", {})["title"] = value

            elif key == "panel_description":
                cfg.setdefault("ticket_panel", {}).setdefault("embed", {})["description"] = value

            elif key == "transcript_channel":
                try:
                    cid = int(value.replace("<#", "").replace(">", ""))
                except ValueError:
                    await interaction.response.send_message(msg.get("admin.invalid_channel"), ephemeral=True)
                    return
                cfg.setdefault("transcripts", {})["channel_id"] = cid

            elif key == "audit_log_enabled":
                if value.lower() not in ("true", "false", "yes", "no", "1", "0"):
                    await interaction.response.send_message(msg.get("admin.invalid_boolean"), ephemeral=True)
                    return
                cfg.setdefault("audit_log", {})["enabled"] = value.lower() in ("true", "yes", "1")

            elif key == "audit_log_channel":
                try:
                    cid = int(value.replace("<#", "").replace(">", ""))
                except ValueError:
                    await interaction.response.send_message(msg.get("admin.invalid_channel"), ephemeral=True)
                    return
                cfg.setdefault("audit_log", {})["channel_id"] = cid

            elif key == "closed_naming_format":
                cfg["closed_naming_format"] = value

            self.config_service._save()

            await self.audit_service.log(
                action="CONFIG_CHANGED",
                actor_id=interaction.user.id,
                actor_name=str(interaction.user),
                details=f"Changed {setting.name} to '{value}'.",
            )

            await interaction.response.send_message(
                msg.get("admin.config_updated", setting=setting.name, value=value),
                ephemeral=True,
            )

        except Exception as e:
            logger.error("Error in /config: %s", e)
            if not interaction.response.is_done():
                try:
                    await interaction.response.send_message(
                        f"Failed to update configuration: {e}",
                        ephemeral=True,
                    )
                except Exception:
                    pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AdminCog(bot))
