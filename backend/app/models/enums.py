from enum import Enum


class PrimaryVerdict(str, Enum):
    """Primary verdict determined on the Edge (Raspberry Pi)"""
    PASS = "PASS"
    REPOSITION = "REPOSITION"
    FAIL = "FAIL"
    ERROR = "ERROR"


class FinalStatus(str, Enum):
    """Final inspection status recorded in the DB"""
    PASSED = "PASSED"
    REPOSITION_LOG = "REPOSITION_LOG"
    MANUAL_RETURN = "MANUAL_RETURN"
    PENDING_REVIEW = "PENDING_REVIEW"
    CONFIRMED_PASS = "CONFIRMED_PASS"
    CONFIRMED_REJECT = "CONFIRMED_REJECT"
    RETROACTIVE_REJECT = "RETROACTIVE_REJECT"
    ERROR = "ERROR"


class AuditAction(str, Enum):
    """Admin audit log (AUDIT_LOG) action types"""
    CONFIRM_PASS = "CONFIRM_PASS"
    CONFIRM_REJECT = "CONFIRM_REJECT"
    RETROACTIVE_REJECT = "RETROACTIVE_REJECT"