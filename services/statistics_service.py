from __future__ import annotations

import logging
from typing import Any

from database.database import Database

logger = logging.getLogger("ticket_bot.statistics")


class StatisticsService:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def get_user_stats(self, user_id: int) -> dict[str, Any]:
        return await self.db.get_user_ticket_stats(user_id)

    async def get_user_tickets(self, user_id: int) -> list[dict[str, Any]]:
        return await self.db.get_tickets_by_user(user_id)

    async def get_server_stats(self) -> dict[str, Any]:
        total = await self.db.get_total_ticket_count()
        pending = await self.db.get_ticket_count_by_status("PENDING")
        open_t = await self.db.get_ticket_count_by_status("OPEN")
        claimed = await self.db.get_ticket_count_by_status("CLAIMED")
        responded = await self.db.get_ticket_count_by_status("RESPONDED")
        closed = await self.db.get_ticket_count_by_status("CLOSED")
        deleted = await self.db.get_ticket_count_by_status("DELETED")

        today_tickets = await self.db.get_tickets_created_today()
        week_tickets = await self.db.get_tickets_created_this_week()
        month_tickets = await self.db.get_tickets_created_this_month()

        avg_response = await self.db.get_avg_response_time()
        avg_resolution = await self.db.get_avg_resolution_time()

        staff_responds = await self.db.get_respond_counts()
        staff_claims = await self.db.get_staff_action_counts()

        categories = await self.db.get_all_tickets()
        cat_counts: dict[str, int] = {}
        for t in categories:
            cat = t["category"]
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

        return {
            "total": total,
            "pending": pending,
            "open": open_t,
            "claimed": claimed,
            "responded": responded,
            "closed": closed,
            "deleted": deleted,
            "today": len(today_tickets),
            "this_week": len(week_tickets),
            "this_month": len(month_tickets),
            "avg_response_time": avg_response,
            "avg_resolution_time": avg_resolution,
            "staff_responds": staff_responds,
            "staff_claims": staff_claims,
            "category_distribution": cat_counts,
        }

    async def get_category_stats(self) -> dict[str, dict[str, int]]:
        categories = await self.db.get_all_tickets()
        result: dict[str, dict[str, int]] = {}
        for t in categories:
            cat = t["category"]
            status = t["status"]
            if cat not in result:
                result[cat] = {}
            result[cat][status] = result[cat].get(status, 0) + 1
        return result
