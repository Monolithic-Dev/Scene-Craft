"""add projects.previs_customization

Revision ID: 83f2fb97a942
Revises: 4a9cc16a98ac
Create Date: 2026-09-02 16:42:58.618605

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '83f2fb97a942'
down_revision: str | Sequence[str] | None = '4a9cc16a98ac'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('projects', sa.Column('previs_customization', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('projects', 'previs_customization')
