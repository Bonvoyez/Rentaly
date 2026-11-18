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
    """상대경로('images/xxx.jpg')와 절대경로('/app/storage/images/xxx.jpg')를 모두 호환합니다."""
    p = Path(stored_path)
    if p.is_absolute() and p.exists():
        return p
    candidate = STORAGE_ROOT / stored_path
    if candidate.exists():
        return candidate
    return Path("/app/storage/images") / p.name


@router.get("/inspections/pending", response_model=List[InspectionSummaryResponse], summary="PENDING_REVIEW 검토 대기열 목록 조회")
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


@router.get("/inspections", response_model=List[InspectionSummaryResponse], summary="전체 검사 이력 조건별 조회")
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


@router.get("/inspections/{inspection_id}", response_model=InspectionDetailResponse, summary="검사 단건 상세 조회")
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
            detail={"code": "INSPECTION_NOT_FOUND", "message": "해당 검사 기록을 찾을 수 없습니다."}
        )
    return inspection


@router.post("/inspections/{inspection_id}/confirm", response_model=InspectionDetailResponse, summary="관리자 수동 판정 확정")
def confirm_inspection_verdict(
    inspection_id: str,
    request: ConfirmVerdictRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    inspection = db.query(Inspection).filter(Inspection.inspection_id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail={"code": "INSPECTION_NOT_FOUND", "message": "해당 검사 기록을 찾을 수 없습니다."})

    if inspection.final_status != FinalStatus.PENDING_REVIEW.value:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE_TRANSITION", "message": "PENDING_REVIEW 상태만 확정할 수 있습니다."})

    if request.decision not in (FinalStatus.CONFIRMED_PASS.value, FinalStatus.CONFIRMED_REJECT.value):
        raise HTTPException(status_code=422, detail={"code": "INVALID_DECISION_VALUE", "message": "CONFIRMED_PASS 또는 CONFIRMED_REJECT여야 합니다."})

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


@router.post("/inspections/{inspection_id}/retroactive-reject", response_model=InspectionDetailResponse, summary="사후 반려 처리")
def retroactive_reject_inspection(
    inspection_id: str,
    request: RetroactiveRejectRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    inspection = db.query(Inspection).filter(Inspection.inspection_id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail={"code": "INSPECTION_NOT_FOUND", "message": "해당 검사 기록을 찾을 수 없습니다."})

    if inspection.final_status != FinalStatus.PASSED.value:
        raise HTTPException(status_code=400, detail={"code": "INVALID_STATE_TRANSITION", "message": "PASSED 상태인 건만 사후 반려가 가능합니다."})

    if inspection.inspected_at < datetime.utcnow() - timedelta(days=30):
        raise HTTPException(status_code=400, detail={"code": "RETENTION_PERIOD_EXPIRED", "message": "검사 후 30일이 경과하여 사후 반려할 수 없습니다."})

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


@router.get("/images/{image_id}", summary="관리자 전용 보호된 검사 이미지 파일 서빙")
def get_protected_image(
    image_id: str,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    image_record = db.query(Image).filter(Image.image_id == image_id).first()
    if not image_record:
        raise HTTPException(status_code=404, detail={"code": "IMAGE_NOT_FOUND", "message": "해당 이미지 레코드를 찾을 수 없습니다."})

    real_path = resolve_image_path(image_record.image_path)
    if not real_path.exists():
        raise HTTPException(status_code=404, detail={"code": "IMAGE_FILE_MISSING", "message": "서버 볼륨에 실제 이미지 파일이 존재하지 않습니다."})

    return FileResponse(str(real_path), media_type="image/jpeg")