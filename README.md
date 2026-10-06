# IRBW Discord Ticket Bot

A complete, production-ready Discord ticket/support system for the IRBW server using discord.py 2.x.

## Features

- Multi-category ticket system with independent configuration
- Pending ticket workflow with Respond and Create Channel flows
- Professional HTML transcript generation
- Complete audit trail
- Dynamic permission system with per-category control
- Persistent views that survive bot restarts
- User and admin statistics
- Hot-reload configuration
- DM notifications for ticket responses

## Requirements

- Python 3.12+
- discord.py 2.3.0+
- aiosqlite
- python-dotenv

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd IRBWTicketBot
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file:
```bash
cp .env.example .env
```

5. Edit `.env` and add your bot token:
```
DISCORD_TOKEN=your_bot_token_here
```

6. Create `config.json`:
```bash
cp config.example.json config.json
```

7. Edit `config.json` with your server configuration.

8. Run the bot:
```bash
python bot.py
```

## Configuration

### Environment Variables (.env)

| Variable | Description | Required |
|----------|-------------|----------|
| `DISCORD_TOKEN` | Your Discord bot token | Yes |

### Configuration File (config.json)

#### Guild Settings

```json
{
  "guild_id": 123456789012345678
}
```

Set this to your Discord server ID. The bot will only operate in this guild.

#### Ticket Panel

```json
{
  "ticket_panel": {
    "channel_id": 123456789,
    "type": "buttons",
    "embed": {
      "title": "IRBW Support",
      "description": "Need help? Select a category below to open a support ticket.",
      "color": 5814783
    }
  }
}
```

- `type`: "buttons" or "dropdown"
- `channel_id`: Channel where the panel will be deployed

#### Categories

```json
{
  "categories": {
    "general": {
      "display_name": "General",
      "id_prefix": "general",
      "pending_channel_id": 123,
      "open_category_id": 456,
      "closed_category_id": 789,
      "staff_roles": [111111],
      "respond_roles": [111111],
      "claim_roles": [111111],
      "delete_roles": [222222],
      "add_roles": [111111],
      "view_open_roles": [111111],
      "view_closed_roles": [222222]
    }
  }
}
```

Each category has independent:
- Pending channel (where pending tickets appear)
- Open category (where ticket channels are created)
- Closed category (where closed tickets are moved)
- Staff role configurations

#### Limits

```json
{
  "max_open_tickets": 1,
  "max_pending_tickets": 1
}
```

#### Transcripts

```json
{
  "transcripts": {
    "enabled": true,
    "channel_id": 123456789
  }
}
```

#### Audit Log

```json
{
  "audit_log": {
    "enabled": true,
    "channel_id": 123456789
  }
}
```

## Discord Bot Permissions

The bot requires the following permissions:

- View Channels
- Send Messages
- Embed Links
- Read Message History
- Attach Files
- Use Application Commands
- Manage Channels (for creating/closing ticket channels)
- Manage Permissions (for setting channel overwrites)

### Required Intents

- `message_content`
- `members`
- `guilds`

## Commands

### User Commands

| Command | Description |
|---------|-------------|
| `/stats` | View your personal ticket statistics |
| `/ticket stats` | View your detailed ticket history |
| `/commands` | View all available bot commands |

### Staff Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `/response` | Send a response to the current ticket | `ticket_respond` |
| `/add` | Add a user or role to a ticket | `ticket_add_user` / `ticket_add_role` |
| `/claim` | Claim the current ticket | `ticket_claim` |
| `/unclaim` | Unclaim the current ticket | `ticket_unclaim` |
| `/delete` | Delete the current ticket | `ticket_delete` |
| `/transcript` | Generate a transcript | `ticket_transcript` |

### Admin Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `/reload` | Hot-reload bot configuration | Administrator |
| `/adminhelp` | View admin documentation | Administrator |
| `/adminstats` | View admin statistics | `adminstats` |
| `/permission list` | List configured permissions | Administrator |
| `/permission add` | Add a permission to a role | Administrator |
| `/permission remove` | Remove a permission | Administrator |
| `/deploy` | Deploy the ticket panel | Administrator |

## Ticket Workflow

### Creating a Ticket

1. User selects a category from the panel
2. User fills out the ticket creation modal (IGN + Problem)
3. A pending ticket message appears in the category's pending channel
4. Staff can either:
   - **Respond**: Send a DM response and close the ticket
   - **Create Channel**: Create a private ticket channel

### Respond Flow

1. Staff clicks "Respond" on the pending ticket
2. Staff fills out the response modal
3. Response is sent to the user via DM
4. Ticket is marked as RESPONDED/CLOSED
5. Transcript is generated
6. Action is logged in the audit trail

### Create Channel Flow

1. Staff clicks "Create Channel" on the pending ticket
2. A private ticket channel is created
3. The ticket creator and authorized staff can access the channel
4. Staff can claim, respond, and close the ticket
5. When closed, the channel is moved to the closed category

## Permission System

### Permission Keys

- `ticket_create` - Create tickets
- `ticket_view_open` - View open tickets
- `ticket_view_closed` - View closed tickets
- `ticket_respond` - Respond to tickets
- `ticket_claim` - Claim tickets
- `ticket_unclaim` - Unclaim tickets
- `ticket_override_claim` - Override existing claims
- `ticket_add_user` - Add users to tickets
- `ticket_add_role` - Add roles to tickets
- `ticket_delete` - Delete tickets
- `ticket_close` - Close tickets
- `ticket_reopen` - Reopen tickets
- `ticket_transcript` - Generate transcripts
- `adminstats` - View admin statistics
- `adminhelp` - View admin help
- `config` - View/modify configuration
- `reload` - Reload configuration
- `permission_list` - List permissions
- `permission_add` - Add permissions
- `permission_remove` - Remove permissions

### Category-Specific Permissions

Permissions can be scoped to specific categories:

```
/permission add key:ticket_respond category:general role:@Moderator
```

This grants the Moderator role permission to respond only to General tickets.

### Global Permissions

Without a category scope, permissions apply to all categories:

```
/permission add key:ticket_claim role:@Staff
```

## Transcript System

When a ticket is closed or responded to, an HTML transcript is generated containing:

- Ticket metadata (ID, category, user, IGN, status)
- Original question
- Claim history
- Staff responses
- All messages with timestamps
- IRBW branding

Transcripts are saved to the `transcripts/` directory and optionally uploaded to a configured channel.

## Audit System

Every significant action is logged:

- Ticket creation, opening, claiming, responding, closing, deletion
- User/role additions
- Transcript generation
- Permission changes
- Configuration reloads

Audit logs are stored in the database and optionally sent to a configured audit channel.

## Statistics

### User Statistics (`/stats`)

- Total tickets
- Tickets by status (pending, open, claimed, responded, closed, deleted)
- Tickets by category
- Responses received
- Recent tickets

### Admin Statistics (`/adminstats`)

- Total tickets, today, this week, this month
- Tickets by status
- Category distribution
- Average response time
- Average resolution time
- Staff activity (responses and claims)

## Hot Reload

Use `/reload` to reload configuration without restarting the bot:

- Reloads `config.json`
- Validates new configuration
- Retains current config if validation fails
- Logs the reload action

## Database

The bot uses SQLite for persistence:

- `tickets.db` - Main database file

### Tables

- `users` - User information
- `tickets` - Ticket records
- `ticket_messages` - Messages in ticket channels
- `claims` - Claim history
- `responses` - Staff responses
- `audit_logs` - Audit trail
- `counters` - Category ticket counters
- `permissions` - Permission configurations

### Backup

To backup the database:
```bash
cp tickets.db tickets_backup.db
```

## Troubleshooting

### Bot not responding to commands

1. Verify the bot token is correct in `.env`
2. Ensure the bot is in the configured guild
3. Check that application commands are synced
4. Verify the bot has `Use Application Commands` permission

### Commands not appearing

1. Run `/reload` to resync commands
2. Wait up to 1 hour for Discord's global command cache to update
3. Try re-inviting the bot with proper permissions

### Ticket panel not working

1. Verify the panel channel ID is correct
2. Ensure the bot has permission to send messages in that channel
3. Redeploy the panel with `/deploy`

### Permission errors

1. Check that roles exist in the server
2. Verify role IDs in the configuration
3. Ensure the user has the required roles
4. Remember admins bypass most permission checks

### Database errors

1. Ensure the bot has write permissions in the working directory
2. Check available disk space
3. Restart the bot if the database is locked

## License

MIT License
