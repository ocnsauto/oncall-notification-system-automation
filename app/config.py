import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")

    # DATABASE_URL: set to your Supabase PostgreSQL URL on Render.
    # Falls back to local SQLite for development.
    _db_url = os.environ.get("DATABASE_URL", "sqlite:///oncall.db")
    # Render/Heroku give 'postgres://' but SQLAlchemy 2.x needs 'postgresql://'
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Base URL for Twilio webhooks. Set to your Render public URL in production.
    # On local dev this is overridden at runtime by ngrok_helper.
    BASE_URL = os.environ.get("BASE_URL", "")

    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

    APP_TIMEZONE = os.environ.get("APP_TIMEZONE", "Asia/Manila")

    GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")
    TWILIO_SMS_SENDER_ID = os.environ.get("TWILIO_SMS_SENDER_ID", TWILIO_PHONE_NUMBER)

    CLICKSEND_USERNAME = os.environ.get("CLICKSEND_USERNAME", "")
    CLICKSEND_API_KEY = os.environ.get("CLICKSEND_API_KEY", "")
    CLICKSEND_SENDER_ID = os.environ.get("CLICKSEND_SENDER_ID", "")

    COMPANY_NAME = os.environ.get("COMPANY_NAME", "Nebulynx")
    TTS_TEMPLATE = os.environ.get(
        "TTS_TEMPLATE",
        "This is an automated oncall notification from {company_name}. "
        "A network incident has been reported. "
        "Incident reference: {email_subject}. "
        "Details: {email_body_snippet}. "
        "Please respond immediately. A follow-up text message will follow this call.",
    )
    SMS_TEMPLATE = os.environ.get(
        "SMS_TEMPLATE",
        "[ONCALL ALERT] {company_name} | Incident: {email_subject} | {email_body_snippet} | Respond immediately.",
    )

    AUTO_APPROVE_SCHEDULE = os.environ.get("AUTO_APPROVE_SCHEDULE", "false").lower() == "true"
    INCIDENT_COOLDOWN_MINUTES = int(os.environ.get("INCIDENT_COOLDOWN_MINUTES", "5"))
    POLL_INTERVAL_SECONDS = int(os.environ.get("POLL_INTERVAL_SECONDS", "30"))
