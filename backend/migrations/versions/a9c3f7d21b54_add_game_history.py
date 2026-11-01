"""add game history

Revision ID: a9c3f7d21b54
Revises: e2710f49b6c2
Create Date: 2026-10-31 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9c3f7d21b54'
down_revision: Union[str, Sequence[str], None] = 'e2710f49b6c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('game_history',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('mode', sa.String(length=20), nullable=False),
    sa.Column('final_score', sa.Integer(), nullable=False),
    sa.Column('rounds_played', sa.Integer(), nullable=False),
    sa.Column('players', sa.Integer(), nullable=False),
    sa.Column('placement', sa.Integer(), nullable=True),
    sa.Column('won', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('game_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_game_history_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('game_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_game_history_user_id'))

    op.drop_table('game_history')
