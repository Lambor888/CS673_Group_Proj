"""add email, google login and round results

Revision ID: 4139cc94314c
Revises: 7a27177ad0ee
Create Date: 2026-10-27 01:56:23.316437

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4139cc94314c'
down_revision: Union[str, Sequence[str], None] = '7a27177ad0ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('round_results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('mode', sa.String(length=20), nullable=False),
    sa.Column('score', sa.Integer(), nullable=False),
    sa.Column('distance_km', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('round_results', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_round_results_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email', sa.String(length=254), nullable=True))
        batch_op.add_column(sa.Column('google_sub', sa.String(length=255), nullable=True))
        batch_op.alter_column('password_hash',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_google_sub'), ['google_sub'], unique=True)



def downgrade() -> None:
    """Downgrade schema."""
    # password_hash becomes required again, so Google-only accounts can't be kept.
    op.execute("DELETE FROM users WHERE password_hash IS NULL")
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_google_sub'))
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.alter_column('password_hash',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
        batch_op.drop_column('google_sub')
        batch_op.drop_column('email')

    with op.batch_alter_table('round_results', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_round_results_user_id'))

    op.drop_table('round_results')
