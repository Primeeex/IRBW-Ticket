from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.permissions import PERMISSION_KEYS, PERMISSION_DESCRIPTIONS, ROLE_PRESETS
from ui.selects import PermissionKeySelect, PermissionCategorySelect, PresetSelect, GLOBAL_VALUE

logger = logging.getLogger("ticket_bot.cogs.permissions")

_INDIVIDUAL_KEYS = [k for k in PERMISSION_KEYS if k not in ROLE_PRESETS]


def _key_choices() -> list[app_commands.Choice[str]]:
    return [
        app_commands.Choice(name=k.replace("_", " ").title(), value=k)
        for k in _INDIVIDUAL_KEYS[:25]
    ]


class PermissionKeyConfirmView(discord.ui.View):
    """View for selecting a permission key, category, and confirming."""

    def __init__(self, action: str, categories: dict, custom_presets: list[dict] | None = None) -> None:
        super().__init__(timeout=120)
        self.action = action
        self.selected_permission: Optional[str] = None
        self.selected_category: Optional[str] = None
        self.selected_is_preset: bool = False
        self.categories = categories
        self.confirmed = False

        self.add_item(PresetSelect(custom_id=f"perm_preset_{action}_{id(self)}", custom_presets=custom_presets))
        self.add_item(PermissionKeySelect(custom_id=f"perm_key_{action}_{id(self)}"))
        self.add_item(PermissionCategorySelect(categories, custom_id=f"perm_cat_{action}_{id(self)}"))

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green, row=2)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        msg = interaction.client.messages
        if not self.selected_permission:
            try:
                await interaction.response.send_message(
                    msg.get("permissions_mgmt.select_key_first"),
                    ephemeral=True,
                )
            except Exception:
                pass
            return
        self.confirmed = True
        try:
            await interaction.response.defer()
        except Exception:
            pass
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, row=2)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        msg = interaction.client.messages
        try:
            await interaction.response.send_message(msg.get("permissions_mgmt.cancelled"), ephemeral=True)
        except Exception:
            pass
        self.confirmed = False
        self.stop()


def _resolve_category_display(categories: dict, category_value: Optional[str]) -> tuple[str, str]:
    """Returns (category_db_value, display_name)."""
    if not category_value or category_value == GLOBAL_VALUE:
        return "", "Global"
    cat_config = categories.get(category_value)
    if cat_config:
        return category_value, cat_config.get("display_name", category_value.title())
    return category_value, category_value.title()


class _PermissionListView(discord.ui.View):
    def __init__(self, user_id: int, pages: list[discord.Embed]) -> None:
        super().__init__(timeout=120)
        self.user_id = user_id
        self.pages = pages
        self.current = 0
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_button.disabled = self.current == 0
        self.next_button.disabled = self.current == len(self.pages) - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        msg = interaction.client.messages
        if interaction.user.id != self.user_id:
            try:
                await interaction.response.send_message(msg.get("permissions_mgmt.not_for_you"), ephemeral=True)
            except Exception:
                pass
            return
        self.current = max(0, self.current - 1)
        self._update_buttons()
        try:
            await interaction.response.edit_message(embed=self.pages[self.current], view=self)
        except Exception:
            pass

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        msg = interaction.client.messages
        if interaction.user.id != self.user_id:
            try:
                await interaction.response.send_message(msg.get("permissions_mgmt.not_for_you"), ephemeral=True)
            except Exception:
                pass
            return
        self.current = min(len(self.pages) - 1, self.current + 1)
        self._update_buttons()
        try:
            await interaction.response.edit_message(embed=self.pages[self.current], view=self)
        except Exception:
            pass


class PermissionsCog(commands.Cog):
    """Permission management commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.permission_group = app_commands.Group(
            name="permission",
            description="Manage bot permissions",
        )
        self._register_commands()

    @property
    def config_service(self):
        return self.bot.config_service

    @property
    def permission_service(self):
        return self.bot.permission_service

    @property
    def audit_service(self):
        return self.bot.audit_service

    def _register_commands(self) -> None:
        @self.permission_group.command(name="list", description="List all permission keys and their configuration")
        async def permission_list(interaction: discord.Interaction) -> None:
            try:
                msg = interaction.client.messages
                all_perms = await self.permission_service.get_all_permissions()
                categories = self.config_service.get_categories()

                grouped: dict[str, list[dict]] = {}
                for p in all_perms:
                    key = p["permission_key"]
                    if key not in grouped:
                        grouped[key] = []
                    grouped[key].append(p)

                total_configured = len(all_perms)
                total_keys = len(PERMISSION_KEYS)

                PAGE_SIZE = 25
                pages: list[discord.Embed] = []
                keys_list = list(PERMISSION_KEYS)

                for page_start in range(0, len(keys_list), PAGE_SIZE):
                    page_keys = keys_list[page_start:page_start + PAGE_SIZE]
                    page_num = len(pages) + 1
                    total_pages = (len(keys_list) + PAGE_SIZE - 1) // PAGE_SIZE

                    embed = discord.Embed(
                        title="Permission Keys",
                        description="All available permission keys and their current configuration.\n"
                        "Use `/permission add` to grant a permission to a role.",
                        color=5814783,
                    )

                    for key in page_keys:
                        desc = PERMISSION_DESCRIPTIONS.get(key, "")
                        entries = grouped.get(key, [])

                        if entries:
                            lines = []
                            for e in entries:
                                cat_display = e["category"].title() if e["category"] else "Global"
                                lines.append(f"<@&{e['role_id']}> ({cat_display})")
                            value = "\n".join(lines)
                        else:
                            value = "*Not configured*"

                        embed.add_field(
                            name=f"`{key}`",
                            value=f"{desc}\n{value}",
                            inline=False,
                        )

                    embed.set_footer(
                        text=f"Page {page_num}/{total_pages} — {total_configured} roles configured across {total_keys} permission keys"
                    )
                    pages.append(embed)

                if len(pages) == 1:
                    await interaction.response.send_message(embed=pages[0], ephemeral=True)
                else:
                    view = _PermissionListView(interaction.user.id, pages)
                    await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)

            except Exception as e:
                logger.error("Error in /permission list: %s", e)
                if not interaction.response.is_done():
                    try:
                        await interaction.response.send_message(
                            msg.get("errors.try_again"),
                            ephemeral=True,
                        )
                    except Exception:
                        pass

        @self.permission_group.command(name="add", description="Add a permission to a role")
        @app_commands.describe(
            role="The role to give permission to",
            key="Permission key (optional - dropdown shown if omitted)",
            category="Category scope (optional - dropdown shown if omitted)",
        )
        @app_commands.choices(key=_key_choices())
        async def permission_add(
            interaction: discord.Interaction,
            role: discord.Role,
            key: Optional[app_commands.Choice[str]] = None,
            category: Optional[str] = None,
        ) -> None:
            try:
                msg = interaction.client.messages
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message(
                        msg.get("permissions.no_permission_manage"),
                        ephemeral=True,
                    )
                    return

                categories = self.config_service.get_categories()

                if key:
                    perm_key = key.value
                    cat_db, cat_display = _resolve_category_display(categories, category)

                    count = await self.permission_service.add_permission(perm_key, cat_db, role.id)

                    await self.audit_service.log(
                        action="PERMISSION_CHANGED",
                        actor_id=interaction.user.id,
                        actor_name=str(interaction.user),
                        target_id=role.id,
                        target_name=str(role),
                        category=cat_db or None,
                        details=f"Added permission '{perm_key}' ({cat_display}) to role {role}.",
                    )

                    if count > 1:
                        custom_presets = await self.permission_service.get_all_custom_presets()
                        all_presets = ROLE_PRESETS.copy()
                        for cp in custom_presets:
                            all_presets[cp["name"]] = cp.get("permission_keys", [])
                        preset_perms = all_presets.get(perm_key, [])
                        perm_list = ", ".join(p.replace("ticket_", "").replace("_", " ") for p in preset_perms)
                        await interaction.response.send_message(
                            f"Preset **{perm_key}** ({count} permissions) granted to {role.mention} ({cat_display}).\n"
                            f"Permissions: {perm_list}",
                            ephemeral=True,
                        )
                    else:
                        await interaction.response.send_message(
                            f"Permission **{perm_key.replace('_', ' ').title()}** "
                            f"({cat_display}) granted to {role.mention}.",
                            ephemeral=True,
                        )
                    return

                view = PermissionKeyConfirmView("add", categories, custom_presets=await self.permission_service.get_all_custom_presets())

                embed = discord.Embed(
                    title="Permission Add",
                    description=msg.get("permissions_mgmt.add_description")
                    + "then click **Confirm**.",
                    color=discord.Color.blurple(),
                )
                embed.add_field(name="Permission", value="```Not selected```", inline=True)
                embed.add_field(name="Category", value="```Global```", inline=True)
                embed.add_field(name="Target Role", value=role.mention, inline=True)

                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                await view.wait()

                if not view.confirmed or not view.selected_permission:
                    return

                cat_db, cat_display = _resolve_category_display(categories, view.selected_category)

                count = await self.permission_service.add_permission(view.selected_permission, cat_db, role.id)

                await self.audit_service.log(
                    action="PERMISSION_CHANGED",
                    actor_id=interaction.user.id,
                    actor_name=str(interaction.user),
                    target_id=role.id,
                    target_name=str(role),
                    category=cat_db or None,
                    details=f"Added permission '{view.selected_permission}' ({cat_display}) to role {role}.",
                )

                if count > 1:
                    custom_presets = await self.permission_service.get_all_custom_presets()
                    all_presets = ROLE_PRESETS.copy()
                    for cp in custom_presets:
                        all_presets[cp["name"]] = cp.get("permission_keys", [])
                    preset_perms = all_presets.get(view.selected_permission, [])
                    perm_list = ", ".join(p.replace("ticket_", "").replace("_", " ") for p in preset_perms)
                    await interaction.followup.send(
                        f"Preset **{view.selected_permission}** ({count} permissions) granted to {role.mention} ({cat_display}).\n"
                        f"Permissions: {perm_list}",
                        ephemeral=True,
                    )
                else:
                    await interaction.followup.send(
                        f"Permission **{view.selected_permission.replace('_', ' ').title()}** "
                        f"({cat_display}) granted to {role.mention}.",
                        ephemeral=True,
                    )

            except Exception as e:
                logger.error("Error in /permission add: %s", e)
                if not interaction.response.is_done():
                    try:
                        await interaction.response.send_message(
                            f"Failed to add permission: {e}",
                            ephemeral=True,
                        )
                    except Exception:
                        pass

        @self.permission_group.command(name="remove", description="Remove a permission from a role")
        @app_commands.describe(
            role="The role to remove permission from",
            key="Permission key (optional - dropdown shown if omitted)",
            category="Category scope (optional - dropdown shown if omitted)",
        )
        @app_commands.choices(key=_key_choices())
        async def permission_remove(
            interaction: discord.Interaction,
            role: discord.Role,
            key: Optional[app_commands.Choice[str]] = None,
            category: Optional[str] = None,
        ) -> None:
            try:
                msg = interaction.client.messages
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message(
                        msg.get("permissions.no_permission_manage"),
                        ephemeral=True,
                    )
                    return

                categories = self.config_service.get_categories()

                if key:
                    perm_key = key.value
                    cat_db, cat_display = _resolve_category_display(categories, category)

                    count = await self.permission_service.remove_permission(perm_key, cat_db, role.id)

                    if count > 0:
                        await self.audit_service.log(
                            action="PERMISSION_CHANGED",
                            actor_id=interaction.user.id,
                            actor_name=str(interaction.user),
                            target_id=role.id,
                            target_name=str(role),
                            category=cat_db or None,
                            details=f"Removed permission '{perm_key}' ({cat_display}) from role {role}.",
                        )
                        if count > 1:
                            await interaction.response.send_message(
                                f"Preset **{perm_key}** ({count} permissions) revoked from {role.mention} ({cat_display}).",
                                ephemeral=True,
                            )
                        else:
                            await interaction.response.send_message(
                                f"Permission **{perm_key.replace('_', ' ').title()}** "
                                f"({cat_display}) revoked from {role.mention}.",
                                ephemeral=True,
                            )
                    else:
                        await interaction.response.send_message(
                            f"No matching permission found for "
                            f"**{perm_key.replace('_', ' ').title()}** "
                            f"({cat_display}) on {role.mention}.",
                            ephemeral=True,
                        )
                    return

                view = PermissionKeyConfirmView("remove", categories, custom_presets=await self.permission_service.get_all_custom_presets())

                embed = discord.Embed(
                    title="Permission Remove",
                    description=msg.get("permissions_mgmt.remove_description")
                    + "then click **Confirm**.",
                    color=discord.Color.orange(),
                )
                embed.add_field(name="Permission", value="```Not selected```", inline=True)
                embed.add_field(name="Category", value="```Global```", inline=True)
                embed.add_field(name="Target Role", value=role.mention, inline=True)

                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                await view.wait()

                if not view.confirmed or not view.selected_permission:
                    return

                cat_db, cat_display = _resolve_category_display(categories, view.selected_category)

                count = await self.permission_service.remove_permission(view.selected_permission, cat_db, role.id)

                if count > 0:
                    await self.audit_service.log(
                        action="PERMISSION_CHANGED",
                        actor_id=interaction.user.id,
                        actor_name=str(interaction.user),
                        target_id=role.id,
                        target_name=str(role),
                        category=cat_db or None,
                        details=f"Removed permission '{view.selected_permission}' ({cat_display}) from role {role}.",
                    )
                    if count > 1:
                        await interaction.followup.send(
                            f"Preset **{view.selected_permission}** ({count} permissions) revoked from {role.mention} ({cat_display}).",
                            ephemeral=True,
                        )
                    else:
                        await interaction.followup.send(
                            f"Permission **{view.selected_permission.replace('_', ' ').title()}** "
                            f"({cat_display}) revoked from {role.mention}.",
                            ephemeral=True,
                        )
                else:
                    await interaction.followup.send(
                        f"No matching permission found for "
                        f"**{view.selected_permission.replace('_', ' ').title()}** "
                        f"({cat_display}) on {role.mention}.",
                        ephemeral=True,
                    )

            except Exception as e:
                logger.error("Error in /permission remove: %s", e)
                if not interaction.response.is_done():
                    try:
                        await interaction.response.send_message(
                            f"Failed to remove permission: {e}",
                            ephemeral=True,
                        )
                    except Exception:
                        pass

        preset_group = app_commands.Group(
            name="preset",
            description="Manage custom permission presets",
            parent=self.permission_group,
        )

        @preset_group.command(name="create", description="Create a custom permission preset bundle")
        @app_commands.describe(
            name="Preset name (e.g., 'support_team')",
            description="Short description of what this preset grants",
            keys="Comma-separated permission keys (e.g., 'ticket_create,ticket_close,ticket_claim')",
        )
        async def preset_create(
            interaction: discord.Interaction,
            name: str,
            description: str,
            keys: str,
        ) -> None:
            try:
                msg = interaction.client.messages
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message(
                        msg.get("permissions.no_permission_presets"),
                        ephemeral=True,
                    )
                    return

                perm_keys = [k.strip() for k in keys.split(",") if k.strip()]
                if not perm_keys:
                    await interaction.response.send_message(
                        "You must provide at least one permission key.",
                        ephemeral=True,
                    )
                    return

                invalid = [k for k in perm_keys if k not in PERMISSION_KEYS]
                if invalid:
                    await interaction.response.send_message(
                        f"Invalid permission keys: {', '.join(invalid)}.\n"
                        f"Valid keys: {', '.join(sorted(PERMISSION_KEYS))}",
                        ephemeral=True,
                    )
                    return

                existing = await self.permission_service.get_custom_preset(name)
                if existing:
                    await interaction.response.send_message(
                        f"Preset **{name}** already exists. Use `/permission preset delete` first to remove it.",
                        ephemeral=True,
                    )
                    return

                await self.permission_service.create_custom_preset(name, description, perm_keys)

                await self.audit_service.log(
                    action="PRESET_CREATED",
                    actor_id=interaction.user.id,
                    actor_name=str(interaction.user),
                    target_id=0,
                    target_name=name,
                    details=f"Created custom preset '{name}' with {len(perm_keys)} permissions: {', '.join(perm_keys)}",
                )

                keys_display = ", ".join(f"`{k}`" for k in perm_keys)
                await interaction.response.send_message(
                    f"Custom preset **{name}** created with {len(perm_keys)} permissions:\n{keys_display}",
                    ephemeral=True,
                )

            except Exception as e:
                logger.error("Error in /permission preset create: %s", e)
                if not interaction.response.is_done():
                    try:
                        await interaction.response.send_message(
                            f"Failed to create preset: {e}",
                            ephemeral=True,
                        )
                    except Exception:
                        pass

        @preset_group.command(name="delete", description="Delete a custom permission preset")
        @app_commands.describe(
            name="Preset name to delete",
        )
        async def preset_delete(
            interaction: discord.Interaction,
            name: str,
        ) -> None:
            try:
                msg = interaction.client.messages
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message(
                        msg.get("permissions.no_permission_presets"),
                        ephemeral=True,
                    )
                    return

                deleted = await self.permission_service.delete_custom_preset(name)
                if deleted:
                    await self.audit_service.log(
                        action="PRESET_DELETED",
                        actor_id=interaction.user.id,
                        actor_name=str(interaction.user),
                        target_id=0,
                        target_name=name,
                        details=f"Deleted custom preset '{name}'",
                    )
                    await interaction.response.send_message(
                        f"Custom preset **{name}** deleted.",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        f"Preset **{name}** not found.",
                        ephemeral=True,
                    )

            except Exception as e:
                logger.error("Error in /permission preset delete: %s", e)
                if not interaction.response.is_done():
                    try:
                        await interaction.response.send_message(
                            f"Failed to delete preset: {e}",
                            ephemeral=True,
                        )
                    except Exception:
                        pass

        @preset_group.command(name="list", description="List all custom permission presets")
        async def preset_list(interaction: discord.Interaction) -> None:
            try:
                msg = interaction.client.messages
                if not interaction.user.guild_permissions.administrator:
                    await interaction.response.send_message(
                        msg.get("permissions.no_permission_view_presets"),
                        ephemeral=True,
                    )
                    return

                custom_presets = await self.permission_service.get_all_custom_presets()

                if not custom_presets:
                    await interaction.response.send_message(
                        msg.get("permissions_mgmt.no_custom_presets"),
                        ephemeral=True,
                    )
                    return

                PAGE_SIZE = 5
                pages: list[discord.Embed] = []

                for page_start in range(0, len(custom_presets), PAGE_SIZE):
                    page = custom_presets[page_start:page_start + PAGE_SIZE]
                    page_num = len(pages) + 1
                    total_pages = (len(custom_presets) + PAGE_SIZE - 1) // PAGE_SIZE

                    embed = discord.Embed(
                        title="Custom Presets",
                        description=msg.get("permissions_mgmt.preset_custom_description"),
                        color=discord.Color.blurple(),
                    )

                    for cp in page:
                        perm_keys = cp.get("permission_keys", [])
                        keys_display = ", ".join(f"`{k}`" for k in perm_keys)
                        embed.add_field(
                            name=f"**{cp['name']}**",
                            value=f"{cp['description']}\nPermissions ({len(perm_keys)}): {keys_display}",
                            inline=False,
                        )

                    embed.set_footer(text=f"Page {page_num}/{total_pages} — {len(custom_presets)} custom presets")
                    pages.append(embed)

                if len(pages) == 1:
                    await interaction.response.send_message(embed=pages[0], ephemeral=True)
                else:
                    view = _PermissionListView(interaction.user.id, pages)
                    await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)

            except Exception as e:
                logger.error("Error in /permission preset list: %s", e)
                if not interaction.response.is_done():
                    try:
                        await interaction.response.send_message(
                            f"Failed to list presets: {e}",
                            ephemeral=True,
                        )
                    except Exception:
                        pass


async def setup(bot: commands.Bot) -> None:
    cog = PermissionsCog(bot)
    bot.tree.add_command(cog.permission_group)
    await bot.add_cog(cog)
