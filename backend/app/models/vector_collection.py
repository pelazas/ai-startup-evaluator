from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class VectorCollectionBase:
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1024), nullable=False)
    doc_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    content_tsvector: Mapped[str] = mapped_column(TSVECTOR, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, server_default=func.now())


class FounderPrinciplesDoc(VectorCollectionBase, Base):
    __tablename__ = "founder_principles_docs"


class AIMarketDataDoc(VectorCollectionBase, Base):
    __tablename__ = "ai_market_data_docs"


class StartupExamplesDoc(VectorCollectionBase, Base):
    __tablename__ = "startup_examples_docs"


class TechnicalConstraintsDoc(VectorCollectionBase, Base):
    __tablename__ = "technical_constraints_docs"


class PersonalProfileDoc(VectorCollectionBase, Base):
    __tablename__ = "personal_profile_docs"
