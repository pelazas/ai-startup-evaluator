from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role_title: Mapped[str] = mapped_column(String(40), nullable=False)
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_city_country: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    industry_focus: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    business_model: Mapped[str] = mapped_column(String(32), nullable=False)
    target_market: Mapped[str] = mapped_column(String(32), nullable=False)
    team_size: Mapped[str] = mapped_column(String(20), nullable=False)
    weekly_hours_available: Mapped[int] = mapped_column(Integer, nullable=False)
    budget_range: Mapped[str] = mapped_column(String(20), nullable=False)
    hiring_ability: Mapped[str] = mapped_column(String(16), nullable=False)
    cloud_deployment_level: Mapped[str] = mapped_column(String(16), nullable=False)
    ai_coding_agents_level: Mapped[str] = mapped_column(String(16), nullable=False)
    backend_engineering_level: Mapped[str] = mapped_column(String(16), nullable=False)
    product_ux_level: Mapped[str] = mapped_column(String(16), nullable=False)
    data_ml_engineering_level: Mapped[str] = mapped_column(String(16), nullable=False)
    shipping_velocity: Mapped[str] = mapped_column(String(16), nullable=False)
    domain_expertise_level: Mapped[int] = mapped_column(Integer, nullable=False)
    distribution_channels: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    audience_access: Mapped[str] = mapped_column(String(24), nullable=False)
    sales_experience: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_tolerance: Mapped[str] = mapped_column(String(10), nullable=False)
    preferred_time_to_revenue: Mapped[str] = mapped_column(String(12), nullable=False)
    motivation_type: Mapped[str] = mapped_column(String(24), nullable=False)
    commitment_horizon: Mapped[str] = mapped_column(String(12), nullable=False)
    regulatory_constraints: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    regulatory_constraints_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_constraints: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    ip_constraints_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    geo_legal_constraints: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    geo_legal_constraints_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_style: Mapped[str] = mapped_column(String(16), nullable=False)
    priority_dimensions: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProfileSnapshot(Base):
    __tablename__ = "profile_snapshots"
    __table_args__ = (UniqueConstraint("user_id", "profile_data", name="uq_profile_snapshots_user_profile_data"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    profile_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
