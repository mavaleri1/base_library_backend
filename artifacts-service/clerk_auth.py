"""Clerk authentication endpoints and helpers."""

import logging
from datetime import datetime
from typing import Optional

import jwt
from jwt import PyJWKClient
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models_web3 import User
from settings import get_settings
from web3_auth import get_db

logger = logging.getLogger(__name__)
settings = get_settings()

security = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/auth", tags=["Clerk Authentication"])


def _get_jwk_client() -> PyJWKClient:
    if not settings.clerk_jwks_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Clerk JWKS URL is not configured",
        )
    return PyJWKClient(settings.clerk_jwks_url)


def verify_clerk_token(token: str) -> dict:
    """Verify Clerk JWT token and return payload."""
    if not settings.clerk_issuer:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Clerk issuer is not configured",
        )

    jwk_client = _get_jwk_client()
    signing_key = jwk_client.get_signing_key_from_jwt(token).key

    decode_kwargs = {
        "algorithms": ["RS256"],
        "issuer": settings.clerk_issuer,
        "options": {"verify_aud": bool(settings.clerk_audience)},
        "leeway": 120,  
    }
    if settings.clerk_audience:
        decode_kwargs["audience"] = settings.clerk_audience

    try:
        payload = jwt.decode(token, signing_key, **decode_kwargs)
        return payload
    except jwt.PyJWTError as exc:
        logger.warning(f"Clerk token verification failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc


async def get_or_create_user(
    clerk_user_id: str,
    db: AsyncSession,
) -> User:
    """Get or create user by Clerk user ID."""
    result = await db.execute(
        select(User).where(User.clerk_user_id == clerk_user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            clerk_user_id=clerk_user_id,
            last_login=datetime.utcnow(),
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        logger.info(f"Created new Clerk user {clerk_user_id}")
    else:
        user.last_login = datetime.utcnow()

    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency to get current authenticated user from Clerk JWT."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = verify_clerk_token(credentials.credentials)
    clerk_user_id = payload.get("sub")

    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    return await get_or_create_user(clerk_user_id, db)


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information."""
    return {
        "id": str(current_user.id),
        "clerk_user_id": current_user.clerk_user_id,
        "created_at": current_user.created_at.isoformat(),
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
    }


@router.post("/logout")
async def logout():
    """Logout endpoint.
    
    Clerk sessions are managed client-side. This endpoint is for API completeness.
    """
    return {"message": "Logged out successfully. Please sign out on client."}
