# Nebulynx Oncall Notification System

Undergraduate capstone project. Monitors a dedicated Gmail inbox and automatically places sequential voice calls + SMS to on-call network engineers when an incident email arrives.

---

## Prerequisites

- macOS with Python 3.11+
- ngrok account (free): https://ngrok.com
- Twilio account with a purchased phone number
- A dedicated Gmail address with an App Password

---

## Quick Start

```bash
cd oncall-system
chmod +x setup.sh
./setup.sh
```

Then open two terminals:

**Terminal 1 — ngrok:**
```bash
ngrok http 5001
```

**Terminal 2 — app:**
```bash
source .venv/bin/activate
python run.py
```

Open http://localhost:5001 — login with `admin` / `admin123`.

---

## Gmail App Password Setup (Required)

The system uses IMAP to poll Gmail. Google requires an App Password (not your regular password) when 2-Step Verification is enabled.

1. Go to https://myaccount.google.com/security
2. Under "How you sign in to Google" → **2-Step Verification** → enable it
3. Search for **App passwords** at the top of the security page
4. Select app: **Mail** → device: **Other** → name it `oncall-imap`
5. Copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)
6. Open `.env` and set: `GMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx` (no spaces)

---

## ngrok Setup

1. Create a free account at https://ngrok.com
2. Go to https://dashboard.ngrok.com/get-started/your-authtoken
3. Copy your authtoken and run:
   ```bash
   ngrok config add-authtoken <your-token>
   ```
4. Start ngrok before starting the app:
   ```bash
   ngrok http 5000
   ```

The app auto-reads the ngrok URL on startup and pushes it to Twilio. **You do not need to manually configure Twilio webhook URLs.**

---

## Twilio Trial Account — Verify Engineer Numbers

Trial accounts can only call/SMS numbers that have been manually verified.

1. Go to https://console.twilio.com/us1/develop/phone-numbers/verified
2. Click **Add a new Caller ID**
3. Enter each engineer's phone number in E.164 format: `+639XXXXXXXXX`
4. Complete the verification call or SMS
5. Repeat for all 4 engineers

This is a one-time step per number. The demo will silently fail calls to unverified numbers.

---

## Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask session secret (change in production) |
| `ADMIN_USERNAME` | Admin login username |
| `ADMIN_PASSWORD` | Admin login password |
| `APP_TIMEZONE` | Display timezone (default: `Asia/Manila`) |
| `GMAIL_ADDRESS` | Monitored Gmail address |
| `GMAIL_APP_PASSWORD` | 16-char App Password from Google |
| `TWILIO_ACCOUNT_SID` | From Twilio console |
| `TWILIO_AUTH_TOKEN` | From Twilio console |
| `TWILIO_PHONE_NUMBER` | Your Twilio number in E.164 format |
| `COMPANY_NAME` | Used in TTS and SMS templates |
| `TTS_TEMPLATE` | Voice message template |
| `SMS_TEMPLATE` | SMS message template |
| `AUTO_APPROVE_SCHEDULE` | `true` = auto-approve engineer shift requests |
| `INCIDENT_COOLDOWN_MINUTES` | Minutes before a second email triggers a new incident |
| `POLL_INTERVAL_SECONDS` | Gmail poll frequency (default: 30) |

---

## How It Works

1. APScheduler polls Gmail INBOX every 30 seconds via IMAP SSL
2. Any new unseen email creates an `Incident` record
3. The orchestrator resolves call order: engineers on an active shift go first, then by queue position
4. Twilio places a voice call; engineer hears a TTS message populated with email subject/body
5. If answered → follow-up SMS sent, incident marked resolved
6. If no-answer/busy/failed → next engineer called (up to 70s timeout per call)
7. If all engineers miss → SMS blast to all oncall engineers
8. All outcomes logged in `NotificationLog` and visible in the admin panel

---

## Admin Panel Pages

| URL | Description |
|---|---|
| `/` | Dashboard — live incident feed with stats |
| `/engineers` | Add/edit/delete engineers, toggle oncall, manage queue order |
| `/schedules` | Add shifts, approve/reject engineer change requests |
| `/logs` | Filterable incident log with Excel export |
| `/auth/login` | Admin login |

---

## Engineer Portal

Each engineer gets a unique URL: `http://your-server/portal/<uuid-token>`

- No login required — the token is the access gate
- Engineers see their upcoming approved shifts
- Engineers can submit schedule change requests
- Bookmark the link; admin can regenerate the token if needed

---

## Call Cost Estimate

| Action | Cost |
|---|---|
| Outbound call (per minute) | ~$0.014 |
| SMS (per message) | ~$0.0079 |
| Demo with 3 test incidents | < $1.00 total |

Twilio trial credit ($15) is more than sufficient for the capstone demo.

---

## Project Structure

```
oncall-system/
├── app/                    # Flask application
│   ├── __init__.py         # App factory
│   ├── config.py           # Env-based configuration
│   ├── models.py           # SQLAlchemy models
│   ├── auth/               # Admin login/logout
│   ├── routes/             # All HTTP routes
│   └── services/           # Email monitor, orchestrator, Twilio
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS and JS
├── instance/               # SQLite database (gitignored)
├── run.py                  # Entry point
├── setup.sh                # One-command setup script
├── .env                    # Secrets (gitignored)
└── requirements.txt
```
