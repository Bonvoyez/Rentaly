from enum import Enum


class PrimaryVerdict(str, Enum):
    """Edge(Raspberry Pi)에서 수행한 1차 판정 결과"""
    PASS = "PASS"
    REPOSITION = "REPOSITION"
    FAIL = "FAIL"
    ERROR = "ERROR"


class FinalStatus(str, Enum):
    """DB에 기록되는 최종 검사 상태"""
    PASSED = "PASSED"
    REPOSITION_LOG = "REPOSITION_LOG"
    MANUAL_RETURN = "MANUAL_RETURN"
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFIRMED_PASS = "CONFIRMED_PASS"
    CONFIRMED_REJECT = "CONFIRMED_REJECT"
    RETROACTIVE_REJECT = "RETROACTIVE_REJECT"
    ERROR = "ERROR"


class AuditAction(str, Enum):
    """관리자 감사 로그(AUDIT_LOG) 작업 유형"""
    CONFIRM_PASS = "CONFIRM_PASS"
    CONFIRM_REJECT = "CONFIRM_REJECT"
    RETROACTIVE_REJECT = "RETROACTIVE_REJECT"