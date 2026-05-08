"""metric: remove table_name and lineage_json (derived from dataset)

Revision ID: 20260508_0024
Revises: 20260508_0023
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260508_0024"
down_revision = "20260508_0023"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("metrics", "table_name")
    op.drop_column("metrics", "lineage_json")


def downgrade():
    op.add_column("metrics", sa.Column("table_name", sa.String(64), nullable=True))
    op.add_column("metrics", sa.Column("lineage_json", sa.JSON(), nullable=True))
