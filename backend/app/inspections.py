import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import verify_device
from app.errors import api_error
from app.schemas import InspectionMetadata
from app.storage import save_image

from app.database import get_db
from app.models.entities import Equipment, Inspection, AIResult, Image
from app.models.enums import PrimaryVerdict, FinalStatus

router = APIRouter(prefix="/api/v1", tags=["inspections"])
logger = logging.getLogger("uvicorn.error")

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg"}


def determine_final_status(primary_verdict: str, reposition_count: int = 0) -> str:
    """1차 판정(primary_verdict)에 따른 초기 final_status 결정"""
    if primary_verdict == PrimaryVerdict.PASS.value:
        return FinalStatus.PASSED.value
    if primary_verdict == PrimaryVerdict.FAIL.value:
        return FinalStatus.PENDING_REVIEW.value
    if primary_verdict == PrimaryVerdict.ERROR.value:
        return FinalStatus.ERROR.value
    if primary_verdict == PrimaryVerdict.REPOSITION.value:
        if reposition_count > 3:
            return FinalStatus.MANUAL_RETURN.value
        return FinalStatus.REPOSITION_LOG.value
    return FinalStatus.ERROR.value


@router.post("/inspections", status_code=201, dependencies=[Depends(verify_device)])
async def receive_inspection(
    metadata: str = Form(...),
    image: UploadFile = File(...),
    x_inspection_id: str | None = Header(None),
    db: Session = Depends(get_db),
):
    try:
        meta = InspectionMetadata.model_validate_json(metadata)
    except ValidationError as e:
        err = e.errors()[0]
        field = ".".join(str(x) for x in err["loc"]) or "metadata"
        raise api_error(422, "INVALID_METADATA", f"{field}: {err['msg']}")

    if x_inspection_id:
        try:
            header_id = UUID(x_inspection_id)
        except ValueError:
            header_id = None
        if header_id != meta.inspection_id:
            raise api_error(400, "INSPECTION_ID_MISMATCH", "X-Inspection-ID와 metadata의 inspection_id가 다릅니다.")

    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise api_error(400, "INVALID_IMAGE", "jpg 이미지만 업로드할 수 있습니다.")

    content = await image.read()
    if not content:
        raise api_error(400, "INVALID_IMAGE", "이미지가 비어 있습니다.")
    if len(content) > MAX_IMAGE_BYTES:
        raise api_error(413, "IMAGE_TOO_LARGE", "이미지는 10MB 이하만 업로드할 수 있습니다.")

    inspection_id_str = str(meta.inspection_id)

    # 1. 멱등성 처리 (중복 전송 시 기존 결과 반환)
    existing = db.query(Inspection).filter(Inspection.inspection_id == inspection_id_str).first()
    if existing:
        logger.info("duplicate inspection ignored: id=%s", inspection_id_str)
        return {
            "status": "SUCCESS",
            "inspection_id": existing.inspection_id,
            "final_status": existing.final_status,
        }

    # 2. 이미지 파일 저장
    image_path = save_image(meta.inspection_id, content)

    # 3. 초기 최종 상태(final_status) 계산
    final_status = determine_final_status(meta.primary_verdict, meta.reposition_count)

    # 4. EQUIPMENT 테이블에 장비 미등록 시 자동 생성
    equipment = db.query(Equipment).filter(Equipment.equipment_id == meta.equipment_id).first()
    if not equipment:
        equipment = Equipment(
            equipment_id=meta.equipment_id,
            equipment_name=f"Raspberry Pi ({meta.equipment_id})"
        )
        db.add(equipment)
        db.flush()

    # 5. INSPECTION 레코드 저장
    new_inspection = Inspection(
        inspection_id=inspection_id_str,
        equipment_id=meta.equipment_id,
        recognized_serial_number=meta.recognized_serial_number,
        primary_verdict=meta.primary_verdict,
        final_status=final_status,
        reposition_count=meta.reposition_count,
        inspected_at=datetime.utcnow(),
        total_duration_ms=meta.metrics.total_duration_ms,
    )
    db.add(new_inspection)

    # 6. AI_RESULT 레코드 저장
    defects_json = [d.model_dump(by_alias=True) for d in meta.detected_defects]
    new_ai_result = AIResult(
        inspection_id=inspection_id_str,
        model_version="yolov8n-v1.0",
        pwr_led_status=meta.pwr_led_status,
        detected_defects=defects_json,
        blur_score=meta.metrics.blur_score,
        stabilization_ms=meta.metrics.stabilization_ms,
        serial_recognition_ms=meta.metrics.serial_recognition_ms,
        visual_inspection_ms=meta.metrics.visual_inspection_ms,
        inference_ms=meta.metrics.inference_ms,
    )
    db.add(new_ai_result)

    # 7. IMAGE 메타데이터 레코드 저장
    new_image = Image(
        inspection_id=inspection_id_str,
        image_path=image_path,
        file_size_bytes=len(content),
    )
    db.add(new_image)

    db.commit()

    logger.info(
        "inspection saved: id=%s verdict=%s final_status=%s image=%s (%d bytes)",
        inspection_id_str,
        meta.primary_verdict,
        final_status,
        image_path,
        len(content),
    )

    return {
        "status": "SUCCESS",
        "inspection_id": inspection_id_str,
        "final_status": final_status,
    }