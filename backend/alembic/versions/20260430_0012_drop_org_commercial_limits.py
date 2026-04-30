"""drop organization commercial limits

Revision ID: 20260430_0012
Revises: 20260430_0011
Create Date: 2026-04-30
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260430_0012"
down_revision: Union[str, None] = "20260430_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COMMERCIAL_COLUMNS = [
    "branding_json",
    "white_label_enabled",
    "monthly_query_limit",
    "big_screen_limit",
    "dashboard_limit",
    "datasource_limit",
    "user_limit",
    "plan_type",
]


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade() -> None:
    if not _has_table("organizations"):
        return
    for column_name in COMMERCIAL_COLUMNS:
        if _has_column("organizations", column_name):
            op.drop_column("organizations", column_name)


def downgrade() -> None:
    pass
