"""User settings models for managing user-specific configurations.

This module has been updated to support Web3 authentication via wallet addresses.
Telegram support has been completely removed.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base


class UserProfile(Base):
    """Model for user profiles - Clerk authentication."""
    
    __tablename__ = "user_profiles"
    
    # Primary key - internal UUID for relationships
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, 
        primary_key=True, 
        default=uuid.uuid4,
        comment="Internal UUID for database relationships"
    )
    
    # Clerk user ID - unique identifier for user
    clerk_user_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
        comment="Clerk user ID (e.g. user_...)"
    )
    
    # Legacy Web3 wallet address (optional, deprecated)
    wallet_address: Mapped[Optional[str]] = mapped_column(
        String(42),
        unique=True,
        nullable=True,
        index=True,
        comment="Legacy Ethereum wallet address (deprecated)"
    )
    
    # Optional display name
    username: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Optional display name for user"
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        comment="User profile creation timestamp"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp"
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Last successful login timestamp"
    )
    
    # Relationships
    placeholder_settings: Mapped[list["UserPlaceholderSetting"]] = relationship(
        "UserPlaceholderSetting",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<UserProfile(id={self.id}, clerk={self.clerk_user_id[:12] if self.clerk_user_id else 'none'}...)>"


class UserPlaceholderSetting(Base):
    """Model for user-specific placeholder settings.
    
    Links users to their chosen placeholder values for prompt personalization.
    """
    
    __tablename__ = "user_placeholder_settings"
    
    # Composite primary key
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("user_profiles.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Reference to user profile"
    )
    placeholder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("placeholders.id", ondelete="CASCADE"),
        primary_key=True,
        comment="Reference to placeholder"
    )
    
    # Selected value for this placeholder
    placeholder_value_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("placeholder_values.id", ondelete="RESTRICT"),
        nullable=False,
        comment="Selected value for this placeholder"
    )
    
    # Timestamp
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last update timestamp"
    )
    
    # Relationships
    user: Mapped["UserProfile"] = relationship(
        "UserProfile",
        back_populates="placeholder_settings"
    )
    placeholder: Mapped["Placeholder"] = relationship(
        "Placeholder",
        back_populates="user_settings"
    )
    placeholder_value: Mapped["PlaceholderValue"] = relationship(
        "PlaceholderValue",
        back_populates="user_settings"
    )

    def __repr__(self) -> str:
        return f"<UserPlaceholderSetting(user_id={self.user_id}, placeholder_id={self.placeholder_id})>"