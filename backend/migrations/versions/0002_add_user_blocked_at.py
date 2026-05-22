"""Add local user deactivation marker.

Revision ID: 0002_add_user_blocked_at
Revises: 0001_baseline
Create Date: 2026-05-21
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_add_user_blocked_at"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("blocked_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "blocked_at")
