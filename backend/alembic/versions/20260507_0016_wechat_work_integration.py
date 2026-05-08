"""add WeChat Work integration tables

Revision ID: 20260507_0016
Revises: 20260507_0015
Create Date: 2026-05-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0016"
down_revision: Union[str, None] = "20260507_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    return any(index["name"] == index_name for index in sa.inspect(op.get_bind()).get_indexes(table_name))


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if _has_table(table_name) and not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    if not _has_table("integration_configs"):
        op.create_table(
            "integration_configs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=128), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("corp_id", sa.String(length=128), nullable=True),
            sa.Column("agent_id", sa.String(length=128), nullable=True),
            sa.Column("app_secret", sa.String(length=512), nullable=True),
            sa.Column("callback_url", sa.String(length=512), nullable=True),
            sa.Column("robot_webhook_url", sa.String(length=512), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("integration_configs", op.f("ix_integration_configs_id"), ["id"])
    _create_index_if_missing("integration_configs", op.f("ix_integration_configs_provider"), ["provider"])
    _create_index_if_missing("integration_configs", op.f("ix_integration_configs_corp_id"), ["corp_id"])

    if not _has_table("external_org_bindings"):
        op.create_table(
            "external_org_bindings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("external_corp_id", sa.String(length=128), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "external_corp_id", name="uq_external_org_provider_corp"),
        )
    _create_index_if_missing("external_org_bindings", op.f("ix_external_org_bindings_id"), ["id"])
    _create_index_if_missing("external_org_bindings", op.f("ix_external_org_bindings_provider"), ["provider"])
    _create_index_if_missing("external_org_bindings", op.f("ix_external_org_bindings_external_corp_id"), ["external_corp_id"])
    _create_index_if_missing("external_org_bindings", op.f("ix_external_org_bindings_org_id"), ["org_id"])

    if not _has_table("external_identities"):
        op.create_table(
            "external_identities",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("external_corp_id", sa.String(length=128), nullable=False),
            sa.Column("external_user_id", sa.String(length=128), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("display_name", sa.String(length=128), nullable=True),
            sa.Column("email", sa.String(length=256), nullable=True),
            sa.Column("mobile", sa.String(length=64), nullable=True),
            sa.Column("department_ids_json", sa.Text(), nullable=True),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("provider", "external_corp_id", "external_user_id", name="uq_external_identity"),
        )
    for column in ("id", "provider", "external_corp_id", "external_user_id", "user_id"):
        _create_index_if_missing("external_identities", op.f(f"ix_external_identities_{column}"), [column])

    if not _has_table("external_permission_mappings"):
        op.create_table(
            "external_permission_mappings",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("external_corp_id", sa.String(length=128), nullable=False),
            sa.Column("external_department_id", sa.String(length=128), nullable=False),
            sa.Column("org_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
            sa.Column("data_scope", sa.String(length=32), nullable=True),
            sa.Column("menu_permissions", sa.Text(), nullable=True),
            sa.Column("action_permissions", sa.Text(), nullable=True),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    for column in ("id", "provider", "external_corp_id", "external_department_id", "org_id"):
        _create_index_if_missing("external_permission_mappings", op.f(f"ix_external_permission_mappings_{column}"), [column])

    if not _has_table("message_deliveries"):
        op.create_table(
            "message_deliveries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("channel", sa.String(length=32), nullable=False),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("recipient_user_id", sa.Integer(), nullable=True),
            sa.Column("recipient_external_user_id", sa.String(length=128), nullable=True),
            sa.Column("org_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=256), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("link_url", sa.String(length=512), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    for column in ("id", "provider", "channel", "event_type", "recipient_user_id", "org_id", "status"):
        _create_index_if_missing("message_deliveries", op.f(f"ix_message_deliveries_{column}"), [column])


def downgrade() -> None:
    for table_name in (
        "message_deliveries",
        "external_permission_mappings",
        "external_identities",
        "external_org_bindings",
        "integration_configs",
    ):
        if _has_table(table_name):
            op.drop_table(table_name)
