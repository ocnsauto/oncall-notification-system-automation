import imaplib
import email
import logging
from datetime import datetime, timedelta
from email.header import decode_header
from flask import current_app
from app import db
from app.models import Incident, NotificationLog

logger = logging.getLogger(__name__)

_scheduler = None
_app = None


def start_scheduler(app, scheduler):
    global _scheduler, _app
    _scheduler = scheduler
    _app = app
    interval = app.config.get("POLL_INTERVAL_SECONDS", 30)
    scheduler.add_job(
        _poll_inbox,
        "interval",
        seconds=interval,
        id="email_poll",
        replace_existing=True,
        next_run_time=datetime.utcnow(),
    )
    logger.info(f"[email_monitor] Polling Gmail every {interval}s.")


def _decode_header_value(value):
    parts = decode_header(value or "")
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _get_plain_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace") if payload else ""
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace") if payload else ""
    return ""


def _poll_inbox():
    with _app.app_context():
        gmail = _app.config["GMAIL_ADDRESS"]
        password = _app.config["GMAIL_APP_PASSWORD"]
        cooldown = _app.config.get("INCIDENT_COOLDOWN_MINUTES", 5)

        if not gmail or not password:
            logger.warning("[email_monitor] Gmail credentials not configured.")
            return

        try:
            mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
            mail.login(gmail, password)
            mail.select("INBOX")

            # Search for unseen emails
            status, data = mail.search(None, "UNSEEN")
            if status != "OK":
                mail.logout()
                return

            email_ids = data[0].split()
            if not email_ids:
                mail.logout()
                return

            for eid in email_ids:
                try:
                    _process_email(mail, eid, cooldown)
                except Exception as e:
                    logger.error(f"[email_monitor] Error processing email {eid}: {e}")

            mail.logout()

        except imaplib.IMAP4.error as e:
            logger.error(f"[email_monitor] IMAP error: {e}")
        except Exception as e:
            logger.error(f"[email_monitor] Unexpected error: {e}")


def _process_email(mail, eid, cooldown_minutes):
    # Fetch headers first for dedup check
    status, data = mail.fetch(eid, "(RFC822)")
    if status != "OK":
        return

    raw = data[0][1]
    msg = email.message_from_bytes(raw)

    message_id = msg.get("Message-ID", "").strip()
    if not message_id:
        message_id = f"no-id-{eid.decode()}-{datetime.utcnow().isoformat()}"

    # Deduplication
    existing = Incident.query.filter_by(message_id=message_id).first()
    if existing:
        logger.debug(f"[email_monitor] Duplicate message_id={message_id}, skipping.")
        mail.store(eid, "+FLAGS", "\\Seen")
        return

    # Cooldown check: suppress if active incident < cooldown_minutes old
    cutoff = datetime.utcnow() - timedelta(minutes=cooldown_minutes)
    recent_active = Incident.query.filter(
        Incident.status == "active",
        Incident.triggered_at >= cutoff,
    ).first()
    if recent_active:
        logger.info(
            f"[email_monitor] Duplicate suppressed — active incident {recent_active.id} is recent."
        )
        mail.store(eid, "+FLAGS", "\\Seen")
        _log_suppressed(recent_active.id, message_id)
        return

    subject = _decode_header_value(msg.get("Subject", "(no subject)"))
    body = _get_plain_body(msg)

    incident = Incident(
        email_subject=subject,
        email_body_raw=body,
        message_id=message_id,
        status="active",
    )
    db.session.add(incident)
    db.session.flush()  # get incident.id

    # Trigger log
    trigger_log = NotificationLog(
        incident_id=incident.id,
        type="trigger",
        status="new",
        notes=f"Email received: {subject[:100]}",
    )
    db.session.add(trigger_log)
    db.session.commit()

    mail.store(eid, "+FLAGS", "\\Seen")
    logger.info(f"[email_monitor] New incident #{incident.id}: {subject[:60]}")

    # Hand off to orchestrator (in background thread to not block APScheduler)
    import threading
    t = threading.Thread(
        target=_fire_orchestrator,
        args=(incident.id,),
        daemon=True,
    )
    t.start()


def _fire_orchestrator(incident_id):
    from app.services.orchestrator import start_incident
    start_incident(incident_id)


def _log_suppressed(incident_id, message_id):
    try:
        log = NotificationLog(
            incident_id=incident_id,
            type="info",
            status="suppressed",
            notes=f"Duplicate email suppressed. message_id={message_id}",
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"[email_monitor] Could not log suppressed: {e}")
