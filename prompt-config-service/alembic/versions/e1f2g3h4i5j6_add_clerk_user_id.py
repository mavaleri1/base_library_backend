"""Add Clerk user ID to user_profiles

Revision ID: e1f2g3h4i5j6
Revises: d5f8a1b2c3d4
Create Date: 2026-02-04 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e1f2g3h4i5j6"
down_revision: Union[str, Sequence[str], None] = "d5f8a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add clerk_user_id column to user_profiles."""
    print("Adding clerk_user_id column to user_profiles...")
    op.add_column(
        "user_profiles",
        sa.Column("clerk_user_id", sa.String(length=255), nullable=True),
    )
    op.create_index("idx_user_profiles_clerk", "user_profiles", ["clerk_user_id"])
    op.alter_column("user_profiles", "wallet_address", nullable=True)
    print("clerk_user_id column added successfully!")


def downgrade() -> None:
    """Remove clerk_user_id column from user_profiles."""
    print("Removing clerk_user_id column from user_profiles...")
    op.alter_column("user_profiles", "wallet_address", nullable=False)
    op.drop_index("idx_user_profiles_clerk", table_name="user_profiles")
    op.drop_column("user_profiles", "clerk_user_id")
    print("clerk_user_id column removed successfully!")
