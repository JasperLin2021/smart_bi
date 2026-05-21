"""add enterprise pipeline dag runtime and versions

Revision ID: 20260514_0034
Revises: 20260511_0033
Create Date: 2026-05-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260514_0034"
down_revision: Union[str, None] = "20260511_0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade() -> None:
    if _has_table("data_pipelines"):
        for column_name, column in [
            ("state_json", sa.Column("state_json", sa.JSON(), nullable=True)),
            ("current_version", sa.Column("current_version", sa.Integer(), nullable=False, server_default="0")),
            ("published_version", sa.Column("published_version", sa.Integer(), nullable=False, server_default="0")),
        ]:
            if not _has_column("data_pipelines", column_name):
                op.add_column("data_pipelines", column)

    if _has_table("data_pipeline_runs"):
        for column_name, column in [
            ("notify_result_json", sa.Column("notify_result_json", sa.JSON(), nullable=True)),
            ("scheduled_job_id", sa.Column("scheduled_job_id", sa.String(128), nullable=True)),
            ("duration_ms", sa.Column("duration_ms", sa.Integer(), nullable=True)),
        ]:
            if not _has_column("data_pipeline_runs", column_name):
                op.add_column("data_pipeline_runs", column)

    if not _has_table("data_pipeline_versions"):
        op.create_table(
            "data_pipeline_versions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("pipeline_id", sa.Integer(), nullable=False, index=True),
            sa.Column("version", sa.Integer(), nullable=False, index=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="published", index=True),
            sa.Column("dag_json", sa.JSON(), nullable=False),
            sa.Column("config_json", sa.JSON(), nullable=True),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("created_by", sa.Integer(), nullable=True, index=True),
            sa.Column("published_at", sa.DateTime(), server_default=sa.func.now()),
        )


def downgrade() -> None:
    if _has_table("data_pipeline_versions"):
        op.drop_table("data_pipeline_versions")
    for column_name in ["duration_ms", "scheduled_job_id", "notify_result_json"]:
        if _has_column("data_pipeline_runs", column_name):
            op.drop_column("data_pipeline_runs", column_name)
    for column_name in ["published_version", "current_version", "state_json"]:
        if _has_column("data_pipelines", column_name):
            op.drop_column("data_pipelines", column_name)
