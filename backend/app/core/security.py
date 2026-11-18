import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entities import AdminUser

# 환경변수 설정 (운영 환경에서는 .env 파일 등으로 주입)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-jwt-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120  # SAD 6.1절: 유효기간 2시간

# Bcrypt 비밀번호 해싱 컨텍스트 (자동 Salt 적용)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Swagger UI에서 Bearer 토큰 입력을 지원하는 보안 스키마
security_scheme = HTTPBearer()

def hash_password(password: str) -> str:
    """평문 비밀번호를 Salt가 적용된 Bcrypt 해시로 변환합니다."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """입력된 비밀번호와 DB의 Bcrypt 해시값을 비교 검증합니다."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(admin_id: str, account: str, expires_delta: Optional[timedelta] = None) -> str:
    """유효기간 2시간과 ADMIN 역할(role)이 포함된 JWT Access Token을 생성합니다."""
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {
        "sub": admin_id,
        "account": account,
        "role": "ADMIN",  # RBAC 검증용 역할 명시
        "exp": expire
    }
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> AdminUser:
    """
    [RBAC 인가 미들웨어]
    1. JWT 토큰 서명 및 만료 여부(HTTP 401) 검증
    2. 토큰 내 ADMIN 역할(RBAC) 보유 여부(HTTP 403) 검증
    3. DB 내 실제 관리자 존재 여부 확인
    """
    token = credentials.credentials
    
    unauthorized_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "INVALID_OR_EXPIRED_TOKEN", "message": "유효하지 않거나 만료된 토큰입니다. 재인증이 필요합니다."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    forbidden_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "INSUFFICIENT_PERMISSION", "message": "관리자(ADMIN) 권한이 없습니다."},
    )

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        admin_id: str = payload.get("sub")
        role: str = payload.get("role")
        if admin_id is None:
            raise unauthorized_exception
        if role != "ADMIN":
            raise forbidden_exception
    except JWTError:
        raise unauthorized_exception

    admin_user = db.query(AdminUser).filter(AdminUser.admin_id == admin_id).first()
    if admin_user is None:
        raise unauthorized_exception

    return admin_user