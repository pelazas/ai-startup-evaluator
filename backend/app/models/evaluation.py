from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    profile_snapshot_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("profile_snapshots.id"), nullable=False
    )

    idea_description: Mapped[str] = mapped_column(Text, nullable=False)
    target_customer: Mapped[str | None] = mapped_column(Text, nullable=True)
    problem_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    startup_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    market_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    idea_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list, server_default=text("ARRAY[]::text[]"))
    idea_folder: Mapped[str | None] = mapped_column(String(64), nullable=True)

    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)

    market_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    technical_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distribution_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    founder_fit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timing_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    dimension_analyses: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    top_risks: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    evidence_sources: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    low_confidence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default=text("'pending'"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())
