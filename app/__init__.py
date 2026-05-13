import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

# Project root is one level above this file (app/)
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def create_app():
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=os.path.join(_ROOT, "templates"),
        static_folder=os.path.join(_ROOT, "static"),
    )

    from app.config import Config
    app.config.from_object(Config)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to access the admin panel."
    login_manager.login_message_category = "warning"

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Add custom template filter for local time
    from zoneinfo import ZoneInfo
    import datetime

    @app.template_filter('local_time')
    def local_time_filter(dt):
        if not dt:
            return ""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        tz = ZoneInfo(app.config.get("APP_TIMEZONE", "Asia/Manila"))
        return dt.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S')

    # Register blueprints
    from app.auth.routes import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.engineers import engineers_bp
    from app.routes.schedules import schedules_bp
    from app.routes.logs import logs_bp
    from app.routes.portal import portal_bp
    from app.routes.webhooks import webhooks_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(engineers_bp)
    app.register_blueprint(schedules_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(webhooks_bp)

    return app
