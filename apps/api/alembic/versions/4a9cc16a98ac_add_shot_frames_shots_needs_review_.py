"""add shot_frames, shots.needs_review, generation_jobs progress fields

Revision ID: 4a9cc16a98ac
Revises: ecf94eabb8c5
Create Date: 2026-09-02 08:48:44.611943

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '4a9cc16a98ac'
down_revision: str | Sequence[str] | None = 'ecf94eabb8c5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('shot_frames',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('shot_id', sa.String(length=36), nullable=False),
    sa.Column('image_url', sa.Text(), nullable=False),
    sa.Column('alt_text', sa.Text(), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['shot_id'], ['shots.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('shot_id')
    )
    op.add_column(
        'generation_jobs', sa.Column('current_stage', sa.String(length=50), nullable=True)
    )
    op.add_column('generation_jobs', sa.Column('frames_total', sa.Integer(), nullable=True))
    op.add_column('generation_jobs', sa.Column('frames_completed', sa.Integer(), nullable=True))
    op.add_column('generation_jobs', sa.Column('frames_failed', sa.Integer(), nullable=True))
    # server_default so this ALTER succeeds against a table that already has
    # rows (autogenerate's plain nullable=False would fail on Postgres for
    # any shots inserted before this migration) — the model itself has no
    # server_default, only a Python-side one, so this only matters for
    # existing rows at migration time, not future inserts.
    op.add_column(
        'shots',
        sa.Column('needs_review', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('shots', 'needs_review')
    op.drop_column('generation_jobs', 'frames_failed')
    op.drop_column('generation_jobs', 'frames_completed')
    op.drop_column('generation_jobs', 'frames_total')
    op.drop_column('generation_jobs', 'current_stage')
    op.drop_table('shot_frames')
