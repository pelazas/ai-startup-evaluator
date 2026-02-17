from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import create_access_token
from app.auth.service import authenticate_user, create_user, get_user_profile_flag
from app.database import get_db
from app.models.user import User
from app.schemas.auth import AuthRequest, AuthResponse, UserPublic

router = APIRouter()


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: AuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        user = create_user(db, email=payload.email, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    token = create_access_token(subject=user.id)
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserPublic(id=user.id, email=user.email, has_profile=False),
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: AuthRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = authenticate_user(db, email=payload.email, password=payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(subject=user.id)
    has_profile = get_user_profile_flag(db, user_id=user.id)
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserPublic(id=user.id, email=user.email, has_profile=has_profile),
    )


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserPublic:
    return UserPublic(
        id=current_user.id,
        email=current_user.email,
        has_profile=get_user_profile_flag(db, user_id=current_user.id),
    )
