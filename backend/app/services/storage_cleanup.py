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
    PASSED 상태로 30일이 지난 검사 건의 실제 이미지 파일 및 DB 레코드 정리
    PENDING_REVIEW, CONFIRMED_REJECT 등은 영구 보존 정책 유지
    """
    threshold_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    
    # 30일이 지난 PASSED 상태의 검사 건 조회
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
            # 실제 영속 볼륨 파일 삭제
            if os.path.exists(img.image_path):
                try:
                    os.remove(img.image_path)
                    logger.info(f"Deleted expired image file: {img.image_path}")
                except OSError as e:
                    logger.error(f"Failed to delete file {img.image_path}: {e}")
            
            # DB 레코드 제거
            db.delete(img)
            deleted_count += 1

    db.commit()
    logger.info(f"Purge complete: {deleted_count} image records/files deleted.")
    return deleted_count