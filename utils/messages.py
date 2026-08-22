from __future__ import annotations

import logging
import os
from typing import Any, Optional

import yaml

logger = logging.getLogger("ticket_bot.messages")


class MessageService:
    def __init__(self, filepath: str = "messages.yml") -> None:
        self._data: dict[str, Any] = {}
        self._persian_enabled: bool = False
        self._filepath = filepath
        self.load()

    def load(self) -> None:
        if not os.path.exists(self._filepath):
            logger.warning("messages.yml not found at %s, using empty messages", self._filepath)
            self._data = {}
            self._persian_enabled = False
            return
        try:
            with open(self._filepath, "r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
            self._persian_enabled = bool(self._data.get("language", {}).get("persian", False))
            logger.info("Loaded messages.yml (persian=%s)", self._persian_enabled)
        except Exception as e:
            logger.error("Failed to load messages.yml: %s", e)
            self._data = {}
            self._persian_enabled = False

    def reload(self) -> None:
        self.load()

    @property
    def persian_enabled(self) -> bool:
        return self._persian_enabled

    def _resolve(self, key: str) -> Any:
        parts = key.split(".")
        value: Any = self._data
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    def get(self, key: str, default: str = "", **kwargs: Any) -> str:
        value = self._resolve(key)
        if value is None:
            return default.format(**kwargs) if kwargs else default
        if isinstance(value, str):
            return value.format(**kwargs) if kwargs else value
        if isinstance(value, dict):
            en = value.get("en", "")
            if isinstance(en, str):
                return en.format(**kwargs) if kwargs else en
        return str(value)

    def get_persian(self, key: str, **kwargs: Any) -> Optional[str]:
        if not self._persian_enabled:
            return None
        value = self._resolve(key)
        if value is None:
            return None
        if isinstance(value, dict) and "fa" in value:
            fa = value["fa"]
            if isinstance(fa, str):
                return fa.format(**kwargs) if kwargs else fa
            if isinstance(fa, dict):
                text = fa.get("text", "") or fa.get("description", "") or fa.get("title", "")
                if text:
                    return text.format(**kwargs) if kwargs else text
        return None

    def has_persian(self, key: str) -> bool:
        if not self._persian_enabled:
            return False
        value = self._resolve(key)
        if isinstance(value, dict) and "fa" in value:
            return True
        return False

    def embed_title(self, key: str, **kwargs: Any) -> str:
        value = self._resolve(key)
        if isinstance(value, dict):
            if "en" in value:
                en = value["en"]
                if isinstance(en, dict):
                    title = en.get("title", "")
                    return title.format(**kwargs) if kwargs else title
            title = value.get("title", "")
            if title:
                return title.format(**kwargs) if kwargs else title
        if isinstance(value, str):
            return value.format(**kwargs) if kwargs else value
        return key

    def embed_description(self, key: str, **kwargs: Any) -> str:
        value = self._resolve(key)
        if isinstance(value, dict):
            if "en" in value:
                en = value["en"]
                if isinstance(en, dict):
                    desc = en.get("description", "")
                    return desc.format(**kwargs) if kwargs else desc
            desc = value.get("description", "")
            if desc:
                return desc.format(**kwargs) if kwargs else desc
        return ""

    def embed_footer(self, key: str, **kwargs: Any) -> str:
        value = self._resolve(key)
        if isinstance(value, dict):
            if "en" in value:
                en = value["en"]
                if isinstance(en, dict):
                    footer = en.get("footer", "")
                    return footer.format(**kwargs) if kwargs else footer
            footer = value.get("footer", "")
            if footer:
                return footer.format(**kwargs) if kwargs else footer
        return ""

    def persian_title(self, key: str, **kwargs: Any) -> Optional[str]:
        if not self._persian_enabled:
            return None
        value = self._resolve(key)
        if isinstance(value, dict) and "fa" in value:
            fa = value["fa"]
            if isinstance(fa, dict):
                title = fa.get("title", "")
                return title.format(**kwargs) if kwargs else title
        return None

    def persian_description(self, key: str, **kwargs: Any) -> Optional[str]:
        if not self._persian_enabled:
            return None
        value = self._resolve(key)
        if isinstance(value, dict) and "fa" in value:
            fa = value["fa"]
            if isinstance(fa, dict):
                desc = fa.get("description", "")
                return desc.format(**kwargs) if kwargs else desc
        return None

    def persian_footer(self, key: str, **kwargs: Any) -> Optional[str]:
        if not self._persian_enabled:
            return None
        value = self._resolve(key)
        if isinstance(value, dict) and "fa" in value:
            fa = value["fa"]
            if isinstance(fa, dict):
                footer = fa.get("footer", "")
                return footer.format(**kwargs) if kwargs else footer
        return None

    def build_dual_embed(
        self,
        key: str,
        *,
        color: int = 5814783,
        fields: Optional[list[tuple[str, str, bool]]] = None,
        fa_fields: Optional[list[tuple[str, str, bool]]] = None,
        thumbnail: Optional[str] = None,
        fa_kwargs: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> list[Any]:
        """Build English embed + optional Persian embed. Returns list of discord.Embed."""
        import discord

        embeds = []

        en_title = self.embed_title(key, **kwargs)
        en_desc = self.embed_description(key, **kwargs)
        en_footer = self.embed_footer(key, **kwargs)
        embed = discord.Embed(title=en_title, description=en_desc, color=color)
        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
        if en_footer:
            embed.set_footer(text=en_footer)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        embeds.append(embed)

        if self._persian_enabled:
            pk = {**kwargs, **(fa_kwargs or {})}
            fa_title = self.persian_title(key, **pk)
            fa_desc = self.persian_description(key, **pk)
            fa_footer = self.persian_footer(key, **pk)
            if fa_title or fa_desc:
                fa_embed = discord.Embed(
                    title=fa_title or en_title,
                    description=fa_desc or en_desc,
                    color=color,
                )
                use_fields = fa_fields if fa_fields is not None else fields
                if use_fields:
                    for name, value, inline in use_fields:
                        fa_embed.add_field(name=name, value=value, inline=inline)
                if fa_footer:
                    fa_embed.set_footer(text=fa_footer)
                if thumbnail:
                    fa_embed.set_thumbnail(url=thumbnail)
                embeds.append(fa_embed)

        return embeds

    async def send_dual_dm(
        self,
        member: Any,
        *,
        key: str,
        color: int = 8487426,
        fields: Optional[list[tuple[str, str, bool]]] = None,
        fa_fields: Optional[list[tuple[str, str, bool]]] = None,
        fa_kwargs: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> bool:
        """Build dual embeds and send as DM. Returns True on success."""
        import discord as _discord

        embeds = self.build_dual_embed(
            key, color=color, fields=fields, fa_fields=fa_fields, fa_kwargs=fa_kwargs, **kwargs,
        )
        try:
            await member.send(embeds=embeds)
            return True
        except _discord.Forbidden:
            return False
        except Exception:
            return False
