"""JWT authentication utilities for prompt-config-service."""

import logging
import uuid
from typing import Optional

import jwt
from jwt import PyJWKClient
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models.user_settings import UserProfile
from repositories.user_settings_repo import UserSettingsRepository

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)


def verify_clerk_token(token: str) -> Optional[dict]:
    """Verify Clerk JWT token and return payload."""
    if not settings.clerk_jwks_url or not settings.clerk_issuer:
        logger.error("Clerk JWT configuration is missing")
        return None

    try:
        jwk_client = PyJWKClient(settings.clerk_jwks_url)
        signing_key = jwk_client.get_signing_key_from_jwt(token).key
        decode_kwargs = {
            "algorithms": ["RS256"],
            "issuer": settings.clerk_issuer,
            "options": {"verify_aud": bool(settings.clerk_audience)},
        }
        if settings.clerk_audience:
            decode_kwargs["audience"] = settings.clerk_audience
        payload = jwt.decode(token, signing_key, **decode_kwargs)
        return payload
    except jwt.PyJWTError as e:
        logger.error(f"Clerk JWT verification failed: {e}")
        return None


async def resolve_user_id_from_artifacts(token: str) -> Optional[uuid.UUID]:
    """Resolve internal user ID from artifacts-service using Clerk token."""
    url = f"{settings.artifacts_service_url}/api/auth/me"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code != 200:
            logger.warning(f"Artifacts user resolution failed: {response.status_code}")
            return None
        data = response.json()
        return uuid.UUID(data["id"])
    except Exception as e:
        logger.error(f"Failed to resolve user from artifacts-service: {e}")
        return None


async def get_current_user_from_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[UserProfile]:
    """Get or create user from JWT token.
    
    This dependency:
    1. Extracts and verifies Clerk JWT token
    2. Resolves internal user_id from artifacts-service
    3. Checks if user exists in prompt-config-service database
    4. If not exists, creates user with same UUID from artifacts-service
    5. Returns user profile
    """
    if not credentials:
        logger.warning("No authorization credentials provided")
        return None
    
    token = credentials.credentials
    payload = verify_clerk_token(token)
    
    if not payload:
        logger.warning("Invalid Clerk token")
        return None
    
    clerk_user_id = payload.get("sub")
    if not clerk_user_id:
        logger.warning("Missing clerk user ID in token payload")
        return None

    user_id = await resolve_user_id_from_artifacts(token)
    if not user_id:
        logger.warning("Unable to resolve user ID from artifacts-service")
        return None
    
    repo = UserSettingsRepository(db)
    
    # Try to get user by internal ID first
    user = await repo.get_user_by_id(user_id)
    
    if not user:
        # User doesn't exist in prompt-config-service, create with same UUID from artifacts-service
        logger.info(f"Creating user in prompt-config-service for Clerk {clerk_user_id} with ID {user_id}")
        user = await repo.get_or_create_user(
            clerk_user_id=clerk_user_id,
            user_id=user_id,
        )
        await db.commit()
    
    return user


async def require_auth(
    user: Optional[UserProfile] = Depends(get_current_user_from_token)
) -> UserProfile:
    """Require authentication - raises 401 if user is not authenticated."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user

