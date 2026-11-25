import os
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.entities import Inspection, Image
from app.models.enums import FinalStatus

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30
IMAGE_STORAGE_PATH = os.getenv("IMAGE_STORAGE_PATH", "/app/storage/images")

def purge_expired_passed_images(db: Session):
    """
    Purge image files and DB records for PASSED inspections older than 30 days.
    PENDING_REVIEW, CONFIRMED_REJECT, etc. are retained permanently.
    """
    threshold_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    
    # Query PASSED inspections older than 30 days
    expired_inspections = (
        db.query(Inspection)
        .filter(
            Inspection.final_status == FinalStatus.PASSED.value,
            Inspection.inspected_at < threshold_date
        )
        .all()
    )

    deleted_count = 0
    for insp in expired_inspections:
        images = db.query(Image).filter(Image.inspection_id == insp.inspection_id).all()
        for img in images:
            # Delete actual file on persistent volume
            if os.path.exists(img.image_path):
                try:
                    os.remove(img.image_path)
                    logger.info(f"Deleted expired image file: {img.image_path}")
                except OSError as e:
                    logger.error(f"Failed to delete file {img.image_path}: {e}")
            
            # Remove DB record
            db.delete(img)
            deleted_count += 1

    db.commit()
    logger.info(f"Purge complete: {deleted_count} image records/files deleted.")
    return deleted_count