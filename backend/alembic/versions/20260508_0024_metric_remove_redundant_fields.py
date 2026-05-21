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


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade():
    if _has_column("metrics", "table_name"):
        op.drop_column("metrics", "table_name")
    if _has_column("metrics", "lineage_json"):
        op.drop_column("metrics", "lineage_json")


def downgrade():
    if _has_table("metrics") and not _has_column("metrics", "table_name"):
        op.add_column("metrics", sa.Column("table_name", sa.String(64), nullable=True))
    if _has_table("metrics") and not _has_column("metrics", "lineage_json"):
        op.add_column("metrics", sa.Column("lineage_json", sa.JSON(), nullable=True))
