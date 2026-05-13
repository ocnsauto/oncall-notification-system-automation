from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app
from flask_login import login_required
from app import db
from app.models import Engineer, OncallSchedule, ScheduleChangeRequest

schedules_bp = Blueprint("schedules", __name__, url_prefix="/schedules")


def _parse_dt(value):
    """Parse datetime-local input string."""
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
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
