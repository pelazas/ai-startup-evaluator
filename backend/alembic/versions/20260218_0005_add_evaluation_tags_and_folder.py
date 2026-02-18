"""add idea tags and folder to evaluations

Revision ID: 20260218_0005
Revises: 20260217_0004
Create Date: 2026-02-18 18:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260218_0005"
down_revision: Union[str, None] = "20260217_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "evaluations",
        sa.Column(
            "idea_tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
    )
    op.add_column("evaluations", sa.Column("idea_folder", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("evaluations", "idea_folder")
    op.drop_column("evaluations", "idea_tags")
