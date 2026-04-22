import jwt
from datetime import datetime, timedelta
from fastapi import Header, HTTPException, Depends, status, Cookie
from app.config import settings
import secrets

# JWT Configuration
SECRET_KEY = settings.jwt_secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 1 day (1440 minutes)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    csrf_token = secrets.token_hex(16)
    to_encode["csrf_token"] = csrf_token
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt, csrf_token


def _decode_token(token):
    """Try to decode a single JWT token. Returns payload or None."""
    if not token or token in ("undefined", "null"):
        return None
    if token.count('.') != 2:
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None


def get_jwt_payload(
    staff_token: str = Cookie(alias="jwt", default=None),
    customer_token: str = Cookie(alias="jwt_customer", default=None),
):
    # Try staff token first, then customer token
    for token in [staff_token, customer_token]:
        payload = _decode_token(token)
        if payload:
            return payload

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid authentication token"
    )


def verify_csrf(
    x_csrf_token: str = Header(alias="X-CSRF-Token"),
    staff_token: str = Cookie(alias="jwt", default=None),
    customer_token: str = Cookie(alias="jwt_customer", default=None),
) -> dict:
    if not x_csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing")

    # Try each JWT and pick the one whose CSRF matches the header
    for token in [staff_token, customer_token]:
        payload = _decode_token(token)
        if payload and payload.get("csrf_token") == x_csrf_token:
            return payload

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")


def require_staff(payload: dict = Depends(verify_csrf)) -> dict:
    role = payload.get("role", "").lower()
    if role not in ("admin", "kitchen", "cashier"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")
    return payload


def require_admin(payload: dict = Depends(verify_csrf)) -> dict:
    if payload.get("role", "").lower() != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return payload


def require_kitchen(payload: dict = Depends(verify_csrf)) -> dict:
    role = payload.get("role", "").lower()
    if role not in ("admin", "kitchen"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Kitchen staff access required")
    return payload


def require_customer(payload: dict = Depends(verify_csrf)) -> dict:
    if payload.get("role", "").lower() != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer access required")
    return payload


def require_customer_read_only(payload: dict = Depends(get_jwt_payload)) -> dict:
    if payload.get("role", "").lower() != "customer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer access required")
    return payload


def require_staff_read_only(payload: dict = Depends(get_jwt_payload)) -> dict:
    role = payload.get("role", "").lower()
    if role not in ("admin", "kitchen", "cashier"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")
    return payload


def require_admin_read_only(payload: dict = Depends(get_jwt_payload)) -> dict:
    if payload.get("role", "").lower() != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return payload