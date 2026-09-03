"""add shot_edits table, generation_jobs needs_clarification status

Revision ID: 08726385b6b9
Revises: 83f2fb97a942
Create Date: 2026-09-02 23:51:46.057015

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '08726385b6b9'
down_revision: str | Sequence[str] | None = '83f2fb97a942'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('shot_edits',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('shot_id', sa.String(length=36), nullable=False),
    sa.Column('field', sa.String(length=100), nullable=False),
    sa.Column('old_value', sa.Text(), nullable=True),
    sa.Column('new_value', sa.Text(), nullable=False),
    sa.Column('requested_by', sa.String(length=36), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['shot_id'], ['shots.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_shot_edits_shot_id'), 'shot_edits', ['shot_id'], unique=False)

    # SQLAlchemy's Enum() only creates a real Postgres ENUM type on
    # Postgres — SQLite always falls back to VARCHAR (no CHECK constraint
    # autogenerate could detect here), so there is no equivalent SQLite DDL
    # needed: a fresh `Base.metadata.create_all()` or `alembic upgrade head`
    # against SQLite already reflects the updated Python-side JobStatus enum.
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block.
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE jobstatus ADD VALUE IF NOT EXISTS 'NEEDS_CLARIFICATION'")


def downgrade() -> None:
    """Downgrade schema."""
    # Postgres has no ALTER TYPE ... DROP VALUE — removing an enum value
    # requires rebuilding the type, which is out of scope for a downgrade
    # path nothing in this codebase actually exercises against Postgres.
    op.drop_index(op.f('ix_shot_edits_shot_id'), table_name='shot_edits')
    op.drop_table('shot_edits')
