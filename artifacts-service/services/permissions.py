"""Permission checking utilities for materials access control."""

import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models_web3 import Material, User

logger = logging.getLogger(__name__)


async def check_material_ownership(
    material_id: str,
    user_id: str,
    db: AsyncSession
) -> bool:
    """Check if user owns the material.
    
    Args:
        material_id: Material UUID
        user_id: User's internal UUID
        db: Database session
        
    Returns:
        True if user owns the material, False otherwise
    """
    try:
        result = await db.execute(
            select(Material).where(Material.id == material_id)
        )
        material = result.scalar_one_or_none()
        
        if not material:
            return False
        
        # Get author
        author_result = await db.execute(
            select(User).where(User.id == material.author_id)
        )
        author = author_result.scalar_one_or_none()
        
        if not author:
            return False
        
        return str(author.id) == str(user_id)
        
    except Exception as e:
        logger.error(f"Error checking material ownership: {e}", exc_info=True)
        return False


async def can_view_material(
    material: Material,
    user_id: Optional[str] = None,
    db: Optional[AsyncSession] = None
) -> bool:
    """Check if user can view the material.
    
    Args:
        material: Material object
        user_id: User's internal UUID (None for anonymous)
        db: Database session (required if user_wallet is provided)
        
    Returns:
        True if user can view the material, False otherwise
    """
    # Published materials are accessible to everyone
    if material.status == "published":
        return True
    
    # Draft and archived materials only accessible to owner
    if user_id and db:
        # Get author
        author_result = await db.execute(
            select(User).where(User.id == material.author_id)
        )
        author = author_result.scalar_one_or_none()
        
        if author:
            return str(author.id) == str(user_id)
    
    return False


async def can_edit_material(
    material: Material,
    user_id: str,
    db: AsyncSession
) -> bool:
    """Check if user can edit the material.
    
    Only material owner can edit it.
    
    Args:
        material: Material object
        user_wallet: User's wallet address
        db: Database session
        
    Returns:
        True if user can edit the material, False otherwise
    """
    return await check_material_ownership(str(material.id), user_id, db)


async def get_material_with_permissions(
    material: Material,
    current_user_id: Optional[str],
    db: AsyncSession
) -> dict:
    """Get material data with permission flags.
    
    Args:
        material: Material object
        current_user_wallet: Current user's wallet address (None if not authenticated)
        db: Database session
        
    Returns:
        Dictionary with material data and permission flags
    """
    # Get author
    author_result = await db.execute(
        select(User).where(User.id == material.author_id)
    )
    author = author_result.scalar_one_or_none()
    author_clerk_id = author.clerk_user_id if author else None
    
    # Check permissions
    can_edit = False
    if current_user_id:
        can_edit = str(material.author_id) == str(current_user_id)
    
    return {
        "id": str(material.id),
        "author_id": str(material.author_id),
        "author_clerk_id": author_clerk_id,
        "thread_id": material.thread_id,
        "session_id": material.session_id,
        "file_path": material.file_path,
        "subject": material.subject,
        "grade": material.grade,
        "topic": material.topic,
        "content_hash": material.content_hash,
        "ipfs_cid": material.ipfs_cid,
        "title": material.title,
        "word_count": material.word_count,
        "status": material.status,
        "created_at": material.created_at.isoformat(),
        "updated_at": material.updated_at.isoformat(),
        "can_edit": can_edit
    }


