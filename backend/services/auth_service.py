import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User, UserRole

DEMO_RESET_OTPS: dict[str, dict[str, Any]] = {}

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"pbkdf2_sha256$120000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_access_token(user: User, expires_in: int = 86_400) -> str:
    payload = {"sub": user.id, "role": user.role.value, "exp": int(time.time()) + expires_in}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.auth_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def generate_demo_farmer_id(user_id: int) -> str:
    return f"MP-FRM-{100000 + user_id}"


def create_demo_otp(phone: str) -> str:
    otp = f"{secrets.randbelow(900000) + 100000}"
    DEMO_RESET_OTPS[phone] = {"otp": otp, "expires_at": int(time.time()) + 600, "used": False}
    print(f"[DEMO OTP] {phone}: {otp}")
    return otp


def verify_demo_otp(phone: str, otp: str) -> bool:
    entry = DEMO_RESET_OTPS.get(phone)
    if entry is None or entry["used"] or int(time.time()) > int(entry["expires_at"]):
        return False
    if entry["otp"] != str(otp):
        return False
    entry["used"] = True
    return True


def reset_password_for_phone(db: Session, phone: str, otp: str, new_password: str) -> User:
    user = db.scalar(select(User).where(User.phone == phone))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_demo_otp(phone, otp):
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")
    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, phone: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.phone == phone))
    return user if user and verify_password(password, user.password_hash) else None


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        encoded, signature = credentials.credentials.split(".", 1)
        expected = hmac.new(settings.auth_secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError
        user = db.scalar(select(User).where(User.id == int(payload["sub"])))
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        user = None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token")
    return user


def optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        return current_user(credentials, db)
    except HTTPException:
        return None


def require_roles(*roles: UserRole):
    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return dependency