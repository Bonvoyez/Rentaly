from datetime import datetime, timezone
from typing import Annotated, Any, List, Literal, Optional
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

# DB stores UTC without timezone, so attach UTC tzinfo in responses
UTCDateTime = Annotated[datetime, AfterValidator(lambda v: v if v.tzinfo else v.replace(tzinfo=timezone.utc))]


# =============================================================================
# Schemas for receiving Edge inspection results
# =============================================================================
class Defect(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    class_name: str = Field(alias="class")
    confidence: float | None = Field(default=None, ge=0, le=1)
    bbox: list[float] | None = Field(default=None, min_length=4, max_length=4)


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

    @model_validator(mode="before")
    @classmethod
    def accept_edge_format(cls, data):
        # Normalize inspector (web_inspector.py) payload to API_CONTRACT format
        if not isinstance(data, dict):
            return data
        data = dict(data)

        if "blur_score" in data:
            metrics = dict(data.get("metrics") or {})
            metrics.setdefault("blur_score", data["blur_score"])
            data["metrics"] = metrics

        extra = data.get("metadata")
        if "detected_defects" not in data and isinstance(extra, dict):
            defect = extra.get("defect_type")
            if defect and defect != "NONE":
                item = {"class": defect}
                conf = extra.get("confidence")
                if isinstance(conf, (int, float)) and 0 <= conf <= 1:
                    item["confidence"] = conf
                data["detected_defects"] = [item]

        return data


# =============================================================================
# Admin Auth schemas
# =============================================================================
class AdminLoginRequest(BaseModel):
    account: str = Field(..., description="Admin login account ID", examples=["admin"])
    password: str = Field(..., description="Admin password", examples=["admin1234!"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 7200


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    admin_id: str
    account: str
    role: str = "ADMIN"
    created_at: UTCDateTime


# =============================================================================
# Admin Dashboard (Admin Inspections) schemas
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
    created_at: UTCDateTime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: str
    admin_id: str
    action: str
    reason: Optional[str] = None
    created_at: UTCDateTime


class InspectionSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inspection_id: str
    equipment_id: str
    recognized_serial_number: Optional[str] = None
    primary_verdict: str
    final_status: str
    reposition_count: int
    inspected_at: UTCDateTime
    total_duration_ms: Optional[int] = None


class InspectionDetailResponse(InspectionSummaryResponse):
    ai_result: Optional[AIResultResponse] = None
    images: List[ImageMetaResponse] = []
    audit_logs: List[AuditLogResponse] = []


class ConfirmVerdictRequest(BaseModel):
    decision: str = Field(
        ...,
        description="Final verdict value ('CONFIRMED_PASS' or 'CONFIRMED_REJECT')",
        examples=["CONFIRMED_PASS"]
    )
    reason: Optional[str] = Field(None, description="Reason for approval/rejection", examples=["Verified no physical defects"])


class RetroactiveRejectRequest(BaseModel):
    reason: str = Field(..., description="Reason for retroactive rejection (required)", examples=["Port damage discovered later due to AI miss"])