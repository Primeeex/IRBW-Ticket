from __future__ import annotations

import datetime
from typing import Optional, Any

import aiosqlite

from utils import timezone


SCHEMA_VERSION = 5

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    ticket_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id TEXT PRIMARY KEY,
    internal_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    custom_fields TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'PENDING',
    discord_channel_id INTEGER,
    pending_message_id INTEGER,
    created_at TEXT NOT NULL,
    opened_at TEXT,
    claimed_by INTEGER,
    responded_at TEXT,
    closed_at TEXT,
    deleted_at TEXT,
    response TEXT,
    response_staff_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS ticket_bans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    offense_number INTEGER NOT NULL DEFAULT 1,
    banned_at TEXT NOT NULL,
    expires_at TEXT,
    reason TEXT NOT NULL DEFAULT '',
    banned_by INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ticket_messages (
    message_id INTEGER PRIMARY KEY,
    ticket_id TEXT NOT NULL,
    author_id INTEGER NOT NULL,
    author_name TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL,
    attachments TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL,
    staff_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
);

CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT NOT NULL,
    staff_id INTEGER NOT NULL,
    response TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES tickets(ticket_id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    actor_id INTEGER NOT NULL,
    actor_name TEXT NOT NULL DEFAULT '',
    target_id INTEGER,
    target_name TEXT NOT NULL DEFAULT '',
    ticket_id TEXT,
    category TEXT,
    channel_id INTEGER,
    details TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS counters (
    category TEXT PRIMARY KEY,
    next_number INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS permissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    permission_key TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    role_id INTEGER NOT NULL,
    UNIQUE(permission_key, category, role_id)
);

CREATE INDEX IF NOT EXISTS idx_tickets_user_id ON tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_category ON tickets(category);
CREATE INDEX IF NOT EXISTS idx_tickets_channel ON tickets(discord_channel_id);
CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON ticket_messages(ticket_id);
CREATE INDEX IF NOT EXISTS idx_claims_ticket ON claims(ticket_id);
CREATE INDEX IF NOT EXISTS idx_responses_ticket ON responses(ticket_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_ticket ON audit_logs(ticket_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_permissions_key ON permissions(permission_key);
CREATE INDEX IF NOT EXISTS idx_permissions_role ON permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_ticket_bans_user ON ticket_bans(user_id);
CREATE INDEX IF NOT EXISTS idx_ticket_bans_active ON ticket_bans(active);

CREATE TABLE IF NOT EXISTS custom_presets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    permission_keys TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_custom_presets_name ON custom_presets(name);
"""


class Database:
    def __init__(self, db_path: str = "tickets.db") -> None:
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._init_schema()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._db

    async def _init_schema(self) -> None:
        await self.db.executescript(SCHEMA_SQL)
        cursor = await self.db.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
        row = await cursor.fetchone()
        if row is None:
            await self.db.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        elif row["version"] < SCHEMA_VERSION:
            if row["version"] < 2:
                try:
                    await self.db.execute("ALTER TABLE tickets ADD COLUMN pending_message_id INTEGER")
                except Exception:
                    pass
            if row["version"] < 3:
                try:
                    await self.db.execute("""CREATE TABLE IF NOT EXISTS ticket_bans (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        offense_number INTEGER NOT NULL DEFAULT 1,
                        banned_at TEXT NOT NULL,
                        expires_at TEXT,
                        reason TEXT NOT NULL DEFAULT '',
                        banned_by INTEGER NOT NULL,
                        active INTEGER NOT NULL DEFAULT 1
                    )""")
                    await self.db.execute("CREATE INDEX IF NOT EXISTS idx_ticket_bans_user ON ticket_bans(user_id)")
                    await self.db.execute("CREATE INDEX IF NOT EXISTS idx_ticket_bans_active ON ticket_bans(active)")
                except Exception:
                    pass
            if row["version"] < 4:
                try:
                    await self.db.execute("ALTER TABLE tickets ADD COLUMN custom_fields TEXT NOT NULL DEFAULT '{}'")
                    cursor = await self.db.execute("SELECT ticket_id, ign, question FROM tickets")
                    rows = await cursor.fetchall()
                    import json as _json
                    for r in rows:
                        cf = _json.dumps({"ign": r["ign"], "question": r["question"]})
                        await self.db.execute("UPDATE tickets SET custom_fields = ? WHERE ticket_id = ?", (cf, r["ticket_id"]))
                    await self.db.execute("ALTER TABLE tickets DROP COLUMN ign")
                    await self.db.execute("ALTER TABLE tickets DROP COLUMN question")
                except Exception:
                    pass
            if row["version"] < 5:
                try:
                    await self.db.executescript("""
                        CREATE TABLE IF NOT EXISTS custom_presets (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL UNIQUE,
                            description TEXT NOT NULL DEFAULT '',
                            permission_keys TEXT NOT NULL DEFAULT '[]'
                        );
                        CREATE INDEX IF NOT EXISTS idx_custom_presets_name ON custom_presets(name);
                    """)
                except Exception:
                    pass
            await self.db.execute(
                "UPDATE schema_version SET version = ? WHERE version = ?",
                (SCHEMA_VERSION, row["version"]),
            )
        await self.db.commit()

    # ── User Operations ──────────────────────────────────────────

    async def get_or_create_user(self, user_id: int, username: str) -> dict[str, Any]:
        now = timezone.now().isoformat()
        cursor = await self.db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        if row:
            await self.db.execute(
                "UPDATE users SET last_seen = ?, username = ? WHERE user_id = ?",
                (now, username, user_id),
            )
            await self.db.commit()
            cursor2 = await self.db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            updated_row = await cursor2.fetchone()
            return dict(updated_row) if updated_row else dict(row)
        await self.db.execute(
            "INSERT INTO users (user_id, username, first_seen, last_seen, ticket_count) VALUES (?, ?, ?, ?, 0)",
            (user_id, username, now, now),
        )
        await self.db.commit()
        return {"user_id": user_id, "username": username, "first_seen": now, "last_seen": now, "ticket_count": 0}

    async def increment_user_ticket_count(self, user_id: int) -> None:
        await self.db.execute(
            "UPDATE users SET ticket_count = ticket_count + 1 WHERE user_id = ?",
            (user_id,),
        )
        await self.db.commit()

    async def get_user(self, user_id: int) -> Optional[dict[str, Any]]:
        cursor = await self.db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    # ── Counter Operations ───────────────────────────────────────

    async def get_next_ticket_number(self, category: str, prefix: str) -> str:
        cursor = await self.db.execute("SELECT next_number FROM counters WHERE category = ?", (category,))
        row = await cursor.fetchone()
        if row:
            num = row["next_number"]
            await self.db.execute(
                "UPDATE counters SET next_number = next_number + 1 WHERE category = ?",
                (category,),
            )
        else:
            num = 1
            await self.db.execute(
                "INSERT INTO counters (category, next_number) VALUES (?, ?)",
                (category, 2),
            )
        await self.db.commit()
        return f"{prefix}-{num:04d}"

    # ── Ticket Operations ────────────────────────────────────────

    async def create_ticket(
        self,
        ticket_id: str,
        internal_id: int,
        category: str,
        user_id: int,
        custom_fields: dict[str, Any],
    ) -> dict[str, Any]:
        import json
        now = timezone.now().isoformat()
        cf_json = json.dumps(custom_fields)
        await self.db.execute(
            """INSERT INTO tickets
               (ticket_id, internal_id, category, user_id, custom_fields, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'PENDING', ?)""",
            (ticket_id, internal_id, category, user_id, cf_json, now),
        )
        await self.db.commit()
        return {
            "ticket_id": ticket_id,
            "internal_id": internal_id,
            "category": category,
            "user_id": user_id,
            "custom_fields": custom_fields,
            "status": "PENDING",
            "created_at": now,
        }

    @staticmethod
    def _parse_ticket(row: dict[str, Any]) -> dict[str, Any]:
        d = dict(row)
        import json
        cf = d.get("custom_fields", "{}")
        if isinstance(cf, str):
            try:
                d["custom_fields"] = json.loads(cf)
            except (json.JSONDecodeError, TypeError):
                d["custom_fields"] = {}
        return d

    async def get_ticket(self, ticket_id: str) -> Optional[dict[str, Any]]:
        cursor = await self.db.execute("SELECT * FROM tickets WHERE ticket_id = ?", (ticket_id,))
        row = await cursor.fetchone()
        return self._parse_ticket(row) if row else None

    async def get_ticket_by_channel(self, channel_id: int) -> Optional[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM tickets WHERE discord_channel_id = ?", (channel_id,)
        )
        row = await cursor.fetchone()
        return self._parse_ticket(row) if row else None

    async def get_tickets_by_user(self, user_id: int, status: Optional[str] = None) -> list[dict[str, Any]]:
        if status:
            cursor = await self.db.execute(
                "SELECT * FROM tickets WHERE user_id = ? AND status = ? ORDER BY created_at DESC",
                (user_id, status),
            )
        else:
            cursor = await self.db.execute(
                "SELECT * FROM tickets WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            )
        rows = await cursor.fetchall()
        return [self._parse_ticket(r) for r in rows]

    async def get_active_tickets_by_user(self, user_id: int) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM tickets WHERE user_id = ? AND status IN ('PENDING', 'OPEN', 'CLAIMED') ORDER BY created_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [self._parse_ticket(r) for r in rows]

    async def count_active_tickets_by_user(self, user_id: int) -> int:
        cursor = await self.db.execute(
            "SELECT COUNT(*) as cnt FROM tickets WHERE user_id = ? AND status IN ('PENDING', 'OPEN', 'CLAIMED')",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def count_pending_tickets_by_user(self, user_id: int, category: str) -> int:
        cursor = await self.db.execute(
            "SELECT COUNT(*) as cnt FROM tickets WHERE user_id = ? AND category = ? AND status = 'PENDING'",
            (user_id, category),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def update_ticket_status(self, ticket_id: str, status: str) -> None:
        now = timezone.now().isoformat()
        extra = ""
        params: list[Any] = [status]
        if status == "OPEN":
            extra = ", opened_at = ?"
            params.append(now)
        elif status == "RESPONDED":
            extra = ", responded_at = ?"
            params.append(now)
        elif status in ("CLOSED", "DELETED"):
            extra = ", closed_at = ?"
            params.append(now)
        params.append(ticket_id)
        await self.db.execute(
            f"UPDATE tickets SET status = ?{extra} WHERE ticket_id = ?",
            params,
        )
        await self.db.commit()

    async def update_ticket_channel(self, ticket_id: str, channel_id: int) -> None:
        await self.db.execute(
            "UPDATE tickets SET discord_channel_id = ? WHERE ticket_id = ?",
            (channel_id, ticket_id),
        )
        await self.db.commit()

    async def update_pending_message_id(self, ticket_id: str, message_id: int) -> None:
        await self.db.execute(
            "UPDATE tickets SET pending_message_id = ? WHERE ticket_id = ?",
            (message_id, ticket_id),
        )
        await self.db.commit()

    async def update_ticket_claim(self, ticket_id: str, staff_id: Optional[int]) -> None:
        await self.db.execute(
            "UPDATE tickets SET claimed_by = ? WHERE ticket_id = ?",
            (staff_id, ticket_id),
        )
        await self.db.commit()

    async def update_ticket_category(self, ticket_id: str, new_category: str) -> None:
        await self.db.execute(
            "UPDATE tickets SET category = ? WHERE ticket_id = ?",
            (new_category, ticket_id),
        )
        await self.db.commit()

    async def update_ticket_response(self, ticket_id: str, response: str, staff_id: int) -> None:
        now = timezone.now().isoformat()
        await self.db.execute(
            "UPDATE tickets SET response = ?, response_staff_id = ?, responded_at = ? WHERE ticket_id = ?",
            (response, staff_id, now, ticket_id),
        )
        await self.db.commit()

    async def reopen_ticket(self, ticket_id: str) -> None:
        now = timezone.now().isoformat()
        await self.db.execute(
            "UPDATE tickets SET status = 'OPEN', opened_at = ?, closed_at = NULL, claimed_by = NULL WHERE ticket_id = ?",
            (now, ticket_id),
        )
        await self.db.commit()

    async def update_ticket_deleted(self, ticket_id: str) -> None:
        now = timezone.now().isoformat()
        await self.db.execute(
            "UPDATE tickets SET status = 'DELETED', deleted_at = ? WHERE ticket_id = ?",
            (now, ticket_id),
        )
        await self.db.commit()

    async def count_tickets_by_category_status(self, category: str, status: str) -> int:
        cursor = await self.db.execute(
            "SELECT COUNT(*) as cnt FROM tickets WHERE category = ? AND status = ?",
            (category, status),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_all_tickets(self, status: Optional[str] = None, category: Optional[str] = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM tickets WHERE 1=1"
        params: list[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY created_at DESC"
        cursor = await self.db.execute(query, params)
        rows = await cursor.fetchall()
        return [self._parse_ticket(r) for r in rows]

    async def get_tickets_created_since(self, since: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM tickets WHERE created_at >= ? ORDER BY created_at DESC",
            (since,),
        )
        rows = await cursor.fetchall()
        return [self._parse_ticket(r) for r in rows]

    # ── Message Operations ───────────────────────────────────────

    async def add_message(
        self,
        message_id: int,
        ticket_id: str,
        author_id: int,
        author_name: str,
        content: str,
        attachments: str = "[]",
    ) -> None:
        now = timezone.now().isoformat()
        await self.db.execute(
            """INSERT OR REPLACE INTO ticket_messages
               (message_id, ticket_id, author_id, author_name, content, timestamp, attachments)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (message_id, ticket_id, author_id, author_name, content, now, attachments),
        )
        await self.db.commit()

    async def get_messages(self, ticket_id: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id = ? ORDER BY timestamp ASC",
            (ticket_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Claim Operations ─────────────────────────────────────────

    async def add_claim(self, ticket_id: str, staff_id: int, action: str) -> None:
        now = timezone.now().isoformat()
        await self.db.execute(
            "INSERT INTO claims (ticket_id, staff_id, action, timestamp) VALUES (?, ?, ?, ?)",
            (ticket_id, staff_id, action, now),
        )
        await self.db.commit()

    async def get_claims(self, ticket_id: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM claims WHERE ticket_id = ? ORDER BY timestamp ASC",
            (ticket_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Response Operations ──────────────────────────────────────

    async def add_response(self, ticket_id: str, staff_id: int, response: str) -> None:
        now = timezone.now().isoformat()
        await self.db.execute(
            "INSERT INTO responses (ticket_id, staff_id, response, timestamp) VALUES (?, ?, ?, ?)",
            (ticket_id, staff_id, response, now),
        )
        await self.db.commit()

    async def get_responses(self, ticket_id: str) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM responses WHERE ticket_id = ? ORDER BY timestamp ASC",
            (ticket_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Audit Operations ─────────────────────────────────────────

    async def add_audit_log(
        self,
        action: str,
        actor_id: int,
        actor_name: str,
        target_id: Optional[int] = None,
        target_name: str = "",
        ticket_id: Optional[str] = None,
        category: Optional[str] = None,
        channel_id: Optional[int] = None,
        details: str = "",
    ) -> None:
        now = timezone.now().isoformat()
        await self.db.execute(
            """INSERT INTO audit_logs
               (action, actor_id, actor_name, target_id, target_name, ticket_id, category, channel_id, details, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (action, actor_id, actor_name, target_id, target_name, ticket_id, category, channel_id, details, now),
        )
        await self.db.commit()

    async def get_audit_logs(
        self,
        ticket_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params: list[Any] = []
        if ticket_id:
            query += " AND ticket_id = ?"
            params.append(ticket_id)
        if action:
            query += " AND action = ?"
            params.append(action)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cursor = await self.db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Permission Operations ────────────────────────────────────

    async def add_permission(self, permission_key: str, category: str, role_id: int) -> None:
        await self.db.execute(
            "INSERT OR IGNORE INTO permissions (permission_key, category, role_id) VALUES (?, ?, ?)",
            (permission_key, category, role_id),
        )
        await self.db.commit()

    async def remove_permission(self, permission_key: str, category: str, role_id: int) -> bool:
        cursor = await self.db.execute(
            "DELETE FROM permissions WHERE permission_key = ? AND category = ? AND role_id = ?",
            (permission_key, category, role_id),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_permissions(self, permission_key: str, category: str = "") -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM permissions WHERE permission_key = ? AND category = ?",
            (permission_key, category),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_all_permissions(self) -> list[dict[str, Any]]:
        cursor = await self.db.execute("SELECT * FROM permissions ORDER BY permission_key, category")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_permission_role_ids(self, permission_key: str, category: str = "") -> list[int]:
        cursor = await self.db.execute(
            "SELECT role_id FROM permissions WHERE permission_key = ? AND category = ?",
            (permission_key, category),
        )
        rows = await cursor.fetchall()
        return [r["role_id"] for r in rows]

    # ── Statistics Operations ────────────────────────────────────

    async def get_total_ticket_count(self) -> int:
        cursor = await self.db.execute("SELECT COUNT(*) as cnt FROM tickets")
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_ticket_count_by_status(self, status: str) -> int:
        cursor = await self.db.execute(
            "SELECT COUNT(*) as cnt FROM tickets WHERE status = ?", (status,)
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_ticket_count_by_category(self, category: str) -> int:
        cursor = await self.db.execute(
            "SELECT COUNT(*) as cnt FROM tickets WHERE category = ?", (category,)
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_ticket_count_by_category_status(self, category: str, status: str) -> int:
        cursor = await self.db.execute(
            "SELECT COUNT(*) as cnt FROM tickets WHERE category = ? AND status = ?",
            (category, status),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def get_tickets_created_today(self) -> list[dict[str, Any]]:
        today = timezone.now().date().isoformat()
        cursor = await self.db.execute(
            "SELECT * FROM tickets WHERE created_at >= ?", (today,)
        )
        rows = await cursor.fetchall()
        return [self._parse_ticket(r) for r in rows]

    async def get_tickets_created_this_week(self) -> list[dict[str, Any]]:
        week_ago = (timezone.now() - datetime.timedelta(days=7)).isoformat()
        cursor = await self.db.execute(
            "SELECT * FROM tickets WHERE created_at >= ?", (week_ago,)
        )
        rows = await cursor.fetchall()
        return [self._parse_ticket(r) for r in rows]

    async def get_tickets_created_this_month(self) -> list[dict[str, Any]]:
        month_ago = (timezone.now() - datetime.timedelta(days=30)).isoformat()
        cursor = await self.db.execute(
            "SELECT * FROM tickets WHERE created_at >= ?", (month_ago,)
        )
        rows = await cursor.fetchall()
        return [self._parse_ticket(r) for r in rows]

    async def get_user_ticket_stats(self, user_id: int) -> dict[str, Any]:
        tickets = await self.get_tickets_by_user(user_id)
        stats: dict[str, Any] = {
            "total": len(tickets),
            "pending": 0,
            "open": 0,
            "claimed": 0,
            "responded": 0,
            "closed": 0,
            "deleted": 0,
            "by_category": {},
            "responses_received": 0,
            "recent": [],
        }
        for t in tickets:
            status = t["status"].lower()
            if status in stats:
                stats[status] += 1
            cat = t["category"]
            if cat not in stats["by_category"]:
                stats["by_category"][cat] = 0
            stats["by_category"][cat] += 1
        for t in tickets[:10]:
            stats["recent"].append({
                "ticket_id": t["ticket_id"],
                "category": t["category"],
                "status": t["status"],
                "created_at": t["created_at"],
            })
        for t in tickets:
            if t.get("response"):
                stats["responses_received"] += 1
        return stats

    async def get_staff_action_counts(self) -> dict[str, dict[str, int]]:
        cursor = await self.db.execute(
            "SELECT staff_id, action, COUNT(*) as cnt FROM claims GROUP BY staff_id, action"
        )
        rows = await cursor.fetchall()
        result: dict[str, dict[str, int]] = {}
        for r in rows:
            sid = str(r["staff_id"])
            if sid not in result:
                result[sid] = {}
            result[sid][r["action"]] = r["cnt"]
        return result

    async def get_respond_counts(self) -> dict[str, int]:
        cursor = await self.db.execute(
            "SELECT staff_id, COUNT(*) as cnt FROM responses GROUP BY staff_id"
        )
        rows = await cursor.fetchall()
        return {str(r["staff_id"]): r["cnt"] for r in rows}

    async def get_avg_response_time(self) -> Optional[float]:
        cursor = await self.db.execute(
            """SELECT AVG(
                (julianday(responded_at) - julianday(created_at)) * 24 * 60
            ) as avg_min
            FROM tickets WHERE responded_at IS NOT NULL AND created_at IS NOT NULL"""
        )
        row = await cursor.fetchone()
        return row["avg_min"] if row and row["avg_min"] else None

    async def get_avg_resolution_time(self) -> Optional[float]:
        cursor = await self.db.execute(
            """SELECT AVG(
                (julianday(closed_at) - julianday(created_at)) * 24 * 60
            ) as avg_min
            FROM tickets WHERE closed_at IS NOT NULL AND created_at IS NOT NULL"""
        )
        row = await cursor.fetchone()
        return row["avg_min"] if row and row["avg_min"] else None

    # ── Ban Operations ───────────────────────────────────────────

    async def add_ticket_ban(
        self, user_id: int, offense_number: int, banned_at: str,
        expires_at: Optional[str], reason: str, banned_by: int,
    ) -> None:
        await self.db.execute(
            """INSERT INTO ticket_bans
               (user_id, offense_number, banned_at, expires_at, reason, banned_by, active)
               VALUES (?, ?, ?, ?, ?, ?, 1)""",
            (user_id, offense_number, banned_at, expires_at, reason, banned_by),
        )
        await self.db.commit()

    async def get_active_ban(self, user_id: int) -> Optional[dict[str, Any]]:
        now = timezone.now().isoformat()
        cursor = await self.db.execute(
            """SELECT * FROM ticket_bans
               WHERE user_id = ? AND active = 1
               AND (expires_at IS NULL OR expires_at > ?)
               ORDER BY banned_at DESC LIMIT 1""",
            (user_id, now),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_user_offense_count(self, user_id: int) -> int:
        cursor = await self.db.execute(
            "SELECT COALESCE(MAX(offense_number), 0) as max_off FROM ticket_bans WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row["max_off"] if row else 0

    async def deactivate_ban(self, user_id: int) -> bool:
        now = timezone.now().isoformat()
        cursor = await self.db.execute(
            """UPDATE ticket_bans SET active = 0
               WHERE user_id = ? AND active = 1""",
            (user_id,),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_all_active_bans(self) -> list[dict[str, Any]]:
        now = timezone.now().isoformat()
        cursor = await self.db.execute(
            """SELECT * FROM ticket_bans
               WHERE active = 1 AND (expires_at IS NULL OR expires_at > ?)
               ORDER BY banned_at DESC""",
            (now,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_ban_history(self, user_id: int) -> list[dict[str, Any]]:
        cursor = await self.db.execute(
            "SELECT * FROM ticket_bans WHERE user_id = ? ORDER BY banned_at DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    # ── Custom Preset Operations ────────────────────────────────

    async def add_custom_preset(self, name: str, description: str, permission_keys: list[str]) -> None:
        import json
        await self.db.execute(
            "INSERT OR REPLACE INTO custom_presets (name, description, permission_keys) VALUES (?, ?, ?)",
            (name, description, json.dumps(permission_keys)),
        )
        await self.db.commit()

    async def remove_custom_preset(self, name: str) -> bool:
        cursor = await self.db.execute(
            "DELETE FROM custom_presets WHERE name = ?", (name,),
        )
        await self.db.commit()
        return cursor.rowcount > 0

    async def get_custom_preset(self, name: str) -> Optional[dict[str, Any]]:
        import json
        cursor = await self.db.execute(
            "SELECT * FROM custom_presets WHERE name = ?", (name,),
        )
        row = await cursor.fetchone()
        if row:
            d = dict(row)
            try:
                d["permission_keys"] = json.loads(d["permission_keys"])
            except (json.JSONDecodeError, TypeError):
                d["permission_keys"] = []
            return d
        return None

    async def get_all_custom_presets(self) -> list[dict[str, Any]]:
        import json
        cursor = await self.db.execute(
            "SELECT * FROM custom_presets ORDER BY name",
        )
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["permission_keys"] = json.loads(d["permission_keys"])
            except (json.JSONDecodeError, TypeError):
                d["permission_keys"] = []
            result.append(d)
        return result
