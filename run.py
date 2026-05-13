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

        if not User.query.first():
            admin = User(
                username=app.config["ADMIN_USERNAME"],
                password_hash=generate_password_hash(app.config["ADMIN_PASSWORD"]),
            )
            db.session.add(admin)
            db.session.commit()
            logger.info(f"[seed] Admin user created: {app.config['ADMIN_USERNAME']}")

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

    logger.warning("[ngrok] No ngrok tunnel found. Start ngrok with: ngrok http 5000")
    logger.warning("[ngrok] Twilio webhooks NOT updated. Calls will fail without ngrok.")
    return None


if __name__ == "__main__":
    from apscheduler.schedulers.background import BackgroundScheduler
    from app import create_app

    app = create_app()

    if "--init-db" in sys.argv:
        seed_database(app)
        logger.info("[setup] Database initialized. Exiting.")
        sys.exit(0)

    seed_database(app)

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.start()

    # Wire orchestrator to scheduler
    from app.services.orchestrator import init_orchestrator
    init_orchestrator(app, scheduler)

    # Start email monitor
    from app.services.email_monitor import start_scheduler as start_email
    start_email(app, scheduler)

    # Setup ngrok + update Twilio webhooks
    setup_ngrok(app)

    logger.info("[run] Starting Flask on http://0.0.0.0:5000")
    app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)
