import os
import sys
import time
import logging
import uuid

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def seed_database(app):
    from app import db
    from app.models import User, Engineer
    from werkzeug.security import generate_password_hash

    with app.app_context():
        db.create_all()

        user = User.query.first()
        if not user:
            admin = User(
                username=app.config["ADMIN_USERNAME"],
                password_hash=generate_password_hash(app.config["ADMIN_PASSWORD"]),
            )
            db.session.add(admin)
            logger.info(f"[seed] Admin user created: {app.config['ADMIN_USERNAME']}")
        else:
            user.username = app.config["ADMIN_USERNAME"]
            user.password_hash = generate_password_hash(app.config["ADMIN_PASSWORD"])
            logger.info("[seed] Admin user synced from environment.")
        db.session.commit()

        if Engineer.query.count() == 0:
            engineers = [
                {"name": "Engineer1 Nebulynx",  "phone": "+639178354657", "email": "engineer1@nebulynx.com", "pos": 1},
                {"name": "Engineer2 Nebulynx2", "phone": "+639606075462", "email": "engineer2@nebulynx.com", "pos": 2},
                {"name": "Engineer 3",           "phone": "+639166860971", "email": "engineer3@nebulynx.com", "pos": 3},
                {"name": "Engineer 4",           "phone": "+639276423773", "email": "engineer4@nebulynx.com", "pos": 4},
            ]
            for e in engineers:
                eng = Engineer(
                    name=e["name"],
                    phone=e["phone"],
                    email=e["email"],
                    queue_position=e["pos"],
                    is_oncall=True,
                    access_token=str(uuid.uuid4()),
                )
                db.session.add(eng)
            db.session.commit()
            logger.info("[seed] 4 engineers seeded.")


def setup_ngrok(app):
    """Only runs on local dev. Skipped automatically on Render (production)."""
    from app.services.ngrok_helper import fetch_ngrok_url, set_ngrok_url, push_to_twilio

    logger.info("[ngrok] Looking for active tunnel...")
    for attempt in range(6):
        url = fetch_ngrok_url()
        if url:
            set_ngrok_url(url)
            push_to_twilio(url, app)
            logger.info(f"[ngrok] Tunnel active: {url}")
            return url
        if attempt < 5:
            logger.info(f"[ngrok] Not found yet, retrying in 2s... ({attempt+1}/6)")
            time.sleep(2)

    logger.warning("[ngrok] No ngrok tunnel found. Start ngrok with: ngrok http 5001")
    logger.warning("[ngrok] Twilio webhooks NOT updated. Calls will fail without ngrok.")
    return None


def create_and_start_app():
    """Called by Gunicorn (Render) and by __main__ (local dev)."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from app import create_app

    app = create_app()
    seed_database(app)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.start()

    # Wire orchestrator to scheduler
    from app.services.orchestrator import init_orchestrator
    init_orchestrator(app, scheduler)

    # Start email monitor
    from app.services.email_monitor import start_scheduler as start_email
    start_email(app, scheduler)

    # Auto-sync on-call status from shifts every minute
    def auto_sync_oncall_status():
        """Background job: auto-enable/disable is_oncall based on active approved shifts."""
        from datetime import datetime as _dt, timezone as _tz
        from zoneinfo import ZoneInfo
        from app.models import Engineer, OncallSchedule
        from app import db
        with app.app_context():
            try:
                # Derive UTC now via the configured app timezone — consistent with _parse_dt
                tz_str = app.config.get("APP_TIMEZONE", "Asia/Manila")
                local_tz = ZoneInfo(tz_str)
                now_local = _dt.now(local_tz)
                now_utc = now_local.astimezone(_tz.utc).replace(tzinfo=None)

                active_shifts = OncallSchedule.query.filter(
                    OncallSchedule.is_approved == True,
                    OncallSchedule.shift_start <= now_utc,
                    OncallSchedule.shift_end >= now_utc,
                ).all()
                active_ids = {s.engineer_id for s in active_shifts}
                engineers = Engineer.query.all()
                changed = 0
                for eng in engineers:
                    desired = eng.id in active_ids
                    if eng.is_oncall != desired:
                        eng.is_oncall = desired
                        changed += 1
                if changed:
                    db.session.commit()
                    logger.info(f"[shift-sync] Auto-toggled is_oncall for {changed} engineer(s) at {now_local.strftime('%Y-%m-%d %H:%M')} {tz_str}.")
            except Exception as e:
                db.session.rollback()
                logger.error(f"[shift-sync] Error during auto oncall sync: {e}")

    scheduler.add_job(
        auto_sync_oncall_status,
        "interval",
        minutes=1,
        id="auto_sync_oncall",
        replace_existing=True,
    )
    logger.info("[run] Auto oncall-shift sync job registered (every 1 min).")

    # Skip ngrok on Render — BASE_URL env var is used instead
    is_render = os.environ.get("RENDER", "").lower() in ("true", "1", "yes")
    if not is_render:
        setup_ngrok(app)
    else:
        logger.info("[run] Running on Render — ngrok skipped. Using BASE_URL for webhooks.")

    return app


# Gunicorn entry point (used by Render via Procfile: gunicorn run:application)
application = create_and_start_app()


if __name__ == "__main__":
    if "--init-db" in sys.argv:
        from app import create_app
        app = create_app()
        seed_database(app)
        logger.info("[setup] Database initialized. Exiting.")
        sys.exit(0)

    port = int(os.environ.get("PORT", 5001))
    logger.info(f"[run] Starting Flask on http://0.0.0.0:{port}")
    application.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
