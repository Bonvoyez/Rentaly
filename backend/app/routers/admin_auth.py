from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import AdminUser
from app.schemas import AdminLoginRequest, TokenResponse, AdminUserResponse
from app.core.security import verify_password, create_access_token, get_current_admin

router = APIRouter(prefix="/api/v1/admin/auth", tags=["Admin Auth"])


@router.post("/login", response_model=TokenResponse, summary="Admin login and JWT issuance")
def login_admin(request: AdminLoginRequest, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter(AdminUser.account == request.account).first()
    if not admin or not verify_password(request.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTH_FAILED", "message": "Invalid account name or password."}
        )
    access_token = create_access_token(admin_id=admin.admin_id, account=admin.account)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=AdminUserResponse, summary="Verify currently logged-in admin info")
def get_me(current_admin: AdminUser = Depends(get_current_admin)):
    return current_admin