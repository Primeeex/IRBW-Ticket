from __future__ import annotations

from typing import Any

import discord

from utils.permissions import PERMISSION_KEYS, PERMISSION_DESCRIPTIONS, ROLE_PRESETS

GLOBAL_VALUE = "__global__"

_INDIVIDUAL_KEYS = [k for k in PERMISSION_KEYS if k not in ROLE_PRESETS]


class PresetSelect(discord.ui.Select):
    """Select menu for choosing a role preset bundle."""

    def __init__(self, custom_id: str = "preset_select", custom_presets: list[dict] | None = None) -> None:
        options = []
        for key, perms in ROLE_PRESETS.items():
            desc = PERMISSION_DESCRIPTIONS.get(key, key)
            perm_list = ", ".join(p.replace("ticket_", "").replace("_", " ") for p in perms)
            options.append(
                discord.SelectOption(
                    label=key,
                    value=key,
                    description=f"{perm_list[:95]}",
                )
            )
        if custom_presets:
            for cp in custom_presets:
                perm_keys = cp.get("permission_keys", [])
                perm_list = ", ".join(p.replace("ticket_", "").replace("_", " ") for p in perm_keys)
                options.append(
                    discord.SelectOption(
                        label=cp["name"],
                        value=cp["name"],
                        description=f"Custom: {perm_list[:80]}",
                    )
                )
        super().__init__(
            placeholder="Select a role preset (bundle)...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=custom_id,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.selected_permission = self.values[0]
        self.view.selected_is_preset = True

        perm_display = self.values[0]
        preset_perms = ROLE_PRESETS.get(self.values[0], [])
        perm_list = ", ".join(p.replace("ticket_", "").replace("_", " ") for p in preset_perms)
        cat_display = "Global"
        view = self.view
        if hasattr(view, "selected_category") and view.selected_category is not None:
            if view.selected_category == GLOBAL_VALUE:
                cat_display = "Global"
            elif view.selected_category in getattr(view, "categories", {}):
                cat_display = view.categories[view.selected_category].get("display_name", view.selected_category.title())

        embed = discord.Embed(
            title=getattr(view, "title", "Permission Selection"),
            description=getattr(view, "description", "Use the dropdowns below to configure, then click **Confirm**."),
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Preset", value=f"```{perm_display}```", inline=True)
        embed.add_field(name="Category", value=f"```{cat_display}```", inline=True)
        if perm_list:
            embed.add_field(name="Includes", value=perm_list, inline=False)
        embed.add_field(name="Status", value="Ready to confirm", inline=False)

        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            try:
                await interaction.response.defer()
            except Exception:
                pass


class PermissionKeySelect(discord.ui.Select):
    """Select menu for choosing an individual permission key."""

    def __init__(self, custom_id: str = "permission_key_select") -> None:
        options = []
        for key in _INDIVIDUAL_KEYS:
            desc = PERMISSION_DESCRIPTIONS.get(key, key)
            display = key.replace("_", " ").title()
            options.append(
                discord.SelectOption(
                    label=display,
                    value=key,
                    description=desc[:100] if desc else key,
                )
            )
        super().__init__(
            placeholder="Or select an individual permission...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=custom_id,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.selected_permission = self.values[0]  # type: ignore
        self.view.selected_is_preset = False  # type: ignore

        perm_display = self.values[0].replace("_", " ").title()
        cat_display = "Global"
        view = self.view
        if hasattr(view, "selected_category") and view.selected_category is not None:
            if view.selected_category == GLOBAL_VALUE:
                cat_display = "Global"
            elif view.selected_category in getattr(view, "categories", {}):
                cat_display = view.categories[view.selected_category].get("display_name", view.selected_category.title())

        embed = discord.Embed(
            title=getattr(view, "title", "Permission Selection"),
            description=getattr(view, "description", "Use the dropdowns below to configure, then click **Confirm**."),
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Permission", value=f"```{perm_display}```", inline=True)
        embed.add_field(name="Category", value=f"```{cat_display}```", inline=True)
        embed.add_field(name="Status", value="Ready to confirm", inline=False)

        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            try:
                await interaction.response.defer()
            except Exception:
                pass


class CategorySelect(discord.ui.Select):
    """Select menu for choosing a ticket category."""

    def __init__(self, categories: dict[str, Any], include_global: bool = True, custom_id: str = "category_select") -> None:
        options = []
        if include_global:
            options.append(
                discord.SelectOption(
                    label="Global",
                    value=GLOBAL_VALUE,
                    description="Apply to all categories",
                )
            )
        for key, cat_config in categories.items():
            display = cat_config.get("display_name", key.title())
            options.append(
                discord.SelectOption(
                    label=display,
                    value=key,
                    description=f"Apply to {display} tickets",
                )
            )
        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=custom_id,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.selected_category = self.values[0]  # type: ignore
        await interaction.response.defer()


class PermissionCategorySelect(discord.ui.Select):
    """Select menu for category-specific permission selection."""

    def __init__(self, categories: dict[str, Any], custom_id: str = "perm_category_select") -> None:
        options = [
            discord.SelectOption(
                label="Global",
                value=GLOBAL_VALUE,
                description="Apply to all categories",
            )
        ]
        for key, cat_config in categories.items():
            display = cat_config.get("display_name", key.title())
            options.append(
                discord.SelectOption(
                    label=display,
                    value=key,
                    description=f"Apply to {display} tickets",
                )
            )
        super().__init__(
            placeholder="Select a category scope...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=custom_id,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        self.view.selected_category = self.values[0]  # type: ignore

        view = self.view
        perm_display = "Not selected"
        if hasattr(view, "selected_permission") and view.selected_permission:
            perm_display = view.selected_permission.replace("_", " ").title()

        if self.values[0] == GLOBAL_VALUE:
            cat_display = "Global"
        elif self.values[0] in getattr(view, "categories", {}):
            cat_display = view.categories[self.values[0]].get("display_name", self.values[0].title())
        else:
            cat_display = "Global"

        embed = discord.Embed(
            title=getattr(view, "title", "Permission Selection"),
            description=getattr(view, "description", "Use the dropdowns below to configure, then click **Confirm**."),
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Permission", value=f"```{perm_display}```", inline=True)
        embed.add_field(name="Category", value=f"```{cat_display}```", inline=True)
        embed.add_field(
            name="Status",
            value="Ready to confirm" if hasattr(view, "selected_permission") and view.selected_permission else "Please select a permission key",
            inline=False,
        )

        try:
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception:
            try:
                await interaction.response.defer()
            except Exception:
                pass
