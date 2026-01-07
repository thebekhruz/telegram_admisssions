# Oxbridge International School - Telegram Concierge Bot

A premium, human-centric Telegram bot for lead generation and admissions support at Oxbridge International School.

## Philosophy

**Automation = Data capture + Reminders**
**Humans = Relationships + Sales + Complex conversations**

Think of it like a luxury hotel concierge: the system handles reservations and wake-up calls, but a real person greets you, understands your preferences, and makes recommendations.

## Features

### 1. Language Selection (Full Auto)
- Supports 4 languages: Russian, Uzbek, English, Turkish
- First interaction when user starts the bot

### 2. Phone Capture + CRM Sync (Full Auto)
- Validates phone number format
- **Smart Formatting:** Automatically adds `+998` if user enters 7 or 9 digits
- Automatically creates/updates contact in Kommo CRM
- Saves `Telegram ID`, `Username`, and `Language` to CRM Contact
- Saves `Parent Name` to CRM Contact

### 3. Basic Qualification (Full Auto)
- 3 simple questions:
  - How many children?
  - Age of each child?
  - Which program interests them?
- All answers pushed to Kommo Lead immediately

### 4. 2-Way Communication (Human-in-the-loop)
- **User -> Manager:** Messages sent to the bot are automatically added as **Notes** to the Lead in CRM.
- **Manager -> User:** Managers can reply directly from the CRM Note by starting the note with `>>>` or `!`. The bot forwards this text to the user.

### 5. Handoff to Admissions (Full Auto)
- Creates task in Kommo: "New lead - call within 1 hour"
- Sends notification to admissions team via Telegram Group
- Provides channel invitation while waiting

### 6. Tour Booking (Self-Service)
- Calendar-based booking system
- Campus selection (MU Campus, Yashnobod)
- Date and time selection
- Saves to Kommo with structured data

### 7. Tour Reminders (Full Auto)
- Automated reminder sent 1 day before tour
- Includes campus info, address, and map
- User can confirm, reschedule, or cancel

### 8. Post-Tour Follow-up (Full Auto)
- Sent 1 day after tour (if status = attended)
- Offers to connect with admissions manager

### 9. Simple Menu (Full Auto)
- Book tour
- Campus addresses
- Contact manager
- Channel link

### 10. Channel Invitation (Full Auto)
- Integrated at handoff and in menu

## Automation Triggers

| Trigger | Action |
|---------|--------|
| User completes qualification | Notify admissions + create Kommo task |
| User sends message | Add Note to CRM Lead |
| Manager writes `>>> Hello` in Note | Send "Hello" to User via Bot |
| User books tour | Save to Kommo, schedule reminder |
| 1 day before tour | Send reminder message |
| User confirms/reschedules/cancels | Update Kommo, notify admissions if needed |
| 1 day after tour (if attended) | Send follow-up message |
| User clicks "Contact manager" anytime | Notify admissions |

## Tour Status Tracking

The bot uses a **hybrid approach** for tracking tour attendance:

1. **Pipeline Stages in Kommo:**
   - New Lead → Qualified → Tour Booked → Tour Attended/No-Show

2. **Bot-Assisted Updates:**
   - Day after tour, bot sends reminder to admissions group
   - One-click update via Telegram buttons
   - Updates both local database and Kommo CRM

This ensures follow-ups are never forgotten while minimizing manual work.

## Installation

### Prerequisites
- Python 3.9+
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- amoCRM account with API access (Kommo = amoCRM rebranded)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd telegram_simle_concierge
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

   **Required environment variables:**
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `AMOCRM_SUBDOMAIN`: Your amoCRM subdomain (e.g., "yourcompany" from yourcompany.amocrm.ru)
   - `AMOCRM_DOMAIN`: Your domain (amocrm.ru or amocrm.com)
   - `AMOCRM_CLIENT_ID`: Client ID from your integration
   - `AMOCRM_CLIENT_SECRET`: Client Secret from your integration
   - `AMOCRM_ACCESS_TOKEN`: Access token (from get_amocrm_token.py)
   - `AMOCRM_REFRESH_TOKEN`: Refresh token (from get_amocrm_token.py)
   - `ADMISSIONS_CHAT_ID`: Telegram chat ID for admissions notifications
   - `CHANNEL_USERNAME`: Your channel username (e.g., @oxbridge_news)
   - `CHANNEL_LINK`: Link to your Telegram channel
   - Campus addresses and map links

4. **Get amoCRM Custom Field IDs:**
   The bot relies on specific Custom Field IDs for mapping data (e.g., Children Count, Program, etc.).
   Run the helper script to see your account's fields:
   ```bash
   python check_fields.py
   ```
   Update `kommo.py` with the correct IDs if they differ from the defaults.

5. **Run the Bot:**
   ```bash
   python bot.py
   ```

### Webhooks & 2-Way Chat Setup

For the 2-way communication to work (Manager -> User), the bot runs a local web server that receives webhooks from amoCRM.

1. The bot automatically starts an **Ngrok** tunnel on startup (if `NGROK_AUTH_TOKEN` is provided).
2. It prints the public URL in the console: `https://xxxx.ngrok-free.app/kommo-webhook`
3. **Go to amoCRM:** Settings -> Integrations -> Your Integration -> Webhooks.
4. **Add Webhook:** Paste the URL provided by the bot.
   - Event: **Note added** (or all Note events).

Now, when a manager adds a note starting with `>>>` in a Lead card, the webhook sends it to the bot, which forwards it to the Telegram user.

## Admin Commands (Optional)

You can extend the bot with manual admin commands (requires configuration in `bot.py`):

```
/remind [phone] - Send tour reminder manually
/followup [phone] - Send post-tour follow-up manually
/broadcast [message] - Send broadcast to all users
```

## File Structure

```
telegram_simle_concierge/
├── bot.py              # Main bot logic, handlers, and webhook server
├── config.py           # Configuration management
├── database.py         # Simple JSON-based database
├── kommo.py           # Kommo CRM API integration
├── scheduler.py        # Automated reminders scheduler
├── translations.py     # Multi-language support
├── check_fields.py     # Utility to fetch CRM field IDs
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables template
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Database

The bot uses a simple JSON-based database (`bot_data.json`) for storing:
- User states and preferences
- Tour bookings
- Lead IDs for CRM sync

**Note:** For production with high volume, consider migrating to PostgreSQL or Redis.

## Deployment

### Option 1: Local / VPS with Ngrok
The simplest way is to run `python bot.py`. It handles the tunneling automatically.

### Option 2: Production Server
For a permanent deployment:
1. Set up a real domain/subdomain pointing to your server.
2. Configure Nginx/Apache as a reverse proxy to port 8000.
3. Disable Ngrok in the code or config.
4. Update the Webhook URL in amoCRM to your permanent domain.

## Monitoring

The bot logs all activities to console. Key events:
- New Lead creation
- Webhook events (incoming notes)
- Tunnel status
- Scheduler jobs

## Support

For questions or issues:
1. Check the logs for error messages
2. Verify Kommo API credentials
3. Ensure bot token is valid
4. Check network connectivity

## License

Proprietary - Oxbridge International School

## Credits

Built with:
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [APScheduler](https://apscheduler.readthedocs.io/)
- [amoCRM API](https://www.amocrm.ru/developers/content/crm_platform/)
