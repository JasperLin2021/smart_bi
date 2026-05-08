"""user: add department field and dept_admin role support

Revision ID: 20260508_0025
Revises: 20260508_0024
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260508_0025"
down_revision = "20260508_0024"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("department", sa.String(64), nullable=True))


def downgrade():
    op.drop_column("users", "department")
