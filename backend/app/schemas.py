from datetime import datetime
from typing import Any, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Edge 검사 결과 수신용 스키마
# =============================================================================
class Defect(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    class_name: str = Field(alias="class")
    confidence: float = Field(ge=0, le=1)
    bbox: list[float] = Field(min_length=4, max_length=4)


class Metrics(BaseModel):
    blur_score: float | None = None
    stabilization_ms: int | None = None
    serial_recognition_ms: int | None = None
    visual_inspection_ms: int | None = None
    inference_ms: int | None = None
    total_duration_ms: int | None = None


class InspectionMetadata(BaseModel):
    inspection_id: UUID
    equipment_id: str = Field(min_length=1)
    recognized_serial_number: str | None = None
    primary_verdict: Literal["PASS", "REPOSITION", "FAIL", "ERROR"]
    reposition_count: int = Field(default=0, ge=0, le=3)
    pwr_led_status: bool
    detected_defects: list[Defect] = []
    metrics: Metrics = Metrics()


# =============================================================================
# 관리자 인증(Auth) 스키마
# =============================================================================
class AdminLoginRequest(BaseModel):
    account: str = Field(..., description="관리자 로그인 계정 ID", examples=["admin"])
    password: str = Field(..., description="관리자 비밀번호", examples=["admin1234!"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 7200


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    admin_id: str
    account: str
    role: str = "ADMIN"
    created_at: datetime


# =============================================================================
# 관리자 대시보드(Admin Inspections) 스키마
# =============================================================================
class AIResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ai_result_id: str
    model_version: str
    pwr_led_status: bool
    detected_defects: Optional[Any] = None
    blur_score: Optional[float] = None
    stabilization_ms: Optional[int] = None
    serial_recognition_ms: Optional[int] = None
    visual_inspection_ms: Optional[int] = None
    inference_ms: Optional[int] = None


class ImageMetaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    image_id: str
    file_size_bytes: int
    created_at: datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: str
    admin_id: str
    action: str
    reason: Optional[str] = None
    created_at: datetime


class InspectionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inspection_id: str
    equipment_id: str
    recognized_serial_number: Optional[str] = None
    primary_verdict: str
    final_status: str
    reposition_count: int
    inspected_at: datetime
    total_duration_ms: Optional[int] = None


class InspectionDetailResponse(InspectionSummaryResponse):
    ai_result: Optional[AIResultResponse] = None
    images: List[ImageMetaResponse] = []
    audit_logs: List[AuditLogResponse] = []


class ConfirmVerdictRequest(BaseModel):
    decision: str = Field(
        ...,
        description="확정 판정 값 ('CONFIRMED_PASS' 또는 'CONFIRMED_REJECT')",
        examples=["CONFIRMED_PASS"]
    )
    reason: Optional[str] = Field(None, description="승인/반려 판정 사유", examples=["외관 이상 없음 확인"])


class RetroactiveRejectRequest(BaseModel):
    reason: str = Field(..., description="사후 반려 사유 (필수)", examples=["AI 미탐으로 인한 포트 파손 사후 발견"])