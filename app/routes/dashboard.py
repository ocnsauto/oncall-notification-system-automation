from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Incident, NotificationLog, Engineer

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    incidents = (
        Incident.query.order_by(Incident.triggered_at.desc()).limit(10).all()
    )
    active_count = Incident.query.filter_by(status="active").count()
    resolved_count = Incident.query.filter_by(status="resolved").count()
    engineer_count = Engineer.query.count()
    oncall_count = Engineer.query.filter_by(is_oncall=True).count()

    return render_template(
        "dashboard.html",
        incidents=incidents,
        active_count=active_count,
        resolved_count=resolved_count,
        engineer_count=engineer_count,
        oncall_count=oncall_count,
    )

from flask import redirect, url_for, flash
from app import db

@dashboard_bp.route("/incident/<int:incident_id>/mark-answered", methods=["POST"])
@login_required
def mark_answered(incident_id):
    from flask import request
    incident = Incident.query.get_or_404(incident_id)
    if incident.status == "active":
        incident.status = "resolved"
        log = NotificationLog(
            incident_id=incident.id,
            type="info",
            status="completed",
            notes="Manually marked as answered by admin."
        )
        db.session.add(log)
        db.session.commit()
        flash(f"Incident #{incident.id} marked as answered.", "success")
    return redirect(request.referrer or url_for("dashboard.index"))
