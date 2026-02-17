"""create core tables

Revision ID: 20260217_0001
Revises:
Create Date: 2026-02-17 13:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260217_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("technical_skills", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("domain_expertise", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("years_experience", sa.String(length=10), nullable=False),
        sa.Column("team_size", sa.String(length=20), nullable=False),
        sa.Column("budget_range", sa.String(length=20), nullable=False),
        sa.Column("network_strength", sa.Integer(), nullable=False),
        sa.Column("risk_tolerance", sa.String(length=10), nullable=False),
        sa.Column("geographic_location", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "profile_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("profile_data", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "profile_data", name="uq_profile_snapshots_user_profile_data"),
    )

    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("profile_snapshot_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("idea_description", sa.Text(), nullable=False),
        sa.Column("target_customer", sa.Text(), nullable=True),
        sa.Column("problem_statement", sa.Text(), nullable=True),
        sa.Column("startup_type", sa.String(length=50), nullable=True),
        sa.Column("market_type", sa.String(length=10), nullable=True),
        sa.Column("overall_score", sa.Integer(), nullable=True),
        sa.Column("verdict", sa.String(length=20), nullable=True),
        sa.Column("market_score", sa.Integer(), nullable=True),
        sa.Column("technical_score", sa.Integer(), nullable=True),
        sa.Column("distribution_score", sa.Integer(), nullable=True),
        sa.Column("founder_fit_score", sa.Integer(), nullable=True),
        sa.Column("timing_score", sa.Integer(), nullable=True),
        sa.Column("dimension_analyses", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("top_risks", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("evidence_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("low_confidence", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_snapshot_id"], ["profile_snapshots.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_evaluations_user_created", "evaluations", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_evaluations_user_created", table_name="evaluations")
    op.drop_table("evaluations")
    op.drop_table("profile_snapshots")
    op.drop_table("profiles")
    op.drop_table("users")

