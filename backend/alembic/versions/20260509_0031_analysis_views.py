"""create analysis views table

Revision ID: 20260509_0031
Revises: 20260509_0030
Create Date: 2026-05-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260509_0031"
down_revision: Union[str, None] = "20260509_0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("analysis_views"):
        return
    op.create_table(
        "analysis_views",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("chart_type", sa.String(length=32), nullable=False, server_default="bar"),
        sa.Column("dimensions", sa.JSON(), nullable=True),
        sa.Column("measures", sa.JSON(), nullable=True),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("sorts", sa.JSON(), nullable=True),
        sa.Column("calculation_fields_json", sa.JSON(), nullable=True),
        sa.Column("visual_config_json", sa.JSON(), nullable=True),
        sa.Column("interaction_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("visibility", sa.String(length=32), nullable=False, server_default="private"),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "name", "dataset_id", "chart_type", "status", "visibility", "org_id", "owner_id"):
        op.create_index(op.f(f"ix_analysis_views_{column}"), "analysis_views", [column], unique=False)


def downgrade() -> None:
    if _has_table("analysis_views"):
        op.drop_table("analysis_views")
