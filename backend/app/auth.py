import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

_ITERATIONS = 120_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


def create_token(user: User) -> str:
    payload = {
        "sub": user.id,
        "email": user.email,
        "role": user.role,
        "name": user.name,
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def current_user(token: str | None = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to continue.")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your session expired. Sign in again.") from None
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That sign-in token isn't valid.") from None
    user = db.get(User, payload.get("sub"))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That account no longer exists.")
    return user


def require_role(*roles: str):
    """Role check reads the *database* row, not the token claim, so a demotion
    takes effect on the next request instead of when the JWT expires."""

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"This action needs the {' or '.join(roles)} role. You're signed in as {user.role}.",
            )
        return user

    return dependency


require_editor = require_role("editor", "admin")
require_admin = require_role("admin")
