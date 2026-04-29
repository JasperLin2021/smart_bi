"""baseline existing smart bi schema

Revision ID: 20260429_0001
Revises:
Create Date: 2026-04-29
"""

from typing import Sequence, Union

revision: str = "20260429_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing deployments were created by SQLAlchemy metadata on startup.
    # This revision establishes an Alembic baseline; subsequent revisions own
    # product schema changes.
    pass


def downgrade() -> None:
    pass
