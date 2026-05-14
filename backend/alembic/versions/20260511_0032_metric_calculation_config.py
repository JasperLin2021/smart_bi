"""add structured metric calculation config

Revision ID: 20260511_0032
Revises: 20260509_0031
Create Date: 2026-05-11
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260511_0032"
down_revision: Union[str, None] = "20260509_0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade() -> None:
    if _has_table("metrics") and not _has_column("metrics", "calculation_config"):
        op.add_column("metrics", sa.Column("calculation_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _has_column("metrics", "calculation_config"):
        op.drop_column("metrics", "calculation_config")
