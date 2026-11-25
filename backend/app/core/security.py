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

# Environment variable configuration (inject via .env file, etc. in production)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-jwt-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120  # SAD 6.1: 2-hour expiration

# Bcrypt password hashing context (automatic salt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme supporting Bearer token input in Swagger UI
security_scheme = HTTPBearer()

def hash_password(password: str) -> str:
    """Convert a plaintext password into a salted Bcrypt hash."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against the stored Bcrypt hash in the DB."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(admin_id: str, account: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT Access Token with a 2-hour expiration and ADMIN role."""
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode = {
        "sub": admin_id,
        "account": account,
        "role": "ADMIN",  # Explicit role for RBAC verification
        "exp": expire
    }
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> AdminUser:
    """
    [RBAC Authorization Middleware]
    1. Verify JWT token signature and expiration (HTTP 401)
    2. Verify ADMIN role (RBAC) in token (HTTP 403)
    3. Verify admin user exists in DB
    """
    token = credentials.credentials
    
    unauthorized_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "INVALID_OR_EXPIRED_TOKEN", "message": "Invalid or expired token. Re-authentication is required."},
        headers={"WWW-Authenticate": "Bearer"},
    )
    forbidden_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "INSUFFICIENT_PERMISSION", "message": "Administrator (ADMIN) permission is required."},
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