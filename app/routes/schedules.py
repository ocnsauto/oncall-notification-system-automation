from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required
from app import db
from app.models import Engineer, OncallSchedule, ScheduleChangeRequest

schedules_bp = Blueprint("schedules", __name__, url_prefix="/schedules")


def _parse_dt(value):
    """Parse datetime-local input string from local timezone to UTC."""
    from zoneinfo import ZoneInfo
    import datetime as dt_module
    
    # We must access current_app here, but _parse_dt is called inside routes.
    # We can do it safely because it's only called during a request context.
    try:
        tz_str = current_app.config.get("APP_TIMEZONE", "Asia/Manila")
        tz = ZoneInfo(tz_str)
    except Exception:
        from app.config import Config
        tz = ZoneInfo(Config.APP_TIMEZONE)

    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(value, fmt)
            # Make aware in local timezone, then convert to UTC, then make naive for DB
            dt_aware = dt.replace(tzinfo=tz)
            dt_utc = dt_aware.astimezone(dt_module.timezone.utc).replace(tzinfo=None)
            return dt_utc
        except ValueError:
            pass
    return None


@schedules_bp.route("/")
@login_required
def admin_schedules():
    engineers = Engineer.query.order_by(Engineer.queue_position).all()
    schedules = OncallSchedule.query.order_by(OncallSchedule.shift_start).all()
    pending = (
        ScheduleChangeRequest.query.filter_by(status="pending")
        .order_by(ScheduleChangeRequest.submitted_at)
        .all()
    )
    return render_template(
        "schedules/admin.html",
        engineers=engineers,
        schedules=schedules,
        pending=pending,
    )


@schedules_bp.route("/add", methods=["POST"])
@login_required
def add_shift():
    engineer_id = int(request.form.get("engineer_id", 0))
    shift_start = _parse_dt(request.form.get("shift_start", ""))
    shift_end = _parse_dt(request.form.get("shift_end", ""))

    if not engineer_id or not shift_start or not shift_end:
        flash("All fields are required.", "error")
        return redirect(url_for("schedules.admin_schedules"))

    if shift_end <= shift_start:
        flash("Shift end must be after shift start.", "error")
        return redirect(url_for("schedules.admin_schedules"))

    # Overlap detection
    overlap = OncallSchedule.query.filter(
        OncallSchedule.engineer_id == engineer_id,
        OncallSchedule.is_approved == True,
        OncallSchedule.shift_start < shift_end,
        OncallSchedule.shift_end > shift_start,
    ).first()
    if overlap:
        flash("Warning: This shift overlaps with an existing approved shift for this engineer.", "warning")

    shift = OncallSchedule(
        engineer_id=engineer_id,
        shift_start=shift_start,
        shift_end=shift_end,
        is_approved=True,
    )
    db.session.add(shift)
    db.session.commit()
    flash("Shift added.", "success")
    return redirect(url_for("schedules.admin_schedules"))


@schedules_bp.route("/<int:shift_id>/delete", methods=["POST"])
@login_required
def delete_shift(shift_id):
    shift = OncallSchedule.query.get_or_404(shift_id)
    db.session.delete(shift)
    db.session.commit()
    flash("Shift deleted.", "info")
    return redirect(url_for("schedules.admin_schedules"))


@schedules_bp.route("/change-request/<int:req_id>/approve", methods=["POST"])
@login_required
def approve_request(req_id):
    req = ScheduleChangeRequest.query.get_or_404(req_id)
    req.status = "approved"
    req.reviewed_at = datetime.utcnow()
    shift = OncallSchedule(
        engineer_id=req.engineer_id,
        shift_start=req.requested_start,
        shift_end=req.requested_end,
        is_approved=True,
    )
    db.session.add(shift)
    db.session.commit()
    flash("Schedule change request approved and shift created.", "success")
    return redirect(url_for("schedules.admin_schedules"))


@schedules_bp.route("/change-request/<int:req_id>/reject", methods=["POST"])
@login_required
def reject_request(req_id):
    req = ScheduleChangeRequest.query.get_or_404(req_id)
    req.status = "rejected"
    req.reviewed_at = datetime.utcnow()
    db.session.commit()
    flash("Schedule change request rejected.", "info")
    return redirect(url_for("schedules.admin_schedules"))


@schedules_bp.route("/sync-queues", methods=["POST"])
@login_required
def sync_queues():
    now = datetime.utcnow()
    # Find all active shifts right now
    active_shifts = OncallSchedule.query.filter(
        OncallSchedule.is_approved == True,
        OncallSchedule.shift_start <= now,
        OncallSchedule.shift_end >= now
    ).all()
    
    active_engineers_info = {}
    for shift in active_shifts:
        if shift.engineer_id not in active_engineers_info:
            active_engineers_info[shift.engineer_id] = shift.shift_start
        else:
            if shift.shift_start < active_engineers_info[shift.engineer_id]:
                active_engineers_info[shift.engineer_id] = shift.shift_start

    # Get all engineers ordered by current queue position
    engineers = Engineer.query.order_by(Engineer.queue_position).all()
    
    # Toggle is_oncall: ON for engineers on active shifts, OFF for everyone else
    on_count = 0
    off_count = 0
    for e in engineers:
        if e.id in active_engineers_info:
            e.is_oncall = True
            on_count += 1
        else:
            e.is_oncall = False
            off_count += 1

    # Split into active and inactive, preserving relative order
    active_engineers = [e for e in engineers if e.id in active_engineers_info]
    inactive_engineers = [e for e in engineers if e.id not in active_engineers_info]
    
    # Sort active engineers by who started their shift earliest
    active_engineers.sort(key=lambda e: active_engineers_info[e.id])
    
    # Re-assign queue positions 1 to N
    for i, e in enumerate(active_engineers + inactive_engineers, start=1):
        e.queue_position = i
        
    db.session.commit()
    flash(
        f"Sync complete: {on_count} engineer(s) enabled (on shift), {off_count} disabled (no active shift). Queues reordered.",
        "success"
    )
    return redirect(url_for("schedules.admin_schedules"))
