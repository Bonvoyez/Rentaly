from apscheduler.schedulers.background import BackgroundScheduler
from app.database import SessionLocal
from app.services.storage_cleanup import purge_expired_passed_images

def scheduled_job():
    db = SessionLocal()
    try:
        purge_expired_passed_images(db)
    finally:
        db.close()

def start_scheduler():
    scheduler = BackgroundScheduler()
    # Run expired image cleanup daily at 03:00 AM
    scheduler.add_job(scheduled_job, "cron", hour=3, minute=0)
    scheduler.start()