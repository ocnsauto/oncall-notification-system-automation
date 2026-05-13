import uuid
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from werkzeug.security import generate_password_hash
from app import db
from app.models import Engineer

engineers_bp = Blueprint("engineers", __name__, url_prefix="/engineers")


@engineers_bp.route("/")
@login_required
def list_engineers():
    engineers = Engineer.query.order_by(Engineer.queue_position).all()
    return render_template("engineers/list.html", engineers=engineers)


@engineers_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_engineer():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()
        queue_position = int(request.form.get("queue_position", 1))
        is_oncall = request.form.get("is_oncall") == "on"

        if not name or not phone or not email:
            flash("Name, phone, and email are required.", "error")
            return render_template("engineers/form.html", engineer=None)

        engineer = Engineer(
            name=name,
            phone=phone,
            email=email,
            queue_position=queue_position,
            is_oncall=is_oncall,
            access_token=str(uuid.uuid4()),
        )
        db.session.add(engineer)
        db.session.commit()
        flash(f"Engineer '{name}' added.", "success")
        return redirect(url_for("engineers.list_engineers"))

    max_pos = db.session.query(db.func.max(Engineer.queue_position)).scalar() or 0
    return render_template("engineers/form.html", engineer=None, next_position=max_pos + 1)


@engineers_bp.route("/<int:engineer_id>/edit", methods=["GET", "POST"])
@login_required
def edit_engineer(engineer_id):
    engineer = Engineer.query.get_or_404(engineer_id)
    if request.method == "POST":
        engineer.name = request.form.get("name", "").strip()
        engineer.phone = request.form.get("phone", "").strip()
        engineer.email = request.form.get("email", "").strip()
        engineer.queue_position = int(request.form.get("queue_position", 1))
        engineer.is_oncall = request.form.get("is_oncall") == "on"
        db.session.commit()
        flash(f"Engineer '{engineer.name}' updated.", "success")
        return redirect(url_for("engineers.list_engineers"))
    return render_template("engineers/form.html", engineer=engineer)


@engineers_bp.route("/<int:engineer_id>/delete", methods=["POST"])
@login_required
def delete_engineer(engineer_id):
    engineer = Engineer.query.get_or_404(engineer_id)
    name = engineer.name
    db.session.delete(engineer)
    db.session.commit()
    flash(f"Engineer '{name}' deleted.", "info")
    return redirect(url_for("engineers.list_engineers"))


@engineers_bp.route("/<int:engineer_id>/toggle-oncall", methods=["POST"])
@login_required
def toggle_oncall(engineer_id):
    engineer = Engineer.query.get_or_404(engineer_id)
    engineer.is_oncall = not engineer.is_oncall
    db.session.commit()
    return jsonify({"is_oncall": engineer.is_oncall})


@engineers_bp.route("/<int:engineer_id>/regenerate-token", methods=["POST"])
@login_required
def regenerate_token(engineer_id):
    engineer = Engineer.query.get_or_404(engineer_id)
    engineer.access_token = str(uuid.uuid4())
    db.session.commit()
    flash(f"Token regenerated for '{engineer.name}'. Old link is now invalid.", "info")
    return redirect(url_for("engineers.list_engineers"))


@engineers_bp.route("/<int:engineer_id>/move", methods=["POST"])
@login_required
def move_engineer(engineer_id):
    direction = request.form.get("direction")
    engineer = Engineer.query.get_or_404(engineer_id)

    if direction == "up" and engineer.queue_position > 1:
        swap = Engineer.query.filter_by(queue_position=engineer.queue_position - 1).first()
        if swap:
            swap.queue_position, engineer.queue_position = engineer.queue_position, swap.queue_position
            db.session.commit()
    elif direction == "down":
        swap = Engineer.query.filter_by(queue_position=engineer.queue_position + 1).first()
        if swap:
            swap.queue_position, engineer.queue_position = engineer.queue_position, swap.queue_position
            db.session.commit()

    return redirect(url_for("engineers.list_engineers"))
