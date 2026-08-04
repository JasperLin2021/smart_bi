"""add ai_reports table and relax report_templates.dataset_id

Revision ID: 20260801_0039
Revises: 20260731_0038
Create Date: 2026-08-01

新增「对话式 AI 报表」的 ai_reports 表；同时把 report_templates.dataset_id
放宽为可空 —— ai_html 类型模板由 publish-to-report-center 创建，不关联数据集。

幂等：空库直接建表；老库（表已由 create_all 建过）跳过建表；dataset_id 的
alter 带表/列守卫，且经 batch_alter_table 以兼容 sqlite。
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260801_0039"
down_revision: Union[str, None] = "20260731_0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))


def upgrade() -> None:
    if not _has_table("ai_reports"):
        op.create_table(
            "ai_reports",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("org_id", sa.Integer(), nullable=True, index=True),
            sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
            sa.Column("title", sa.String(256), nullable=False),
            sa.Column("html", sa.Text(), nullable=False),
            sa.Column("conversation_json", sa.Text(), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
            sa.Column("share_token", sa.String(64), nullable=True, unique=True, index=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        )

    # ai_html 类型模板无数据集，dataset_id 放宽为可空
    if _has_column("report_templates", "dataset_id"):
        with op.batch_alter_table("report_templates") as batch_op:
            batch_op.alter_column("dataset_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    if _has_column("report_templates", "dataset_id"):
        with op.batch_alter_table("report_templates") as batch_op:
            batch_op.alter_column("dataset_id", existing_type=sa.Integer(), nullable=False)
    if _has_table("ai_reports"):
        op.drop_table("ai_reports")
