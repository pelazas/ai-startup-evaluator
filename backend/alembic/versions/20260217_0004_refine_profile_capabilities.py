"""refine profile capabilities and remove unused fields

Revision ID: 20260217_0004
Revises: 20260217_0003
Create Date: 2026-02-17 16:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260217_0004"
down_revision: Union[str, None] = "20260217_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("cloud_deployment_level", sa.String(length=16), nullable=True))
    op.add_column("profiles", sa.Column("ai_coding_agents_level", sa.String(length=16), nullable=True))
    op.add_column("profiles", sa.Column("backend_engineering_level", sa.String(length=16), nullable=True))
    op.add_column("profiles", sa.Column("product_ux_level", sa.String(length=16), nullable=True))
    op.add_column("profiles", sa.Column("data_ml_engineering_level", sa.String(length=16), nullable=True))

    op.execute(
        """
        UPDATE profiles SET
          cloud_deployment_level = 'Intermediate',
          ai_coding_agents_level = 'Intermediate',
          backend_engineering_level = 'Intermediate',
          product_ux_level = 'Intermediate',
          data_ml_engineering_level = 'Intermediate'
        """
    )

    op.alter_column("profiles", "cloud_deployment_level", nullable=False)
    op.alter_column("profiles", "ai_coding_agents_level", nullable=False)
    op.alter_column("profiles", "backend_engineering_level", nullable=False)
    op.alter_column("profiles", "product_ux_level", nullable=False)
    op.alter_column("profiles", "data_ml_engineering_level", nullable=False)

    op.drop_column("profiles", "technical_skills")
    op.drop_column("profiles", "data_access_level")
    op.drop_column("profiles", "ai_ml_maturity")
    op.drop_column("profiles", "hard_no_go_conditions")


def downgrade() -> None:
    op.add_column("profiles", sa.Column("hard_no_go_conditions", sa.Text(), nullable=True))
    op.add_column("profiles", sa.Column("ai_ml_maturity", sa.String(length=20), nullable=True))
    op.add_column("profiles", sa.Column("data_access_level", sa.String(length=48), nullable=True))
    op.add_column("profiles", sa.Column("technical_skills", sa.ARRAY(sa.String()), nullable=True))

    op.execute(
        """
        UPDATE profiles SET
          ai_ml_maturity = 'Beginner',
          data_access_level = 'Some',
          technical_skills = ARRAY['Generalist']::varchar[]
        """
    )

    op.alter_column("profiles", "ai_ml_maturity", nullable=False)
    op.alter_column("profiles", "data_access_level", nullable=False)
    op.alter_column("profiles", "technical_skills", nullable=False)

    op.drop_column("profiles", "data_ml_engineering_level")
    op.drop_column("profiles", "product_ux_level")
    op.drop_column("profiles", "backend_engineering_level")
    op.drop_column("profiles", "ai_coding_agents_level")
    op.drop_column("profiles", "cloud_deployment_level")
