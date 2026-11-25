from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.entities import Inspection, Image, AuditLog, AdminUser
from app.models.enums import FinalStatus, AuditAction
from app.schemas import (
    InspectionSummaryResponse,
    InspectionDetailResponse,
    ConfirmVerdictRequest,
    RetroactiveRejectRequest,
)
from app.core.security import get_current_admin

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Inspections"])

STORAGE_ROOT = Path("/app/storage")


def resolve_image_path(stored_path: str) -> Path:
    """Supports both relative paths ('images/xxx.jpg') and absolute paths ('/app/storage/images/xxx.jpg')."""
    p = Path(stored_path)
    if p.is_absolute() and p.exists():
        return p
    candidate = STORAGE_ROOT / stored_path
    if candidate.exists():
        return candidate
    return Path("/app/storage/images") / p.name


@router.get("/inspections/pending", response_model=List[InspectionSummaryResponse], summary="List PENDING_REVIEW inspections in review queue")
def get_pending_inspections(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    return (
        db.query(Inspection)
        .filter(Inspection.final_status == FinalStatus.PENDING_REVIEW.value)
        .order_by(Inspection.inspected_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/inspections", response_model=List[InspectionSummaryResponse], summary="List all inspection history with filters")
def list_inspections(
    final_status: Optional[str] = Query(None),
    equipment_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    query = db.query(Inspection)
    if final_status:
        query = query.filter(Inspection.final_status == final_status)
    if equipment_id:
        query = query.filter(Inspection.equipment_id == equipment_id)
    return query.order_by(Inspection.inspected_at.desc()).offset(skip).limit(limit).all()


@router.get("/inspections/{inspection_id}", response_model=InspectionDetailResponse, summary="Get single inspection details")
def get_inspection_detail(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    inspection = (
        db.query(Inspection)
        .options(
            joinedload(Inspection.ai_result),
            joinedload(Inspection.images),
            joinedload(Inspection.audit_logs)
        )
        .filter(Inspection.inspection_id == inspection_id)
        .first()
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "INSPECTION_NOT_FOUND", "message": "Inspection record not found."}
        )
    return inspection


@router.post("/inspections/{inspection_id}/confirm", response_model=InspectionDetailResponse, summary="Confirm admin manual verdict")
def confirm_inspection_verdict(
    inspection_id: str,
    request: ConfirmVerdictRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    inspection = db.query(Inspection).filter(Inspection.inspection_id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail={"code": "INSPECTION_NOT_FOUND", "message": "Inspection record not found."})

    if inspection.final_status != FinalStatus.PENDING_REVIEW.value:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE_TRANSITION", "message": "Only PENDING_REVIEW inspections can be confirmed."})

    if request.decision not in (FinalStatus.CONFIRMED_PASS.value, FinalStatus.CONFIRMED_REJECT.value):
        raise HTTPException(status_code=422, detail={"code": "INVALID_DECISION_VALUE", "message": "Decision must be CONFIRMED_PASS or CONFIRMED_REJECT."})

    inspection.final_status = request.decision
    action = AuditAction.CONFIRM_PASS.value if request.decision == FinalStatus.CONFIRMED_PASS.value else AuditAction.CONFIRM_REJECT.value

    db.add(AuditLog(
        inspection_id=inspection.inspection_id,
        admin_id=current_admin.admin_id,
        action=action,
        reason=request.reason
    ))
    db.commit()
    db.refresh(inspection)
    return inspection


@router.post("/inspections/{inspection_id}/retroactive-reject", response_model=InspectionDetailResponse, summary="Retroactively reject a passed inspection")
def retroactive_reject_inspection(
    inspection_id: str,
    request: RetroactiveRejectRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    inspection = db.query(Inspection).filter(Inspection.inspection_id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail={"code": "INSPECTION_NOT_FOUND", "message": "Inspection record not found."})

    if inspection.final_status != FinalStatus.PASSED.value:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE_TRANSITION", "message": "Only PASSED inspections can be retroactively rejected."})

    if inspection.inspected_at < datetime.utcnow() - timedelta(days=30):
        raise HTTPException(status_code=400, detail={"code": "RETENTION_PERIOD_EXPIRED", "message": "Cannot retroactively reject an inspection older than 30 days."})

    inspection.final_status = FinalStatus.RETROACTIVE_REJECT.value
    db.add(AuditLog(
        inspection_id=inspection.inspection_id,
        admin_id=current_admin.admin_id,
        action=AuditAction.RETROACTIVE_REJECT.value,
        reason=request.reason
    ))
    db.commit()
    db.refresh(inspection)
    return inspection


@router.get("/images/{image_id}", summary="Serve protected inspection image file for admins")
def get_protected_image(
    image_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    image_record = db.query(Image).filter(Image.image_id == image_id).first()
    if not image_record:
        raise HTTPException(status_code=404, detail={"code": "IMAGE_NOT_FOUND", "message": "Image record not found."})

    real_path = resolve_image_path(image_record.image_path)
    if not real_path.exists():
        raise HTTPException(status_code=404, detail={"code": "IMAGE_FILE_MISSING", "message": "Image file does not exist on the server volume."})

    return FileResponse(str(real_path), media_type="image/jpeg")