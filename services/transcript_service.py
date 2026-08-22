from __future__ import annotations

import html
import logging
import os
from typing import Any, Optional

import discord

from database.database import Database
from utils.formatting import format_timestamp
from utils import timezone
from utils.messages import MessageService

_msg = MessageService()

logger = logging.getLogger("ticket_bot.transcript")


def _build_meta_items(custom_fields: dict[str, Any]) -> str:
    parts = ""
    for key, val in custom_fields.items():
        if val:
            label = key.replace("_", " ").title()
            parts += f"""
                <div class="meta-item">
                    <div class="meta-label">{html.escape(label)}</div>
                    <div class="meta-value">{html.escape(str(val))}</div>
                </div>"""
    return parts


def _build_custom_fields_section(custom_fields: dict[str, Any]) -> str:
    parts = ""
    for key, val in custom_fields.items():
        if val:
            label = key.replace("_", " ").title()
            parts += f"""
        <div class="section">
            <div class="section-header">{html.escape(label)}</div>
            <div class="section-content">
                <div class="question-box">{html.escape(str(val))}</div>
            </div>
        </div>"""
    return parts


class TranscriptService:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def generate_transcript(
        self,
        ticket: dict[str, Any],
        messages: list[dict[str, Any]],
        claims: list[dict[str, Any]],
        responses: list[dict[str, Any]],
    ) -> str:
        ticket_id = ticket["ticket_id"]
        category = ticket["category"]
        user_id = ticket["user_id"]
        custom_fields = ticket.get("custom_fields", {})
        status = ticket["status"]
        created_at = ticket.get("created_at", "N/A")
        closed_at = ticket.get("closed_at") or ticket.get("responded_at") or "N/A"

        claim_rows = ""
        for c in claims:
            action_emoji = "\u2705" if c["action"] == "CLAIM" else "\u274c" if c["action"] == "UNCLAIM" else "\ud83d\udd04"
            claim_rows += f"""
            <tr>
                <td>{action_emoji} {html.escape(c['action'])}</td>
                <td>User ID: {c['staff_id']}</td>
                <td>{format_timestamp(c['timestamp'])}</td>
            </tr>"""

        response_rows = ""
        for r in responses:
            response_rows += f"""
            <tr>
                <td>Staff ID: {r['staff_id']}</td>
                <td>{html.escape(r['response'])}</td>
                <td>{format_timestamp(r['timestamp'])}</td>
            </tr>"""

        message_rows = ""
        for m in messages:
            attachments_html = ""
            if m.get("attachments") and m["attachments"] != "[]":
                try:
                    import json
                    atts = json.loads(m["attachments"])
                    for att in atts:
                        attachments_html += f'<div class="attachment"><a href="{html.escape(att.get("url", ""))}" target="_blank">{html.escape(att.get("filename", "file"))}</a></div>'
                except (json.JSONDecodeError, TypeError):
                    pass

            message_rows += f"""
            <div class="message">
                <div class="message-header">
                    <span class="author">User ID: {m['author_id']}</span>
                    <span class="timestamp">{format_timestamp(m['timestamp'])}</span>
                </div>
                <div class="message-content">{html.escape(m.get('content', ''))}</div>
                {attachments_html}
            </div>"""

        transcript_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IRBW Ticket Transcript - {html.escape(ticket_id)}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #36393f;
            color: #dcddde;
            line-height: 1.6;
            padding: 20px;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #5865f2, #7289da);
            border-radius: 10px 10px 0 0;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 28px;
            color: white;
            margin-bottom: 5px;
        }}
        .header .subtitle {{
            color: rgba(255,255,255,0.8);
            font-size: 14px;
        }}
        .branding {{
            background: #202225;
            padding: 15px 30px;
            text-align: center;
            font-size: 12px;
            color: #72767d;
            border-bottom: 1px solid #2f3136;
        }}
        .meta-section {{
            background: #2f3136;
            padding: 20px 30px;
            border-bottom: 1px solid #202225;
        }}
        .meta-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .meta-item {{
            background: #36393f;
            padding: 12px 15px;
            border-radius: 6px;
            border-left: 3px solid #5865f2;
        }}
        .meta-label {{
            font-size: 11px;
            color: #72767d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .meta-value {{
            font-size: 15px;
            color: #dcddde;
            font-weight: 500;
            margin-top: 3px;
        }}
        .section {{
            background: #2f3136;
            margin: 10px 0;
            border-radius: 6px;
            overflow: hidden;
        }}
        .section-header {{
            background: #202225;
            padding: 12px 20px;
            font-weight: 600;
            font-size: 14px;
            color: #5865f2;
            border-bottom: 1px solid #36393f;
        }}
        .section-content {{
            padding: 15px 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            padding: 10px 15px;
            text-align: left;
            border-bottom: 1px solid #36393f;
        }}
        th {{
            background: #202225;
            color: #72767d;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .message {{
            background: #36393f;
            padding: 12px 15px;
            margin: 8px 0;
            border-radius: 6px;
            border-left: 3px solid #5865f2;
        }}
        .message-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 6px;
        }}
        .author {{
            font-weight: 600;
            color: #5865f2;
        }}
        .timestamp {{
            color: #72767d;
            font-size: 12px;
        }}
        .message-content {{
            color: #dcddde;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .attachment {{
            margin-top: 6px;
            padding: 6px 10px;
            background: #202225;
            border-radius: 4px;
            display: inline-block;
        }}
        .attachment a {{
            color: #00aff4;
            text-decoration: none;
        }}
        .attachment a:hover {{
            text-decoration: underline;
        }}
        .question-box {{
            background: #36393f;
            padding: 15px 20px;
            border-radius: 6px;
            border-left: 3px solid #fee75c;
            margin: 10px 0;
        }}
        .footer {{
            background: #202225;
            padding: 20px;
            text-align: center;
            border-radius: 0 0 10px 10px;
            color: #72767d;
            font-size: 12px;
        }}
        .status-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .status-pending {{ background: #fee75c33; color: #fee75c; }}
        .status-open {{ background: #57f28733; color: #57f287; }}
        .status-claimed {{ background: #5865f233; color: #5865f2; }}
        .status-responded {{ background: #57f28733; color: #57f287; }}
        .status-closed {{ background: #747f8d33; color: #747f8d; }}
        .status-deleted {{ background: #ed424533; color: #ed4245; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>IRBW Ticket Transcript</h1>
            <div class="subtitle">Support Ticket Documentation</div>
        </div>
        <div class="branding">IRBW Ticket System &bull; Auto-generated Transcript</div>

        <div class="meta-section">
            <div class="meta-grid">
                <div class="meta-item">
                    <div class="meta-label">Ticket ID</div>
                    <div class="meta-value">{html.escape(ticket_id)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Category</div>
                    <div class="meta-value">{html.escape(category.title())}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">User</div>
                    <div class="meta-value">User ID: {user_id}</div>
                </div>
                {_build_meta_items(custom_fields)}
                <div class="meta-item">
                    <div class="meta-label">Created</div>
                    <div class="meta-value">{format_timestamp(created_at)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Closed</div>
                    <div class="meta-value">{format_timestamp(closed_at)}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">Status</div>
                    <div class="meta-value"><span class="status-badge status-{status.lower()}">{status}</span></div>
                </div>
            </div>
        </div>

        {_build_custom_fields_section(custom_fields)}

        <div class="section">
            <div class="section-header">Claim History</div>
            <div class="section-content">
                <table>
                    <tr><th>Action</th><th>Staff</th><th>Time</th></tr>
                    {claim_rows if claim_rows else '<tr><td colspan="3" style="color:#72767d;">No claims recorded</td></tr>'}
                </table>
            </div>
        </div>

        <div class="section">
            <div class="section-header">Staff Responses</div>
            <div class="section-content">
                <table>
                    <tr><th>Staff</th><th>Response</th><th>Time</th></tr>
                    {response_rows if response_rows else '<tr><td colspan="3" style="color:#72767d;">No responses recorded</td></tr>'}
                </table>
            </div>
        </div>

        <div class="section">
            <div class="section-header">Messages ({len(messages)})</div>
            <div class="section-content">
                {message_rows if message_rows else '<div style="color:#72767d;">No messages recorded</div>'}
            </div>
        </div>

        <div class="footer">
            IRBW Ticket System &bull; Transcript generated {timezone.now().strftime('%Y-%m-%d %H:%M %Z')}
        </div>
    </div>
</body>
</html>"""
        return transcript_html

    async def save_transcript(self, ticket_id: str, html_content: str) -> str:
        os.makedirs("transcripts", exist_ok=True)
        safe_id = ticket_id.replace("/", "-").replace("\\", "-")
        filepath = f"transcripts/{safe_id}.html"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info("Transcript saved to %s", filepath)
        return filepath

    async def upload_transcript(
        self, channel: discord.abc.Messageable, filepath: str, ticket_id: str
    ) -> Optional[discord.Message]:
        try:
            file = discord.File(filepath, filename=f"{ticket_id}_transcript.html")
            embed = discord.Embed(
                title=_msg.get("transcript.upload_title"),
                description=_msg.get("transcript.upload_description", ticket_id=ticket_id),
                color=5814783,
            )
            return await channel.send(embed=embed, file=file)
        except Exception as e:
            logger.error("Failed to upload transcript for %s: %s", ticket_id, e)
            return None
