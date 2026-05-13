import uuid
from datetime import datetime
from flask_login import UserMixin
from app import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)


class Engineer(db.Model):
    __tablename__ = "engineers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    queue_position = db.Column(db.Integer, nullable=False, default=1)
    is_oncall = db.Column(db.Boolean, default=True, nullable=False)
    access_token = db.Column(
        db.String(36), unique=True, nullable=False,
        default=lambda: str(uuid.uuid4())
    )

    schedules = db.relationship(
        "OncallSchedule", backref="engineer", lazy=True, cascade="all, delete-orphan"
    )
    change_requests = db.relationship(
        "ScheduleChangeRequest", backref="engineer", lazy=True, cascade="all, delete-orphan"
    )
    notification_logs = db.relationship(
        "NotificationLog", backref="engineer", lazy=True
    )


class OncallSchedule(db.Model):
    __tablename__ = "oncall_schedules"
    id = db.Column(db.Integer, primary_key=True)
    engineer_id = db.Column(db.Integer, db.ForeignKey("engineers.id"), nullable=False)
    shift_start = db.Column(db.DateTime, nullable=False)
    shift_end = db.Column(db.DateTime, nullable=False)
    is_approved = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ScheduleChangeRequest(db.Model):
    __tablename__ = "schedule_change_requests"
    id = db.Column(db.Integer, primary_key=True)
    engineer_id = db.Column(db.Integer, db.ForeignKey("engineers.id"), nullable=False)
    requested_start = db.Column(db.DateTime, nullable=False)
    requested_end = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)


class Incident(db.Model):
    __tablename__ = "incidents"
    id = db.Column(db.Integer, primary_key=True)
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    email_subject = db.Column(db.String(500), nullable=False)
    email_body_raw = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default="active", nullable=False)
    message_id = db.Column(db.String(500), unique=True, nullable=False)

    notification_logs = db.relationship(
        "NotificationLog", backref="incident", lazy=True, cascade="all, delete-orphan"
    )

    @property
    def body_snippet(self):
        if self.email_body_raw:
            return self.email_body_raw[:80].strip()
        return ""


class NotificationLog(db.Model):
    __tablename__ = "notification_logs"
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id"), nullable=False)
    engineer_id = db.Column(db.Integer, db.ForeignKey("engineers.id"), nullable=True)
    type = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(30), nullable=True)
    twilio_sid = db.Column(db.String(64), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
