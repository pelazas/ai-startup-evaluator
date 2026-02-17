"""create vector collection tables

Revision ID: 20260217_0002
Revises: 20260217_0001
Create Date: 2026-02-17 14:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260217_0002"
down_revision: Union[str, None] = "20260217_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLLECTIONS = (
    "founder_principles_docs",
    "ai_market_data_docs",
    "startup_examples_docs",
    "technical_constraints_docs",
    "personal_profile_docs",
)


def _create_collection_table(table_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("id", postgresql.UUID(as_uuid=False), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("content_tsvector", postgresql.TSVECTOR(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("NOW()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        f"CREATE INDEX idx_{table_name}_embedding ON {table_name} USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )
    op.create_index(
        f"idx_{table_name}_content_tsvector",
        table_name,
        ["content_tsvector"],
        unique=False,
        postgresql_using="gin",
    )
    op.execute(
        f"""
        CREATE TRIGGER {table_name}_tsvector_trigger
        BEFORE INSERT OR UPDATE ON {table_name}
        FOR EACH ROW
        EXECUTE FUNCTION update_content_tsvector();
        """
    )


def _drop_collection_table(table_name: str) -> None:
    op.execute(f"DROP TRIGGER IF EXISTS {table_name}_tsvector_trigger ON {table_name}")
    op.drop_index(f"idx_{table_name}_content_tsvector", table_name=table_name)
    op.drop_index(f"idx_{table_name}_embedding", table_name=table_name)
    op.drop_table(table_name)


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_content_tsvector()
        RETURNS trigger AS $$
        BEGIN
          NEW.content_tsvector := to_tsvector('english', COALESCE(NEW.content, ''));
          RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )

    for table_name in COLLECTIONS:
        _create_collection_table(table_name)


def downgrade() -> None:
    for table_name in reversed(COLLECTIONS):
        _drop_collection_table(table_name)

    op.execute("DROP FUNCTION IF EXISTS update_content_tsvector()")
