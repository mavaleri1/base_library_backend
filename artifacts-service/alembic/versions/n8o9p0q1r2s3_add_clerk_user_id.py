"""Add Clerk user ID to users

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-02-04 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "n8o9p0q1r2s3"
down_revision: Union[str, Sequence[str], None] = "m7n8o9p0q1r2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Clerk user ID column to users."""
    print("Adding clerk_user_id column to users...")
    op.add_column(
        "users",
        sa.Column("clerk_user_id", sa.String(length=255), nullable=True),
    )
    op.create_index("idx_users_clerk", "users", ["clerk_user_id"])
    op.alter_column("users", "wallet_address", nullable=True)
    print("clerk_user_id column added successfully!")


def downgrade() -> None:
    """Remove Clerk user ID column from users."""
    print("Removing clerk_user_id column from users...")
    op.alter_column("users", "wallet_address", nullable=False)
    op.drop_index("idx_users_clerk", table_name="users")
    op.drop_column("users", "clerk_user_id")
    print("clerk_user_id column removed successfully!")
