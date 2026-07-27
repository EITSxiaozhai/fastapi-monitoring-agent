"""add_hidden_agent_ids

Revision ID: a1b2c3d4e5f6
Revises: db7763314aba
Create Date: 2026-07-27 16:55:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'db7763314aba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE user_machines_display_prefs
        ADD COLUMN IF NOT EXISTS hidden_agent_ids JSON NOT NULL DEFAULT '[]'::json
        """
    )


def downgrade() -> None:
    op.drop_column('user_machines_display_prefs', 'hidden_agent_ids')
