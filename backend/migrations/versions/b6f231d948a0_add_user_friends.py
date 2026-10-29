"""Add user friend ID lists.

Revision ID: b6f231d948a0
Revises: 7a27177ad0ee
"""
from alembic import op
import sqlalchemy as sa

revision = "b6f231d948a0"
down_revision = "7a27177ad0ee"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_friends",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("friend_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["friend_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "friend_id"),
        sa.CheckConstraint("user_id <> friend_id", name="ck_user_friends_not_self"),
    )
    op.create_index("ix_user_friends_friend_id", "user_friends", ["friend_id"])


def downgrade() -> None:
    op.drop_index("ix_user_friends_friend_id", table_name="user_friends")
    op.drop_table("user_friends")
