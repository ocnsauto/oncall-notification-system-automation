import threading
import logging
from flask import Blueprint, request, Response, current_app
from twilio.twiml.voice_response import VoiceResponse
from app.models import Incident
from app.services.orchestrator import handle_call_status

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint("webhooks", __name__, url_prefix="/webhooks")


@webhooks_bp.route("/twiml/<int:incident_id>", methods=["GET", "POST"])
def twiml(incident_id):
    """Return TwiML voice response for the given incident."""
    incident = Incident.query.get(incident_id) if incident_id else None
    company = current_app.config.get("COMPANY_NAME", "Nebulynx")
    template = current_app.config.get("TTS_TEMPLATE", "")

    if incident:
        subject = incident.email_subject or "Unknown"
        snippet = incident.body_snippet or ""
        message = template.format(
            company_name=company,
            email_subject=subject,
            email_body_snippet=snippet,
        )
    else:
        message = f"This is an automated oncall notification from {company}. Please check your systems."

    response = VoiceResponse()
    response.say(message, voice="Polly.Matthew", language="en-US")
    response.pause(length=1)
    response.say("End of message. Goodbye.", voice="Polly.Matthew", language="en-US")

    return Response(str(response), mimetype="text/xml")


@webhooks_bp.route("/call-status", methods=["POST"])
def call_status():
    """Twilio POSTs call status updates here."""
    call_sid = request.form.get("CallSid", "")
    call_status_value = request.form.get("CallStatus", "")

    logger.info(f"[webhooks] call-status SID={call_sid} status={call_status_value}")

    if call_sid and call_status_value in ("completed", "no-answer", "busy", "failed"):
        # Run in background thread so it gets a clean app context.
        # Running handle_call_status directly inside a Flask request context
        # causes the nested app_context inside it to fail silently on DB/SMS ops.
        t = threading.Thread(
            target=handle_call_status,
            args=(call_sid, call_status_value),
            daemon=True,
        )
        t.start()

    return "", 204
