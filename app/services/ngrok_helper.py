import logging
import requests

logger = logging.getLogger(__name__)

_cached_ngrok_url = None


def get_current_ngrok_url():
    """Return cached ngrok URL (set at startup by run.py)."""
    return _cached_ngrok_url


def set_ngrok_url(url):
    global _cached_ngrok_url
    _cached_ngrok_url = url
    logger.info(f"[ngrok_helper] URL set to: {url}")


def fetch_ngrok_url():
    """Query local ngrok API for the current HTTPS tunnel URL."""
    try:
        resp = requests.get("http://localhost:4040/api/tunnels", timeout=3)
        tunnels = resp.json().get("tunnels", [])
        for tunnel in tunnels:
            if tunnel.get("proto") == "https":
                return tunnel["public_url"]
    except Exception as e:
        logger.warning(f"[ngrok_helper] Could not reach ngrok API: {e}")
    return None


def push_to_twilio(ngrok_url, app):
    """Update Twilio phone number voice/sms webhook URLs."""
    try:
        from twilio.rest import Client
        client = Client(
            app.config["TWILIO_ACCOUNT_SID"],
            app.config["TWILIO_AUTH_TOKEN"],
        )
        twilio_number = app.config["TWILIO_PHONE_NUMBER"]
        numbers = client.incoming_phone_numbers.list(phone_number=twilio_number)
        if numbers:
            numbers[0].update(
                voice_url=f"{ngrok_url}/webhooks/twiml/0",
                voice_method="GET",
                status_callback=f"{ngrok_url}/webhooks/call-status",
                status_callback_method="POST",
            )
            logger.info(f"[ngrok_helper] Twilio webhooks updated → {ngrok_url}")
        else:
            logger.warning("[ngrok_helper] Twilio phone number not found in account.")
    except Exception as e:
        logger.error(f"[ngrok_helper] Failed to update Twilio webhooks: {e}")
