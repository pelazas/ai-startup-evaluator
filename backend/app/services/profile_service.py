from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.profile import Profile, ProfileSnapshot


def _profile_payload(profile: Profile) -> dict:
    return {
        "technical_skills": profile.technical_skills,
        "domain_expertise": profile.domain_expertise,
        "years_experience": profile.years_experience,
        "team_size": profile.team_size,
        "budget_range": profile.budget_range,
        "network_strength": profile.network_strength,
        "risk_tolerance": profile.risk_tolerance,
        "geographic_location": profile.geographic_location,
    }


def get_profile_by_user_id(db: Session, user_id: str) -> Profile | None:
    stmt = select(Profile).where(Profile.user_id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def create_profile(db: Session, user_id: str, profile_data: dict) -> Profile:
    existing = get_profile_by_user_id(db, user_id=user_id)
    if existing is not None:
        raise ValueError("Profile already exists")

    profile = Profile(user_id=user_id, **profile_data)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(db: Session, profile: Profile, profile_data: dict) -> Profile:
    for key, value in profile_data.items():
        setattr(profile, key, value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_or_create_profile_snapshot(db: Session, user_id: str) -> ProfileSnapshot:
    profile = get_profile_by_user_id(db, user_id=user_id)
    if profile is None:
        raise ValueError("Profile not found")

    payload = _profile_payload(profile)
    existing_stmt = select(ProfileSnapshot).where(
        ProfileSnapshot.user_id == user_id,
        ProfileSnapshot.profile_data == payload,
    )
    existing = db.execute(existing_stmt).scalar_one_or_none()
    if existing is not None:
        return existing

    snapshot = ProfileSnapshot(user_id=user_id, profile_data=payload)
    db.add(snapshot)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        deduped = db.execute(existing_stmt).scalar_one_or_none()
        if deduped is None:
            raise
        return deduped

    db.refresh(snapshot)
    return snapshot

