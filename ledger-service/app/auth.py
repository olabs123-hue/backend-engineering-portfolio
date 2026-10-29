import os
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

hasher = PasswordHasher()
bearer = HTTPBearer()
def hash_password(password: str) -> str:
    return hasher.hash(password)
def check_password(stored: str, password: str) -> bool:
    try:
        return hasher.verify(stored, password)
    except (VerifyMismatchError, VerificationError):
        return False
def secret() -> str:
    value = os.environ.get("JWT_SECRET", "")
    if len(value) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 characters")
    return value
def token_for(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=30)}, secret(), algorithm="HS256")
def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> int:
    try:
        payload = jwt.decode(credentials.credentials, secret(), algorithms=["HS256"])
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="invalid or expired token") from exc
