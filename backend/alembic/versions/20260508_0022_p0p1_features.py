"""P0/P1 features: alert auto-action, metric compute, access requests, insights, report logs

Revision ID: 20260508_0022
Revises: 20260508_0021
Create Date: 2026-05-08
"""

from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "20260508_0022"
down_revision: Union[str, None] = "20260508_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_col(table: str, col: str) -> bool:
    if not _has_table(table):
        return False
    return col in [c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)]


def upgrade() -> None:
    # alerts: auto action-item columns
    if not _has_col("alerts", "auto_create_action_item"):
        op.add_column("alerts", sa.Column("auto_create_action_item", sa.Boolean(), nullable=False, server_default=sa.false()))
    if not _has_col("alerts", "action_item_assignee_id"):
        op.add_column("alerts", sa.Column("action_item_assignee_id", sa.Integer(), nullable=True))

    # metrics: computed value columns
    if not _has_col("metrics", "last_value"):
        op.add_column("metrics", sa.Column("last_value", sa.Float(), nullable=True))
    if not _has_col("metrics", "last_computed_at"):
        op.add_column("metrics", sa.Column("last_computed_at", sa.DateTime(), nullable=True))

    # query_history: insight columns
    if not _has_col("query_history", "is_insight"):
        op.add_column("query_history", sa.Column("is_insight", sa.Boolean(), nullable=False, server_default=sa.false()))
    if not _has_col("query_history", "insight_title"):
        op.add_column("query_history", sa.Column("insight_title", sa.String(200), nullable=True))
    if not _has_col("query_history", "org_id"):
        op.add_column("query_history", sa.Column("org_id", sa.Integer(), nullable=True))

    # access_requests table
    if not _has_table("access_requests"):
        op.create_table(
            "access_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("requester_id", sa.Integer(), nullable=False),
            sa.Column("resource_type", sa.String(32), nullable=False),
            sa.Column("resource_id", sa.Integer(), nullable=False),
            sa.Column("resource_name", sa.String(128), nullable=True),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("reviewer_id", sa.Integer(), nullable=True),
            sa.Column("review_comment", sa.Text(), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_access_requests_requester_id", "access_requests", ["requester_id"])
        op.create_index("ix_access_requests_resource_type", "access_requests", ["resource_type"])
        op.create_index("ix_access_requests_resource_id", "access_requests", ["resource_id"])
        op.create_index("ix_access_requests_status", "access_requests", ["status"])
        op.create_index("ix_access_requests_org_id", "access_requests", ["org_id"])

    # report_execution_logs table
    if not _has_table("report_execution_logs"):
        op.create_table(
            "report_execution_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("report_id", sa.Integer(), nullable=False),
            sa.Column("report_name", sa.String(128), nullable=True),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("content_preview", sa.Text(), nullable=True),
            sa.Column("notify_result", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("run_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("org_id", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_report_execution_logs_report_id", "report_execution_logs", ["report_id"])
        op.create_index("ix_report_execution_logs_run_at", "report_execution_logs", ["run_at"])


def downgrade() -> None:
    for t in ("report_execution_logs", "access_requests"):
        if _has_table(t):
            op.drop_table(t)
    for table, col in [
        ("query_history", "org_id"), ("query_history", "insight_title"), ("query_history", "is_insight"),
        ("metrics", "last_computed_at"), ("metrics", "last_value"),
        ("alerts", "action_item_assignee_id"), ("alerts", "auto_create_action_item"),
    ]:
        if _has_col(table, col):
            op.drop_column(table, col)
