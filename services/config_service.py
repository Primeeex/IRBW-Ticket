from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

from utils.errors import ConfigurationError

logger = logging.getLogger("ticket_bot.config")


class ConfigService:
    def __init__(self, config_path: str = "config.json") -> None:
        self.config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self._loaded = False

    @property
    def config(self) -> dict[str, Any]:
        if not self._loaded:
            raise ConfigurationError("Configuration not loaded.")
        return self._config

    def load(self) -> dict[str, Any]:
        if not self.config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {self.config_path}. "
                "Copy config.example.json to config.json and fill in the required values."
            )
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            self._loaded = True
            self._validate_basics()
            logger.info("Configuration loaded successfully from %s", self.config_path)
            return self._config
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in configuration file: {e}")

    def _validate_basics(self) -> None:
        if not self._config.get("guild_id"):
            raise ConfigurationError("guild_id is required in config.json")

        categories = self._config.get("categories", {})
        if not categories:
            logger.warning("No ticket categories defined in configuration.")

        for cat_key, cat_config in categories.items():
            if not cat_config.get("display_name"):
                raise ConfigurationError(f"Category '{cat_key}' missing display_name")
            if not cat_config.get("pending_channel_id"):
                logger.warning("Category '%s' has no pending_channel_id configured.", cat_key)
            if not cat_config.get("open_category_id"):
                logger.warning("Category '%s' has no open_category_id configured.", cat_key)

    def get_guild_id(self) -> int:
        return self._config.get("guild_id", 0)

    def get_category(self, category: str) -> Optional[dict[str, Any]]:
        return self._config.get("categories", {}).get(category)

    def get_categories(self) -> dict[str, Any]:
        return self._config.get("categories", {})

    def get_ticket_panel(self) -> dict[str, Any]:
        return self._config.get("ticket_panel", {})

    def get_ui(self) -> dict[str, Any]:
        return self._config.get("ui", {})

    def get_transcripts(self) -> dict[str, Any]:
        return self._config.get("transcripts", {})

    def get_audit_log(self) -> dict[str, Any]:
        return self._config.get("audit_log", {})

    def get_dm_settings(self) -> dict[str, Any]:
        return self._config.get("dm_settings", {})

    def get_max_open_tickets(self) -> int:
        return self._config.get("max_open_tickets", 1)

    def get_closed_naming_format(self) -> str:
        return self._config.get("closed_naming_format", "closed-{prefix}-{number}")


    def set_panel_message_id(self, message_id: int) -> None:
        self._config.setdefault("ticket_panel", {})["message_id"] = message_id
        self._save()

    def _save(self) -> None:
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2)
            logger.info("Configuration saved to %s", self.config_path)
        except Exception as e:
            logger.error("Failed to save configuration: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)
