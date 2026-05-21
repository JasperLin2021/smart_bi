"""baseline existing smart bi schema

Revision ID: 20260429_0001
Revises:
Create Date: 2026-04-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260429_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing deployments were created by SQLAlchemy metadata on startup. The
    # baseline keeps the minimal legacy tables that later migrations reference
    # so a production deploy can run Alembic before the application starts.
    bind = op.get_bind()
    metadata = sa.MetaData()
    organizations = sa.Table(
        "organizations",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column("hashed_password", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=32), server_default="user", nullable=True),
        sa.Column("org_id", sa.Integer(), nullable=True, index=True),
    )
    datasources = sa.Table(
        "datasources",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("slug", sa.String(length=64), nullable=False, unique=True),
        sa.Column("database_url", sa.String(length=512), nullable=False),
        sa.Column("source_type", sa.String(length=32), server_default="database", nullable=True),
        sa.Column("metadata_prompt", sa.Text(), nullable=False),
        sa.Column("schema_metadata", sa.Text(), nullable=True),
        sa.Column("metrics_prompt", sa.Text(), nullable=True),
        sa.Column("text2sql_prompt", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Integer(), server_default="1", nullable=True),
        sa.Column("org_id", sa.Integer(), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    metrics = sa.Table(
        "metrics",
        metadata,
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("datasource_id", sa.Integer(), nullable=True, index=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("table_name", sa.String(length=64), nullable=True),
        sa.Column("column_name", sa.String(length=64), nullable=True),
        sa.Column("formula", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Integer(), server_default="1", nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )
    organizations.create(bind, checkfirst=True)
    users.create(bind, checkfirst=True)
    datasources.create(bind, checkfirst=True)
    metrics.create(bind, checkfirst=True)
    sa.Index("ix_organizations_id", organizations.c.id).create(bind, checkfirst=True)
    sa.Index("ix_organizations_slug", organizations.c.slug).create(bind, checkfirst=True)
    sa.Index("ix_users_id", users.c.id).create(bind, checkfirst=True)
    sa.Index("ix_users_username", users.c.username).create(bind, checkfirst=True)
    sa.Index("ix_users_org_id", users.c.org_id).create(bind, checkfirst=True)
    sa.Index("ix_datasources_id", datasources.c.id).create(bind, checkfirst=True)
    sa.Index("ix_datasources_org_id", datasources.c.org_id).create(bind, checkfirst=True)
    sa.Index("ix_metrics_id", metrics.c.id).create(bind, checkfirst=True)
    sa.Index("ix_metrics_datasource_id", metrics.c.datasource_id).create(bind, checkfirst=True)


def downgrade() -> None:
    pass
