import logging
import threading
from datetime import datetime
from flask import current_app
from app import db
from app.models import Engineer, OncallSchedule, Incident, NotificationLog

logger = logging.getLogger(__name__)

# In-memory state (sufficient for 4 engineers, single-process deployment)
_lock = threading.Lock()
_active_incidents = {}   # incident_id -> {queue:[eng_id,...], index:int, call_sid:str}
_active_calls = {}       # call_sid -> {incident_id, engineer_id, index}
_safety_jobs = {}        # call_sid -> scheduler_job_id
_app_ref = None
_scheduler_ref = None


def init_orchestrator(app, scheduler):
    global _app_ref, _scheduler_ref
    _app_ref = app
    _scheduler_ref = scheduler


def resolve_call_queue():
    """Return ordered engineer list: on-shift first, then by queue_position."""
    now = datetime.utcnow()
    oncall_engineers = (
        Engineer.query.filter_by(is_oncall=True)
        .order_by(Engineer.queue_position)
        .all()
    )
    on_shift, off_shift = [], []
    for eng in oncall_engineers:
        active = OncallSchedule.query.filter(
            OncallSchedule.engineer_id == eng.id,
            OncallSchedule.is_approved == True,
            OncallSchedule.shift_start <= now,
            OncallSchedule.shift_end >= now,
        ).first()
        (on_shift if active else off_shift).append(eng)
    return on_shift + off_shift


def start_incident(incident_id):
    """Entry point: begin call chain for a new incident."""
    with _app_ref.app_context():
        queue = resolve_call_queue()
        if not queue:
            logger.warning(f"[orchestrator] No oncall engineers for incident {incident_id}")
            _sms_all_oncall(incident_id)
            return

        with _lock:
            _active_incidents[incident_id] = {
                "queue": [e.id for e in queue],
                "index": 0,
                "call_sid": None,
            }
        _place_call(incident_id, queue, 0)


def _place_call(incident_id, queue, index):
    from app.services.call_service import place_call

    with _app_ref.app_context():
        if index >= len(queue):
            logger.info(f"[orchestrator] All engineers exhausted for incident {incident_id}. SMS fallback.")
            _sms_all_oncall(incident_id)
            return

        engineer = queue[index]
        incident = Incident.query.get(incident_id)
        if not incident:
            return

        call_sid = place_call(incident, engineer)

        with _lock:
            state = _active_incidents.get(incident_id)
            if state:
                state["index"] = index
                state["call_sid"] = call_sid

        if call_sid:
            with _lock:
                _active_calls[call_sid] = {
                    "incident_id": incident_id,
                    "engineer_id": engineer.id,
                    "index": index,
                    "queue_ids": [e.id for e in queue],
                }
            _schedule_safety_timer(incident_id, call_sid, queue, index)
        else:
            # Call placement failed immediately — advance
            _advance_by_incident(incident_id, None, "failed")


def handle_call_status(call_sid, call_status):
    """Called by webhook route when Twilio POSTs call outcome."""
    # Atomically claim this call_sid. If already claimed (by webhook or safety timer),
    # return immediately — prevents double-SMS when both race each other.
    with _lock:
        call_info = _active_calls.pop(call_sid, None)

    if not call_info:
        logger.debug(f"[orchestrator] Unknown or already-processed call_sid {call_sid} — ignoring.")
        return

    _cancel_safety_timer(call_sid)

    incident_id = call_info["incident_id"]
    engineer_id = call_info["engineer_id"]
    queue_ids = call_info["queue_ids"]
    index = call_info["index"]

    with _app_ref.app_context():
        # Update log entry
        log = NotificationLog.query.filter_by(twilio_sid=call_sid).first()
        if log:
            log.status = call_status
            db.session.commit()

        if call_status == "completed":
            # Answered — send SMS, resolve incident
            from app.services.sms_service import send_sms
            engineer = Engineer.query.get(engineer_id)
            incident = Incident.query.get(incident_id)
            if engineer and incident:
                send_sms(incident, engineer)
                incident.status = "resolved"
                db.session.commit()
            with _lock:
                _active_incidents.pop(incident_id, None)
            logger.info(f"[orchestrator] Incident {incident_id} resolved by {engineer_id}.")
        else:
            # No answer / busy / failed — send SMS to the same engineer, then advance queue
            from app.services.sms_service import send_sms
            engineer = Engineer.query.get(engineer_id)
            incident = Incident.query.get(incident_id)
            if engineer and incident:
                send_sms(incident, engineer)
            queue = [Engineer.query.get(eid) for eid in queue_ids]
            queue = [e for e in queue if e]
            _place_call(incident_id, queue, index + 1)


def _advance_by_incident(incident_id, call_sid, reason):
    """Advance call chain (called from safety timer or immediate failure)."""
    with _lock:
        call_info = _active_calls.pop(call_sid, None) if call_sid else None
        state = _active_incidents.get(incident_id)

    if not state:
        return

    queue_ids = call_info["queue_ids"] if call_info else state.get("queue", [])
    index = call_info["index"] if call_info else state.get("index", 0)

    with _app_ref.app_context():
        queue = [Engineer.query.get(eid) for eid in queue_ids]
        queue = [e for e in queue if e]
        _place_call(incident_id, queue, index + 1)


def _schedule_safety_timer(incident_id, call_sid, queue, index):
    """APScheduler one-shot job: if no webhook in 70s, poll Twilio and advance."""
    from datetime import timedelta

    job_id = f"safety_{call_sid}"

    def _check():
        with _app_ref.app_context():
            try:
                from twilio.rest import Client
                client = Client(
                    _app_ref.config["TWILIO_ACCOUNT_SID"],
                    _app_ref.config["TWILIO_AUTH_TOKEN"],
                )
                call = client.calls(call_sid).fetch()
                status = call.status
            except Exception as e:
                logger.error(f"[orchestrator] Safety timer fetch failed: {e}")
                status = "failed"

            with _lock:
                still_pending = call_sid in _active_calls

            if still_pending:
                logger.warning(
                    f"[orchestrator] Safety timer fired for {call_sid} status={status}"
                )
                handle_call_status(call_sid, status if status != "in-progress" else "no-answer")

    from datetime import datetime as _dt, timedelta as _td
    run_at = _dt.utcnow() + _td(seconds=15)
    _scheduler_ref.add_job(
        _check, "date", run_date=run_at, id=job_id, replace_existing=True
    )
    with _lock:
        _safety_jobs[call_sid] = job_id


def _cancel_safety_timer(call_sid):
    with _lock:
        job_id = _safety_jobs.pop(call_sid, None)
    if job_id:
        try:
            _scheduler_ref.remove_job(job_id)
        except Exception:
            pass


def _sms_all_oncall(incident_id):
    """Fallback: SMS every oncall engineer."""
    from app.services.sms_service import send_sms
    with _app_ref.app_context():
        incident = Incident.query.get(incident_id)
        if not incident:
            return
        engineers = Engineer.query.filter_by(is_oncall=True).order_by(Engineer.queue_position).all()
        for eng in engineers:
            send_sms(incident, eng)
        with _lock:
            _active_incidents.pop(incident_id, None)
        logger.info(f"[orchestrator] SMS fallback complete for incident {incident_id}.")
