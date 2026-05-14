import logging
from flask import current_app
from twilio.rest import Client
from app import db
from app.models import NotificationLog

logger = logging.getLogger(__name__)

MAX_SMS_LENGTH = 160


def send_sms(incident, engineer):
    """Send a SMS to the engineer using ClickSend or Twilio. Returns message_sid or None."""
    body = _build_sms_body(incident)

    clicksend_user = current_app.config.get("CLICKSEND_USERNAME")
    clicksend_key = current_app.config.get("CLICKSEND_API_KEY")
    clicksend_sender = current_app.config.get("CLICKSEND_SENDER_ID")

    if clicksend_user and clicksend_key:
        return _send_via_clicksend(incident, engineer, body, clicksend_user, clicksend_key, clicksend_sender)
    else:
        return _send_via_twilio(incident, engineer, body)

def _send_via_clicksend(incident, engineer, body, username, api_key, sender_id):
    import requests
    from requests.auth import HTTPBasicAuth
    try:
        # ClickSend requires E.164 format with '+'
        phone = engineer.phone.strip()
        if not phone.startswith("+"):
            if phone.startswith("63"): # Philippines
                 phone = "+" + phone
            elif phone.startswith("0"): # Local format
                 phone = "+63" + phone[1:]
            else:
                 phone = "+" + phone

        url = "https://rest.clicksend.com/v3/sms/send"
        payload = {
            "messages": [
                {
                    "source": "python",
                    "body": body,
                    "to": phone
                }
            ]
        }
        if sender_id:
            payload["messages"][0]["from"] = sender_id

        logger.info(f"[sms_service] Attempting ClickSend SMS to {phone} (From: {sender_id or 'Shared Number'})...")
        resp = requests.post(url, json=payload, auth=HTTPBasicAuth(username, api_key))
        data = resp.json()
        
        logger.debug(f"[sms_service] ClickSend Full Response: {data}")

        if resp.status_code == 200 and data.get("http_code") == 200:
            msg_data = data["data"]["messages"][0]
            msg_id = msg_data.get("message_id")
            # Some regions/accounts return 'SUCCESS', others might be different
            status = str(msg_data.get("status", "")).upper()
            
            if status == "SUCCESS":
                log = NotificationLog(
                    incident_id=incident.id,
                    engineer_id=engineer.id,
                    type="sms",
                    status="sent",
                    twilio_sid=msg_id,
                    notes=f"ClickSend SMS success to {phone}",
                )
                db.session.add(log)
                db.session.commit()
                logger.info(f"[sms_service] ClickSend SMS Sent Successfully! ID={msg_id}")
                return msg_id
            else:
                # The error message is usually at the top level 'response_string'
                error_msg = data.get("response_string") or msg_data.get("response_string") or "Unknown ClickSend Error"
                raise Exception(f"ClickSend Delivery Error: {error_msg} (Status: {status})")
        else:
            logger.error(f"[sms_service] ClickSend API Failure Raw: {data}")
            raise Exception(f"ClickSend HTTP Error {resp.status_code}: {data.get('response_string', resp.text)}")
    except Exception as e:
        logger.error(f"[sms_service] Failed to send ClickSend SMS: {e}")
        db.session.rollback()
        _log_sms_failure(incident, engineer, str(e))
        return None

def _send_via_twilio(incident, engineer, body):
    try:
        client = Client(
            current_app.config["TWILIO_ACCOUNT_SID"],
            current_app.config["TWILIO_AUTH_TOKEN"],
        )
        msg = client.messages.create(
            to=engineer.phone,
            from_=current_app.config["TWILIO_SMS_SENDER_ID"],
            body=body,
        )
        log = NotificationLog(
            incident_id=incident.id,
            engineer_id=engineer.id,
            type="sms",
            status="sent",
            twilio_sid=msg.sid,
            notes=f"Twilio SMS sent to {engineer.phone}",
        )
        db.session.add(log)
        db.session.commit()
        logger.info(f"[sms_service] Twilio SMS sent → SID={msg.sid} engineer={engineer.name}")
        return msg.sid
    except Exception as e:
        logger.error(f"[sms_service] Failed to send Twilio SMS to {engineer.name}: {e}")
        db.session.rollback()
        _log_sms_failure(incident, engineer, str(e))
        return None

def _log_sms_failure(incident, engineer, error_msg):
    try:
        log = NotificationLog(
            incident_id=incident.id,
            engineer_id=engineer.id,
            type="sms",
            status="failed",
            notes=error_msg,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _build_sms_body(incident):
    template = current_app.config["SMS_TEMPLATE"]
    company = current_app.config["COMPANY_NAME"]
    subject = incident.email_subject or "Unknown"
    snippet = incident.body_snippet or ""

    # Assemble without snippet first to measure fixed length
    fixed = template.format(
        company_name=company,
        email_subject=subject,
        email_body_snippet="",
    )
    budget = MAX_SMS_LENGTH - len(fixed)
    if budget < 0:
        budget = 0
    snippet = snippet[:budget]

    body = template.format(
        company_name=company,
        email_subject=subject,
        email_body_snippet=snippet,
    )
    if len(body) > MAX_SMS_LENGTH:
        body = body[:MAX_SMS_LENGTH]
    return body
