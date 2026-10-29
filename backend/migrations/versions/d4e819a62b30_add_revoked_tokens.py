"""Persist revoked login tokens.

Revision ID: d4e819a62b30
Revises: c8a492e13f70
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e819a62b30"
down_revision = "c8a492e13f70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revoked_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("revoked_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("revoked_tokens")
