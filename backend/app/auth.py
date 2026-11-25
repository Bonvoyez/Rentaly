import os
import secrets

from fastapi import Header

from app.errors import api_error

DEVICE_SECRET = os.environ["DEVICE_SECRET"]


def verify_device(x_device_secret: str | None = Header(None)):
    if not x_device_secret or not secrets.compare_digest(
        x_device_secret.encode(), DEVICE_SECRET.encode()
    ):
        raise api_error(401, "INVALID_DEVICE_SECRET", "장비 인증에 실패했습니다.")
