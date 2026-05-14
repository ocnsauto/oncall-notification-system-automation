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
    from flask import current_app as _app
    from app.services.ngrok_helper import get_current_ngrok_url

    # On Render, BASE_URL is set as an env var (the permanent public URL).
    # Locally, ngrok provides the tunneled URL.
    base_url = _app.config.get("BASE_URL") or get_current_ngrok_url()
    if not base_url:
        logger.error("[call_service] No public URL available (BASE_URL or ngrok). Cannot place call.")
        _log_failure(incident.id, engineer.id, "call", "no-url")
        return None

    twiml_url = f"{base_url}/webhooks/twiml/{incident.id}"
    status_url = f"{base_url}/webhooks/call-status"

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
        try:
            db.session.add(log)
            db.session.commit()
        except Exception as db_e:
            db.session.rollback()
            logger.warning(f"[call_service] DB commit failed, retrying once: {db_e}")
            db.session.add(log)
            db.session.commit()

        logger.info(f"[call_service] Call placed → SID={call.sid} engineer={engineer.name}")
        return call.sid
    except Exception as e:
        logger.error(f"[call_service] Failed to place call to {engineer.name}: {e}")
        db.session.rollback()
        _log_failure(incident.id, engineer.id, "call", "failed", str(e))
        return None


def _log_failure(incident_id, engineer_id, log_type, status, notes=None):
    log = NotificationLog(
        incident_id=incident_id,
        engineer_id=engineer_id,
        type=log_type,
        status=status,
        notes=notes,
    )
    try:
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.warning(f"[call_service] Could not write failure log, retrying: {e}")
        try:
            db.session.add(log)
            db.session.commit()
        except Exception as retry_e:
            db.session.rollback()
            logger.error(f"[call_service] Retry failed for failure log: {retry_e}")
