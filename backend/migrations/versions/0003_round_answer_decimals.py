"""Change question_templates.round_answer from boolean to integer decimals.

Revision ID: 0003_round_answer_decimals
Revises: 0002_add_user_blocked_at
Create Date: 2026-10-29
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003_round_answer_decimals"
down_revision: Union[str, None] = "0002_add_user_blocked_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE question_templates ALTER COLUMN round_answer DROP DEFAULT")
    op.execute(
        "ALTER TABLE question_templates ALTER COLUMN round_answer TYPE INTEGER "
        "USING (CASE WHEN round_answer THEN 0 ELSE NULL END)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE question_templates ALTER COLUMN round_answer TYPE BOOLEAN "
        "USING (round_answer IS NOT NULL)"
    )
    op.execute("ALTER TABLE question_templates ALTER COLUMN round_answer SET DEFAULT FALSE")