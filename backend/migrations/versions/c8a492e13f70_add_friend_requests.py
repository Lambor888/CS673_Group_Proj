"""Add persistent friend requests.

Revision ID: c8a492e13f70
Revises: b6f231d948a0
"""
from alembic import op
import sqlalchemy as sa

revision = "c8a492e13f70"
down_revision = "b6f231d948a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "friend_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_low_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_high_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recipient_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_low_id", "user_high_id", name="uq_friend_requests_pair"),
        sa.CheckConstraint("user_low_id < user_high_id", name="ck_friend_requests_pair"),
        sa.CheckConstraint(
            "(sender_id = user_low_id AND recipient_id = user_high_id) OR "
            "(sender_id = user_high_id AND recipient_id = user_low_id)",
            name="ck_friend_requests_participants",
        ),
        sa.CheckConstraint("status IN ('pending', 'accepted', 'rejected', 'removed')",
                           name="ck_friend_requests_status"),
    )
    op.create_index("ix_friend_requests_sender_id", "friend_requests", ["sender_id"])
    op.create_index("ix_friend_requests_recipient_id", "friend_requests", ["recipient_id"])


def downgrade() -> None:
    op.drop_table("friend_requests")
