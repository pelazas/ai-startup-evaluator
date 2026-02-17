from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    technical_skills: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    domain_expertise: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    years_experience: Mapped[str] = mapped_column(String(10), nullable=False)
    team_size: Mapped[str] = mapped_column(String(20), nullable=False)
    budget_range: Mapped[str] = mapped_column(String(20), nullable=False)
    network_strength: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_tolerance: Mapped[str] = mapped_column(String(10), nullable=False)
    geographic_location: Mapped[str] = mapped_column(String(255), nullable=False)
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
