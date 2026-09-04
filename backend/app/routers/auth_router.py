from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import create_token, current_user, verify_password
from ..db import get_db
from ..models import User
from ..schemas import LoginIn, TokenOut, UserOut

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(func.lower(User.email) == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "That email and password don't match.")
    return TokenOut(access_token=create_token(user), role=user.role, name=user.name, email=user.email)


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user
