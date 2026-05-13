import logging
from flask import current_app
from twilio.rest import Client
from app import db
from app.models import NotificationLog

logger = logging.getLogger(__name__)


def get_twilio_client():
    return Client(
        current_app.config["TWILIO_ACCOUNT_SID"],
        current_app.config["TWILIO_AUTH_TOKEN"],
    )


def place_call(incident, engineer):
    """Place a Twilio voice call to the engineer. Returns call_sid or None."""
    from app.services.ngrok_helper import get_current_ngrok_url

    ngrok_url = get_current_ngrok_url()
    if not ngrok_url:
        logger.error("[call_service] No ngrok URL available. Cannot place call.")
        _log_failure(incident.id, engineer.id, "call", "no-ngrok")
        return None

    twiml_url = f"{ngrok_url}/webhooks/twiml/{incident.id}"
    status_url = f"{ngrok_url}/webhooks/call-status"

    try:
        client = get_twilio_client()
        call = client.calls.create(
            to=engineer.phone,
            from_=current_app.config["TWILIO_PHONE_NUMBER"],
            url=twiml_url,
            status_callback=status_url,
            status_callback_method="POST",
            timeout=60,
        )
        log = NotificationLog(
            incident_id=incident.id,
            engineer_id=engineer.id,
            type="call",
            status="initiated",
            twilio_sid=call.sid,
            notes=f"Call placed to {engineer.phone}",
        )
        db.session.add(log)
        db.session.commit()
        logger.info(f"[call_service] Call placed → SID={call.sid} engineer={engineer.name}")
        return call.sid
    except Exception as e:
        logger.error(f"[call_service] Failed to place call to {engineer.name}: {e}")
        _log_failure(incident.id, engineer.id, "call", "failed", str(e))
        return None


def _log_failure(incident_id, engineer_id, log_type, status, notes=None):
    try:
        log = NotificationLog(
            incident_id=incident_id,
            engineer_id=engineer_id,
            type=log_type,
            status=status,
            notes=notes,
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"[call_service] Could not write failure log: {e}")
