from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import get_password_hash, verify_password
from app.models.profile import Profile
from app.models.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    normalized_email = email.strip().lower()
    stmt = select(User).where(User.email == normalized_email)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: str) -> User | None:
    stmt = select(User).where(User.id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, email: str, password: str) -> User:
    if get_user_by_email(db, email=email) is not None:
        raise ValueError("Email already exists")

    user = User(email=email.strip().lower(), hashed_password=get_password_hash(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email=email)
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user


def get_user_profile_flag(db: Session, user_id: str) -> bool:
    stmt = select(Profile.id).where(Profile.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none() is not None
