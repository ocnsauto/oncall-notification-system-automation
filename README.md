# Nebulynx Oncall Notification System

Undergraduate capstone project. Monitors a dedicated Gmail inbox and automatically places sequential voice calls + SMS to on-call network engineers when an incident email arrives.

**Live deployment:** [https://oncall-system.onrender.com](https://oncall-system.onrender.com)

---

## Deployment Stack

| Layer | Service |
|---|---|
| **App Hosting** | [Render.com](https://render.com) — Web Service (free tier) |
| **Database** | [Supabase](https://supabase.com) — PostgreSQL (cloud-hosted) |
| **Keep-Alive** | [cron-job.org](https://cron-job.org) — pings Render every 5 min to prevent sleep |
| **Voice & SMS** | [Twilio](https://twilio.com) — outbound calls + SMS |
| **Email Monitoring** | Gmail IMAP with App Password |
| **Secondary SMS** | [ClickSend](https://clicksend.com) (optional fallback) |

---

## Accessing the Admin Panel

Navigate to the live URL and log in:

- **URL:** `https://oncall-system.onrender.com`
- **Username:** set via `ADMIN_USERNAME` environment variable on Render
- **Password:** set via `ADMIN_PASSWORD` environment variable on Render

> Credentials are managed via Render's **Environment** settings tab — not in code.

---

## Gmail App Password Setup (Required)

The system uses IMAP to poll Gmail. Google requires an App Password (not your regular password) when 2-Step Verification is enabled.

1. Go to https://myaccount.google.com/security
2. Under "How you sign in to Google" → **2-Step Verification** → enable it
3. Search for **App passwords** at the top of the security page
4. Select app: **Mail** → device: **Other** → name it `oncall-imap`
5. Copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)
6. In Render → **Environment** → set: `GMAIL_APP_PASSWORD=xxxxxxxxxxxxxxxx` (no spaces)

---

## Twilio Trial Account — Verify Engineer Numbers

Trial accounts can only call/SMS numbers that have been manually verified.

1. Go to https://console.twilio.com/us1/develop/phone-numbers/verified
2. Click **Add a new Caller ID**
3. Enter each engineer's phone number in E.164 format: `+639XXXXXXXXX`
4. Complete the verification call or SMS
5. Repeat for all engineers

This is a one-time step per number. Calls to unverified numbers will silently fail.

---

## Environment Variables

All secrets are configured via **Render → Environment** (never committed to the repo).

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask session secret |
| `ADMIN_USERNAME` | Admin login username |
| `ADMIN_PASSWORD` | Admin login password (synced to DB on every deploy) |
| `APP_TIMEZONE` | Display timezone (default: `Asia/Manila`) |
| `BASE_URL` | Full public URL of the Render service (e.g. `https://oncall-system.onrender.com`) |
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `GMAIL_ADDRESS` | Monitored Gmail address |
| `GMAIL_APP_PASSWORD` | 16-char App Password from Google |
| `TWILIO_ACCOUNT_SID` | From Twilio console |
| `TWILIO_AUTH_TOKEN` | From Twilio console |
| `TWILIO_PHONE_NUMBER` | Your Twilio number in E.164 format |
| `CLICKSEND_USERNAME` | ClickSend account email (optional) |
| `CLICKSEND_API_KEY` | ClickSend API key (optional) |
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
3. A background job (every 60s) auto-toggles each engineer's on-call status based on approved shift coverage at the current time
4. The orchestrator resolves call order: engineers on an active shift go first (sorted by earliest shift start), then by queue position
5. Twilio places a voice call; engineer hears a TTS message populated with email subject/body
6. If **answered** → SMS sent immediately, incident marked resolved, call chain stops
7. If **no-answer / busy / failed** → SMS sent to that engineer, next engineer called (40s timeout per call)
8. If all engineers miss → SMS blast to all on-call engineers
9. All outcomes logged in `NotificationLog` and visible in the admin panel
10. A `_processed_calls` guard prevents double-SMS when the safety timer and Twilio webhook race each other

---

## Admin Panel Pages

| URL | Description |
|---|---|
| `/` | Dashboard — live tail of the 10 most recent incidents, auto-updates every 30s without full reload |
| `/engineers` | Add/edit/delete engineers, manual on-call toggle, queue reordering |
| `/schedules` | Add shifts, approve/reject engineer change requests, Sync Queues button, Auto-Sync toggle |
| `/logs` | Filterable + paginated incident log with Excel export (Weekly/Monthly) |
| `/portal/<token>` | Engineer self-service portal (no login needed) |
| `/auth/login` | Admin login |

---

## On-Call Status Logic

- **New engineers** are created as **Off-Call** by default
- On-call status is enabled automatically when an approved shift covers the current time
- On-call status is disabled automatically when a shift ends
- Admins can also manually toggle status from the Engineers page at any time
- The **"Sync Queues with Shifts"** button in Schedules does a full sync immediately (toggles status + reorders queue)
- The **"Auto-Sync: ON/OFF"** toggle in Schedules controls whether the Engineers page auto-syncs every 15 seconds in the background

---

## Engineer Portal

Each engineer gets a unique URL: `https://oncall-system.onrender.com/portal/<uuid-token>`

- No login required — the token is the access gate
- Engineers see their upcoming approved shifts (times displayed in GMT+8)
- Engineers can submit schedule change requests
- Bookmark the link; admin can regenerate the token if needed from the Engineers page

---

## Live UI Updates

| Page | Behavior |
|---|---|
| **Dashboard** | Patches the incident table every 30s (3s after Engineers sync). Expanded detail rows are preserved — no full page reload. |
| **Engineers** | Calls the sync API every 15s, then patches the engineers table. On-call toggles are re-attached after each patch. |
| **Logs** | Static page with filter + pagination. Navigate to view historical entries. |

---

## Call Cost Estimate

| Action | Cost |
|---|---|
| Outbound call (per minute) | ~$0.014 |
| SMS (per message) | ~$$0.0079 |
| Demo with 3 test incidents | < $1.00 total |

Twilio trial credit ($15) is sufficient for a full capstone demo.

---

## Redeployment

Any `git push` to `main` triggers an automatic redeploy on Render.

To update `ADMIN_PASSWORD`:
1. Change the value in Render → **Environment**
2. Trigger a manual redeploy (or push a new commit)
3. The app syncs the new password to the database on startup via `seed_database()` in `run.py`

> **Do not** edit the password directly in the database — it will be overwritten on next deploy.

---

## Local Development (Optional)

If running locally for development, ngrok is required for Twilio webhooks:

```bash
# Terminal 1
ngrok http 5001

# Terminal 2
cp .env.example .env   # fill in your secrets
pip install -r requirements.txt
python run.py
```

The app auto-reads the ngrok URL on startup and pushes it to Twilio. The local DB defaults to SQLite unless `DATABASE_URL` is set in `.env`.

---

## Project Structure

```
codebase/
├── app/                    # Flask application
│   ├── __init__.py         # App factory
│   ├── config.py           # Env-based configuration
│   ├── models.py           # SQLAlchemy models
│   ├── routes/             # All HTTP routes (dashboard, engineers, schedules, logs, portal, webhooks)
│   └── services/           # Email monitor, orchestrator, call service, SMS service
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS and JS (main.js handles live polling)
├── run.py                  # Entry point + background job registration
├── Procfile                # Gunicorn start command for Render
├── .env.example            # Template for required environment variables
└── requirements.txt
```
