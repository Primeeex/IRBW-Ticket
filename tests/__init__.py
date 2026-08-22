import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_async(coro):
    """Helper to run async functions in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


def get_loop():
    """Get or create event loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


loop = get_loop()


class TestDatabase(unittest.TestCase):
    """Test database operations."""

    def setUp(self):
        from database.database import Database
        self.db = Database(":memory:")
        loop.run_until_complete(self.db.connect())

    def tearDown(self):
        loop.run_until_complete(self.db.close())

    def test_create_user(self):
        user = loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )
        self.assertEqual(user["user_id"], 12345)
        self.assertEqual(user["username"], "TestUser")

    def test_get_or_create_user_existing(self):
        loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )
        updated = loop.run_until_complete(
            self.db.get_or_create_user(12345, "UpdatedUser")
        )
        self.assertEqual(updated["username"], "UpdatedUser")

    def test_ticket_counter(self):
        id1 = loop.run_until_complete(
            self.db.get_next_ticket_number("general", "general")
        )
        id2 = loop.run_until_complete(
            self.db.get_next_ticket_number("general", "general")
        )
        id3 = loop.run_until_complete(
            self.db.get_next_ticket_number("appeal", "appeal")
        )
        self.assertEqual(id1, "general-0001")
        self.assertEqual(id2, "general-0002")
        self.assertEqual(id3, "appeal-0001")

    def test_create_ticket(self):
        loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )
        ticket = loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="general-0001",
                internal_id=1,
                category="general",
                user_id=12345,
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        self.assertEqual(ticket["ticket_id"], "general-0001")
        self.assertEqual(ticket["status"], "PENDING")

    def test_get_ticket(self):
        loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )
        loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="general-0001",
                internal_id=1,
                category="general",
                user_id=12345,
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        ticket = loop.run_until_complete(
            self.db.get_ticket("general-0001")
        )
        self.assertIsNotNone(ticket)
        self.assertEqual(ticket["ticket_id"], "general-0001")

    def test_get_ticket_not_found(self):
        ticket = loop.run_until_complete(
            self.db.get_ticket("nonexistent-001")
        )
        self.assertIsNone(ticket)

    def test_update_ticket_status(self):
        loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )
        loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="general-0001",
                internal_id=1,
                category="general",
                user_id=12345,
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        loop.run_until_complete(
            self.db.update_ticket_status("general-0001", "OPEN")
        )
        ticket = loop.run_until_complete(
            self.db.get_ticket("general-0001")
        )
        self.assertEqual(ticket["status"], "OPEN")
        self.assertIsNotNone(ticket["opened_at"])

    def test_count_active_tickets(self):
        loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )
        loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="general-0001",
                internal_id=1,
                category="general",
                user_id=12345,
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="general-0002",
                internal_id=2,
                category="general",
                user_id=12345,
                custom_fields={"ign": "TestIGN", "question": "Test question 2"},
            )
        )
        count = loop.run_until_complete(
            self.db.count_active_tickets_by_user(12345)
        )
        self.assertEqual(count, 2)

    def test_add_and_get_messages(self):
        loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )
        loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="general-0001",
                internal_id=1,
                category="general",
                user_id=12345,
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        loop.run_until_complete(
            self.db.add_message(
                message_id=111,
                ticket_id="general-0001",
                author_id=12345,
                author_name="TestUser",
                content="Hello world",
            )
        )
        messages = loop.run_until_complete(
            self.db.get_messages("general-0001")
        )
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "Hello world")

    def test_add_claim(self):
        loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )
        loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="general-0001",
                internal_id=1,
                category="general",
                user_id=12345,
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        loop.run_until_complete(
            self.db.add_claim("general-0001", 67890, "CLAIM")
        )
        claims = loop.run_until_complete(
            self.db.get_claims("general-0001")
        )
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["action"], "CLAIM")

    def test_add_response(self):
        loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )
        loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="general-0001",
                internal_id=1,
                category="general",
                user_id=12345,
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        loop.run_until_complete(
            self.db.add_response("general-0001", 67890, "Test response")
        )
        responses = loop.run_until_complete(
            self.db.get_responses("general-0001")
        )
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["response"], "Test response")

    def test_permissions(self):
        loop.run_until_complete(
            self.db.add_permission("ticket_respond", "general", 11111)
        )
        loop.run_until_complete(
            self.db.add_permission("ticket_respond", "", 22222)
        )
        perms = loop.run_until_complete(
            self.db.get_permissions("ticket_respond", "general")
        )
        self.assertEqual(len(perms), 1)
        self.assertEqual(perms[0]["role_id"], 11111)

        global_perms = loop.run_until_complete(
            self.db.get_permissions("ticket_respond", "")
        )
        self.assertEqual(len(global_perms), 1)
        self.assertEqual(global_perms[0]["role_id"], 22222)

    def test_remove_permission(self):
        loop.run_until_complete(
            self.db.add_permission("ticket_respond", "general", 11111)
        )
        removed = loop.run_until_complete(
            self.db.remove_permission("ticket_respond", "general", 11111)
        )
        self.assertTrue(removed)
        perms = loop.run_until_complete(
            self.db.get_permissions("ticket_respond", "general")
        )
        self.assertEqual(len(perms), 0)

    def test_audit_log(self):
        loop.run_until_complete(
            self.db.add_audit_log(
                action="TEST_ACTION",
                actor_id=12345,
                actor_name="TestUser",
                ticket_id="general-0001",
                category="general",
                details="Test details",
            )
        )
        logs = loop.run_until_complete(
            self.db.get_audit_logs(action="TEST_ACTION")
        )
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]["action"], "TEST_ACTION")

    def test_ticket_count_by_status(self):
        loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )
        loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="general-0001",
                internal_id=1,
                category="general",
                user_id=12345,
                custom_fields={"ign": "IGN", "question": "Q1"},
            )
        )
        loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="general-0002",
                internal_id=2,
                category="general",
                user_id=12345,
                custom_fields={"ign": "IGN", "question": "Q2"},
            )
        )
        count = loop.run_until_complete(
            self.db.get_ticket_count_by_status("PENDING")
        )
        self.assertEqual(count, 2)

    def test_user_ticket_stats(self):
        loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )
        loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="general-0001",
                internal_id=1,
                category="general",
                user_id=12345,
                custom_fields={"ign": "IGN", "question": "Q1"},
            )
        )
        loop.run_until_complete(
            self.db.create_ticket(
                ticket_id="appeal-0001",
                internal_id=2,
                category="appeal",
                user_id=12345,
                custom_fields={"ign": "IGN", "question": "Q2"},
            )
        )
        stats = loop.run_until_complete(
            self.db.get_user_ticket_stats(12345)
        )
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["by_category"]["general"], 1)
        self.assertEqual(stats["by_category"]["appeal"], 1)


class TestConfigService(unittest.TestCase):
    """Test configuration service."""

    def setUp(self):
        import json
        self.test_config = {
            "guild_id": 123456789,
            "categories": {
                "general": {
                    "display_name": "General",
                    "id_prefix": "general",
                    "pending_channel_id": 111,
                    "open_category_id": 222,
                    "closed_category_id": 333,
                }
            },
            "max_open_tickets": 1,
        }
        with open("test_config.json", "w") as f:
            json.dump(self.test_config, f)

        from services.config_service import ConfigService
        self.config = ConfigService("test_config.json")

    def tearDown(self):
        if os.path.exists("test_config.json"):
            os.remove("test_config.json")

    def test_load_config(self):
        self.config.load()
        self.assertEqual(self.config.get_guild_id(), 123456789)

    def test_get_category(self):
        self.config.load()
        cat = self.config.get_category("general")
        self.assertIsNotNone(cat)
        self.assertEqual(cat["display_name"], "General")

    def test_get_categories(self):
        self.config.load()
        cats = self.config.get_categories()
        self.assertIn("general", cats)

    def test_get_max_open_tickets(self):
        self.config.load()
        self.assertEqual(self.config.get_max_open_tickets(), 1)


class TestPermissionUtils(unittest.TestCase):
    """Test permission utility functions."""

    def test_permission_keys_exist(self):
        from utils.permissions import PERMISSION_KEYS, PERMISSION_DESCRIPTIONS
        self.assertIn("ticket_create", PERMISSION_KEYS)
        self.assertIn("ticket_respond", PERMISSION_KEYS)
        self.assertIn("ticket_claim", PERMISSION_KEYS)
        self.assertIn("ticket_delete", PERMISSION_KEYS)
        self.assertIn("adminstats", PERMISSION_KEYS)
        self.assertIn("permission_add", PERMISSION_KEYS)

        for key in PERMISSION_KEYS:
            self.assertIn(key, PERMISSION_DESCRIPTIONS)


class TestFormattingUtils(unittest.TestCase):
    """Test formatting utility functions."""

    def test_truncate(self):
        from utils.formatting import truncate
        self.assertEqual(truncate("short", 10), "short")
        self.assertEqual(truncate("a" * 20, 10), "aaaaaaa...")

    def test_format_duration(self):
        from utils.formatting import format_duration
        self.assertIn("minute", format_duration(5))
        self.assertIn("hour", format_duration(120))
        self.assertIn("day", format_duration(1440))

    def test_ticket_status_emoji(self):
        from utils.formatting import ticket_status_emoji
        self.assertEqual(ticket_status_emoji("PENDING"), "\u23f3")
        self.assertEqual(ticket_status_emoji("OPEN"), "\ud83d\udce2")
        self.assertEqual(ticket_status_emoji("CLOSED"), "\ud83d\udd12")


class TestTicketService(unittest.TestCase):
    """Test ticket service operations."""

    def setUp(self):
        from database.database import Database
        from services.ticket_service import TicketService

        self.db = Database(":memory:")
        loop.run_until_complete(self.db.connect())
        self.service = TicketService(self.db)

        loop.run_until_complete(
            self.db.get_or_create_user(12345, "TestUser")
        )

    def tearDown(self):
        loop.run_until_complete(self.db.close())

    def test_create_ticket(self):
        ticket = loop.run_until_complete(
            self.service.create_ticket(
                category="general",
                prefix="general",
                user_id=12345,
                username="TestUser",
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        self.assertEqual(ticket["category"], "general")
        self.assertEqual(ticket["status"], "PENDING")

    def test_open_ticket(self):
        loop.run_until_complete(
            self.service.create_ticket(
                category="general",
                prefix="general",
                user_id=12345,
                username="TestUser",
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        updated = loop.run_until_complete(
            self.service.open_ticket("general-0001", 99999)
        )
        self.assertEqual(updated["status"], "OPEN")
        self.assertEqual(updated["discord_channel_id"], 99999)

    def test_claim_ticket(self):
        loop.run_until_complete(
            self.service.create_ticket(
                category="general",
                prefix="general",
                user_id=12345,
                username="TestUser",
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        updated = loop.run_until_complete(
            self.service.claim_ticket("general-0001", 67890)
        )
        self.assertEqual(updated["claimed_by"], 67890)

    def test_respond_to_ticket(self):
        loop.run_until_complete(
            self.service.create_ticket(
                category="general",
                prefix="general",
                user_id=12345,
                username="TestUser",
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        updated = loop.run_until_complete(
            self.service.respond_to_ticket("general-0001", 67890, "Test response")
        )
        self.assertEqual(updated["status"], "RESPONDED")
        self.assertEqual(updated["response"], "Test response")

    def test_close_ticket(self):
        loop.run_until_complete(
            self.service.create_ticket(
                category="general",
                prefix="general",
                user_id=12345,
                username="TestUser",
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        loop.run_until_complete(
            self.service.open_ticket("general-0001", 99999)
        )
        updated = loop.run_until_complete(
            self.service.close_ticket("general-0001")
        )
        self.assertEqual(updated["status"], "CLOSED")

    def test_delete_ticket(self):
        loop.run_until_complete(
            self.service.create_ticket(
                category="general",
                prefix="general",
                user_id=12345,
                username="TestUser",
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        updated = loop.run_until_complete(
            self.service.delete_ticket("general-0001")
        )
        self.assertEqual(updated["status"], "DELETED")

    def test_count_active_tickets(self):
        loop.run_until_complete(
            self.service.create_ticket(
                category="general",
                prefix="general",
                user_id=12345,
                username="TestUser",
                custom_fields={"ign": "TestIGN", "question": "Test question"},
            )
        )
        count = loop.run_until_complete(
            self.service.count_active_tickets(12345)
        )
        self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
