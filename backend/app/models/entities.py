import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, 
    DateTime, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.enums import PrimaryVerdict, FinalStatus, AuditAction

class Equipment(Base):
    __tablename__ = "EQUIPMENT"

    equipment_id = Column(String(50), primary_key=True, index=True)
    equipment_name = Column(String(100), nullable=False)

    inspections = relationship("Inspection", back_populates="equipment")


class Inspection(Base):
    __tablename__ = "INSPECTION"

    inspection_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    equipment_id = Column(String(50), ForeignKey("EQUIPMENT.equipment_id"), nullable=False)
    recognized_serial_number = Column(String(100), nullable=True)
    primary_verdict = Column(String(20), nullable=False)  # PrimaryVerdict
    final_status = Column(String(30), nullable=False, default=FinalStatus.PENDING_REVIEW.value, index=True)
    reposition_count = Column(Integer, default=0, nullable=False)
    inspected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    total_duration_ms = Column(Integer, nullable=True)

    equipment = relationship("Equipment", back_populates="inspections")
    ai_result = relationship("AIResult", back_populates="inspection", uselist=False, cascade="all, delete-orphan")
    images = relationship("Image", back_populates="inspection", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="inspection", cascade="all, delete-orphan")


class AIResult(Base):
    __tablename__ = "AI_RESULT"

    ai_result_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inspection_id = Column(String(36), ForeignKey("INSPECTION.inspection_id"), nullable=False, unique=True)
    model_version = Column(String(50), nullable=False)
    pwr_led_status = Column(Boolean, default=False, nullable=False)
    detected_defects = Column(JSONB, nullable=True)  # Bounding box, confidence list
    blur_score = Column(Float, nullable=True)
    stabilization_ms = Column(Integer, nullable=True)
    serial_recognition_ms = Column(Integer, nullable=True)
    visual_inspection_ms = Column(Integer, nullable=True)
    inference_ms = Column(Integer, nullable=True)

    inspection = relationship("Inspection", back_populates="ai_result")


class Image(Base):
    __tablename__ = "IMAGE"

    image_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inspection_id = Column(String(36), ForeignKey("INSPECTION.inspection_id"), nullable=False)
    image_path = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    inspection = relationship("Inspection", back_populates="images")


class AdminUser(Base):
    __tablename__ = "ADMIN_USER"

    admin_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    audit_logs = relationship("AuditLog", back_populates="admin_user")


class AuditLog(Base):
    __tablename__ = "AUDIT_LOG"

    audit_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    inspection_id = Column(String(36), ForeignKey("INSPECTION.inspection_id"), nullable=False)
    admin_id = Column(String(36), ForeignKey("ADMIN_USER.admin_id"), nullable=False)
    action = Column(String(50), nullable=False)  # AuditAction
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    inspection = relationship("Inspection", back_populates="audit_logs")
    admin_user = relationship("AdminUser", back_populates="audit_logs")