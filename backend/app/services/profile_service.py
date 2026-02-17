from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.profile import Profile, ProfileSnapshot


def _profile_payload(profile: Profile) -> dict:
    return {
        "full_name": profile.full_name,
        "role_title": profile.role_title,
        "linkedin_url": profile.linkedin_url,
        "location_city_country": profile.location_city_country,
        "timezone": profile.timezone,
        "current_stage": profile.current_stage,
        "industry_focus": profile.industry_focus,
        "business_model": profile.business_model,
        "target_market": profile.target_market,
        "team_size": profile.team_size,
        "weekly_hours_available": profile.weekly_hours_available,
        "budget_range": profile.budget_range,
        "hiring_ability": profile.hiring_ability,
        "cloud_deployment_level": profile.cloud_deployment_level,
        "ai_coding_agents_level": profile.ai_coding_agents_level,
        "backend_engineering_level": profile.backend_engineering_level,
        "product_ux_level": profile.product_ux_level,
        "data_ml_engineering_level": profile.data_ml_engineering_level,
        "shipping_velocity": profile.shipping_velocity,
        "domain_expertise_level": profile.domain_expertise_level,
        "distribution_channels": profile.distribution_channels,
        "audience_access": profile.audience_access,
        "sales_experience": profile.sales_experience,
        "risk_tolerance": profile.risk_tolerance,
        "preferred_time_to_revenue": profile.preferred_time_to_revenue,
        "motivation_type": profile.motivation_type,
        "commitment_horizon": profile.commitment_horizon,
        "regulatory_constraints": profile.regulatory_constraints,
        "regulatory_constraints_notes": profile.regulatory_constraints_notes,
        "ip_constraints": profile.ip_constraints,
        "ip_constraints_notes": profile.ip_constraints_notes,
        "geo_legal_constraints": profile.geo_legal_constraints,
        "geo_legal_constraints_notes": profile.geo_legal_constraints_notes,
        "confidence_style": profile.confidence_style,
        "priority_dimensions": profile.priority_dimensions,
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
