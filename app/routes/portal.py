from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from app import db
from app.models import Engineer, OncallSchedule, ScheduleChangeRequest

portal_bp = Blueprint("portal", __name__, url_prefix="/portal")


def _parse_dt(value):
    from zoneinfo import ZoneInfo
    import datetime as dt_module
    try:
        tz_str = current_app.config.get("APP_TIMEZONE", "Asia/Manila")
        tz = ZoneInfo(tz_str)
    except Exception:
        tz = ZoneInfo("Asia/Manila")

    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(value, fmt)
            dt_aware = dt.replace(tzinfo=tz)
            dt_utc = dt_aware.astimezone(dt_module.timezone.utc).replace(tzinfo=None)
            return dt_utc
        except ValueError:
            pass
    return None


@portal_bp.route("/<token>")
def view_portal(token):
    from zoneinfo import ZoneInfo
    import datetime as dt_module
    engineer = Engineer.query.filter_by(access_token=token).first_or_404()
    schedules = (
        OncallSchedule.query.filter_by(engineer_id=engineer.id, is_approved=True)
        .order_by(OncallSchedule.shift_start)
        .all()
    )
    change_requests = (
        ScheduleChangeRequest.query.filter_by(engineer_id=engineer.id)
        .order_by(ScheduleChangeRequest.submitted_at.desc())
        .limit(10)
        .all()
    )
    tz_str = current_app.config.get("APP_TIMEZONE", "Asia/Manila")
    tz = ZoneInfo(tz_str)

    def local_dt(dt_utc):
        """Convert a naive UTC datetime to a formatted local time string."""
        if not dt_utc:
            return ""
        aware = dt_utc.replace(tzinfo=dt_module.timezone.utc)
        local = aware.astimezone(tz)
        return local.strftime("%Y-%m-%d %H:%M")

    now_utc = datetime.utcnow()
    return render_template(
        "schedules/portal.html",
        engineer=engineer,
        schedules=schedules,
        change_requests=change_requests,
        token=token,
        now=now_utc,
        local_dt=local_dt,
        tz_label=tz_str.split("/")[-1].replace("_", " ") + " (GMT+8)",
    )


@portal_bp.route("/<token>/submit-request", methods=["POST"])
def submit_request(token):
    engineer = Engineer.query.filter_by(access_token=token).first_or_404()
    requested_start = _parse_dt(request.form.get("requested_start", ""))
    requested_end = _parse_dt(request.form.get("requested_end", ""))
    notes = request.form.get("notes", "").strip()

    if not requested_start or not requested_end:
        flash("Please enter valid start and end times.", "error")
        return redirect(url_for("portal.view_portal", token=token))

    if requested_end <= requested_start:
        flash("End time must be after start time.", "error")
        return redirect(url_for("portal.view_portal", token=token))

    auto_approve = current_app.config.get("AUTO_APPROVE_SCHEDULE", True)
    status = "approved" if auto_approve else "pending"

    req = ScheduleChangeRequest(
        engineer_id=engineer.id,
        requested_start=requested_start,
        requested_end=requested_end,
        status=status,
        notes=notes,
        reviewed_at=datetime.utcnow() if auto_approve else None,
    )
    db.session.add(req)

    if auto_approve:
        shift = OncallSchedule(
            engineer_id=engineer.id,
            shift_start=requested_start,
            shift_end=requested_end,
            is_approved=True,
        )
        db.session.add(shift)

    db.session.commit()
    flash("Schedule change request submitted successfully.", "success")
    return redirect(url_for("portal.view_portal", token=token))
