"""upgrade profile schema for richer founder classification

Revision ID: 20260217_0003
Revises: 20260217_0002
Create Date: 2026-02-17 15:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260217_0003"
down_revision: Union[str, None] = "20260217_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("full_name", sa.String(length=120), nullable=True))
    op.add_column("profiles", sa.Column("role_title", sa.String(length=40), nullable=True))
    op.add_column("profiles", sa.Column("linkedin_url", sa.String(length=255), nullable=True))
    op.add_column("profiles", sa.Column("location_city_country", sa.String(length=255), nullable=True))
    op.add_column("profiles", sa.Column("timezone", sa.String(length=64), nullable=True))
    op.add_column("profiles", sa.Column("current_stage", sa.String(length=24), nullable=True))
    op.add_column("profiles", sa.Column("industry_focus", postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column("profiles", sa.Column("business_model", sa.String(length=32), nullable=True))
    op.add_column("profiles", sa.Column("target_market", sa.String(length=32), nullable=True))
    op.add_column("profiles", sa.Column("weekly_hours_available", sa.Integer(), nullable=True))
    op.add_column("profiles", sa.Column("hiring_ability", sa.String(length=16), nullable=True))
    op.add_column("profiles", sa.Column("ai_ml_maturity", sa.String(length=20), nullable=True))
    op.add_column("profiles", sa.Column("shipping_velocity", sa.String(length=16), nullable=True))
    op.add_column("profiles", sa.Column("data_access_level", sa.String(length=48), nullable=True))
    op.add_column("profiles", sa.Column("domain_expertise_level", sa.Integer(), nullable=True))
    op.add_column("profiles", sa.Column("distribution_channels", postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column("profiles", sa.Column("audience_access", sa.String(length=24), nullable=True))
    op.add_column("profiles", sa.Column("sales_experience", sa.String(length=16), nullable=True))
    op.add_column("profiles", sa.Column("preferred_time_to_revenue", sa.String(length=12), nullable=True))
    op.add_column("profiles", sa.Column("motivation_type", sa.String(length=24), nullable=True))
    op.add_column("profiles", sa.Column("commitment_horizon", sa.String(length=12), nullable=True))
    op.add_column("profiles", sa.Column("regulatory_constraints", sa.Boolean(), server_default=sa.text("false"), nullable=True))
    op.add_column("profiles", sa.Column("regulatory_constraints_notes", sa.Text(), nullable=True))
    op.add_column("profiles", sa.Column("ip_constraints", sa.Boolean(), server_default=sa.text("false"), nullable=True))
    op.add_column("profiles", sa.Column("ip_constraints_notes", sa.Text(), nullable=True))
    op.add_column("profiles", sa.Column("geo_legal_constraints", sa.Boolean(), server_default=sa.text("false"), nullable=True))
    op.add_column("profiles", sa.Column("geo_legal_constraints_notes", sa.Text(), nullable=True))
    op.add_column("profiles", sa.Column("confidence_style", sa.String(length=16), nullable=True))
    op.add_column("profiles", sa.Column("priority_dimensions", postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column("profiles", sa.Column("hard_no_go_conditions", sa.Text(), nullable=True))

    op.execute(
        """
        UPDATE profiles SET
          full_name = COALESCE(NULLIF(geographic_location, ''), 'Unknown Founder'),
          role_title = 'Solo Founder',
          location_city_country = geographic_location,
          timezone = 'UTC',
          current_stage = 'Idea',
          industry_focus = COALESCE(domain_expertise, ARRAY['General']::varchar[]),
          business_model = 'SaaS',
          target_market = 'B2B',
          weekly_hours_available = 20,
          hiring_ability = 'None',
          ai_ml_maturity = 'Beginner',
          shipping_velocity = 'Moderate',
          data_access_level = 'No proprietary data',
          domain_expertise_level = GREATEST(1, LEAST(5, network_strength)),
          distribution_channels = ARRAY['Community']::varchar[],
          audience_access = 'None',
          sales_experience = 'None',
          preferred_time_to_revenue = '6-12m',
          motivation_type = 'Technical challenge',
          commitment_horizon = '1-2y',
          regulatory_constraints = false,
          ip_constraints = false,
          geo_legal_constraints = false,
          confidence_style = 'Balanced',
          priority_dimensions = ARRAY['Market', 'Technical']::varchar[]
        """
    )

    op.alter_column("profiles", "full_name", nullable=False)
    op.alter_column("profiles", "role_title", nullable=False)
    op.alter_column("profiles", "location_city_country", nullable=False)
    op.alter_column("profiles", "timezone", nullable=False)
    op.alter_column("profiles", "current_stage", nullable=False)
    op.alter_column("profiles", "industry_focus", nullable=False)
    op.alter_column("profiles", "business_model", nullable=False)
    op.alter_column("profiles", "target_market", nullable=False)
    op.alter_column("profiles", "weekly_hours_available", nullable=False)
    op.alter_column("profiles", "hiring_ability", nullable=False)
    op.alter_column("profiles", "ai_ml_maturity", nullable=False)
    op.alter_column("profiles", "shipping_velocity", nullable=False)
    op.alter_column("profiles", "data_access_level", nullable=False)
    op.alter_column("profiles", "domain_expertise_level", nullable=False)
    op.alter_column("profiles", "distribution_channels", nullable=False)
    op.alter_column("profiles", "audience_access", nullable=False)
    op.alter_column("profiles", "sales_experience", nullable=False)
    op.alter_column("profiles", "preferred_time_to_revenue", nullable=False)
    op.alter_column("profiles", "motivation_type", nullable=False)
    op.alter_column("profiles", "commitment_horizon", nullable=False)
    op.alter_column("profiles", "regulatory_constraints", nullable=False)
    op.alter_column("profiles", "ip_constraints", nullable=False)
    op.alter_column("profiles", "geo_legal_constraints", nullable=False)
    op.alter_column("profiles", "confidence_style", nullable=False)
    op.alter_column("profiles", "priority_dimensions", nullable=False)

    op.drop_column("profiles", "domain_expertise")
    op.drop_column("profiles", "years_experience")
    op.drop_column("profiles", "network_strength")
    op.drop_column("profiles", "geographic_location")


def downgrade() -> None:
    op.add_column("profiles", sa.Column("geographic_location", sa.String(length=255), nullable=True))
    op.add_column("profiles", sa.Column("network_strength", sa.Integer(), nullable=True))
    op.add_column("profiles", sa.Column("years_experience", sa.String(length=10), nullable=True))
    op.add_column("profiles", sa.Column("domain_expertise", postgresql.ARRAY(sa.Text()), nullable=True))

    op.execute(
        """
        UPDATE profiles SET
          geographic_location = location_city_country,
          network_strength = GREATEST(1, LEAST(10, domain_expertise_level)),
          years_experience = '3-5',
          domain_expertise = COALESCE(industry_focus, ARRAY['General']::text[])
        """
    )

    op.alter_column("profiles", "domain_expertise", nullable=False)
    op.alter_column("profiles", "years_experience", nullable=False)
    op.alter_column("profiles", "network_strength", nullable=False)
    op.alter_column("profiles", "geographic_location", nullable=False)

    op.drop_column("profiles", "hard_no_go_conditions")
    op.drop_column("profiles", "priority_dimensions")
    op.drop_column("profiles", "confidence_style")
    op.drop_column("profiles", "geo_legal_constraints_notes")
    op.drop_column("profiles", "geo_legal_constraints")
    op.drop_column("profiles", "ip_constraints_notes")
    op.drop_column("profiles", "ip_constraints")
    op.drop_column("profiles", "regulatory_constraints_notes")
    op.drop_column("profiles", "regulatory_constraints")
    op.drop_column("profiles", "commitment_horizon")
    op.drop_column("profiles", "motivation_type")
    op.drop_column("profiles", "preferred_time_to_revenue")
    op.drop_column("profiles", "sales_experience")
    op.drop_column("profiles", "audience_access")
    op.drop_column("profiles", "distribution_channels")
    op.drop_column("profiles", "domain_expertise_level")
    op.drop_column("profiles", "data_access_level")
    op.drop_column("profiles", "shipping_velocity")
    op.drop_column("profiles", "ai_ml_maturity")
    op.drop_column("profiles", "hiring_ability")
    op.drop_column("profiles", "weekly_hours_available")
    op.drop_column("profiles", "target_market")
    op.drop_column("profiles", "business_model")
    op.drop_column("profiles", "industry_focus")
    op.drop_column("profiles", "current_stage")
    op.drop_column("profiles", "timezone")
    op.drop_column("profiles", "location_city_country")
    op.drop_column("profiles", "linkedin_url")
    op.drop_column("profiles", "role_title")
    op.drop_column("profiles", "full_name")

