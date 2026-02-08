"""FastAPI application for Artifacts Service."""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException, status, Path as PathParam, Query, Depends, Form, UploadFile, File
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
import httpx

from storage import ArtifactsStorage
from auth import auth_service, require_auth, verify_resource_owner
from auth_models_api import AuthCodeRequest, AuthTokenResponse
from clerk_auth import router as clerk_router, get_current_user
from web3_auth import get_db
from models_web3 import Material, User
from models import (
    HealthResponse,
    ThreadsListResponse,
    ThreadDetailResponse,
    SessionFilesResponse,
    FileContent,
    FileOperationResponse,
    ErrorResponse,
    ExportFormat,
    PackageType,
    ExportSettings,
    SessionSummary,
    ExportRequest,
    MaterialUpdateRequest,
    MaterialDeleteResponse,
    LeaderboardEntry,
    LeaderboardResponse,
)
from exceptions import ArtifactsServiceException, map_to_http_exception
from settings import settings
from services.export import MarkdownExporter, PDFExporter, ZIPExporter
from services.permissions import (
    check_material_ownership,
    can_view_material,
    can_edit_material,
    get_material_with_permissions
)
from services.content_hash import calculate_content_hash, ContentHashManager
from sqlalchemy import func, select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
# Create logs directory if it doesn't exist
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Console
        logging.FileHandler(log_dir / "artifacts.log", encoding="utf-8")  # File
    ],
    force=True  # Force reconfiguration if logging was already configured
)

# Global storage instance
storage = ArtifactsStorage()

# Logger instance
logger = logging.getLogger(__name__)

# In-memory store for async /api/process results (thread_id -> {status, result?, error?})
# Used when POST returns 202 and client polls GET /api/process/result/{thread_id}
_process_results: Dict[str, Dict[str, Any]] = {}
_process_results_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    # Ensure data directory exists
    storage.base_path.mkdir(parents=True, exist_ok=True)
    # Connect auth service
    await auth_service.connect()
    yield
    # Shutdown - cleanup if needed
    await auth_service.disconnect()


# FastAPI application
app = FastAPI(
    title="Artifacts Service",
    description="File storage system for core AI artifacts",
    version="0.1.0",
    lifespan=lifespan,
)

# Configure CORS (origins from ARTIFACTS_CORS_ORIGINS env for Vercel production)
def _get_cors_origins() -> list[str]:
    origins_str = settings.cors_origins
    return [o.strip() for o in origins_str.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Clerk authentication router
app.include_router(clerk_router, prefix="/api")


@app.exception_handler(ArtifactsServiceException)
async def service_exception_handler(request, exc: ArtifactsServiceException):
    """Handle service exceptions."""
    http_exc = map_to_http_exception(exc)
    return JSONResponse(
        status_code=http_exc.status_code,
        content=ErrorResponse(error=str(exc)).model_dump(),
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Check if storage is accessible
        storage.base_path.exists()
        return HealthResponse(status="ok")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unavailable: {str(e)}",
        )


@app.post("/auth/verify", response_model=AuthTokenResponse)
async def verify_auth_code(request: AuthCodeRequest):
    """Verify auth code and return JWT token."""
    if not auth_service.pool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not available"
        )
    
    user_id = await auth_service.verify_auth_code(request.username, request.code)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired auth code"
        )
    
    # Create JWT token
    token = auth_service.create_jwt_token(user_id, request.username)
    
    return AuthTokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_minutes * 60
    )


@app.get("/threads", response_model=ThreadsListResponse, dependencies=[Depends(require_auth)])
async def get_threads():
    """Get list of all threads."""
    try:
        threads = storage.get_threads()
        return ThreadsListResponse(threads=threads)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get threads: {str(e)}",
        )


@app.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(
    thread_id: str = PathParam(description="Thread identifier"),
    user_id: str = Depends(verify_resource_owner)
):
    """Get information about a specific thread."""
    try:
        thread_info = storage.get_thread_info(thread_id)
        return ThreadDetailResponse(
            thread_id=thread_info.thread_id,
            sessions=thread_info.sessions,
            created=thread_info.created,
            last_activity=thread_info.last_activity,
            sessions_count=thread_info.sessions_count,
        )
    except ArtifactsServiceException as e:
        raise map_to_http_exception(e)


@app.get(
    "/threads/{thread_id}/sessions/{session_id}", response_model=SessionFilesResponse
)
async def get_session_files(
    thread_id: str = PathParam(description="Thread identifier"),
    session_id: str = PathParam(description="Session identifier"),
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get list of files in a session."""
    try:
        # Check if user has access to this material
        # Find material by thread_id
        result = await db.execute(
            select(Material).where(Material.thread_id == thread_id)
        )
        material = result.scalar_one_or_none()
        
        if material:
            # Check ownership
            if not await check_material_ownership(str(material.id), str(current_user.id), db):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access to this resource is forbidden"
                )
        
        files = storage.get_session_files(thread_id, session_id)
        try:
            session_metadata = storage.get_session_metadata(thread_id, session_id)
        except ArtifactsServiceException:
            session_metadata = None
        return SessionFilesResponse(
            thread_id=thread_id,
            session_id=session_id,
            files=files,
            metadata=session_metadata,
        )
    except ArtifactsServiceException as e:
        raise map_to_http_exception(e)


@app.get("/threads/{thread_id}/sessions/{session_id}/files/{file_path:path}")
async def get_file(
    thread_id: str = PathParam(description="Thread identifier"),
    session_id: str = PathParam(description="Session identifier"),
    file_path: str = PathParam(description="File path relative to session"),
    current_user: User = Depends(get_current_user),
    db = Depends(get_db)
):
    """Get file content."""
    try:
        # Check if user has access to this material
        # Find material by thread_id
        result = await db.execute(
            select(Material).where(Material.thread_id == thread_id)
        )
        material = result.scalar_one_or_none()
        
        if material:
            # Check ownership
            if not await check_material_ownership(str(material.id), str(current_user.id), db):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access to this resource is forbidden"
                )
        
        content = storage.read_file(thread_id, session_id, file_path)

        # Determine response type based on file extension
        if file_path.endswith(".json"):
            return JSONResponse(content=content)
        else:
            return PlainTextResponse(content=content, media_type="text/plain")

    except ArtifactsServiceException as e:
        raise map_to_http_exception(e)


@app.post(
    "/threads/{thread_id}/sessions/{session_id}/files/{file_path:path}",
    response_model=FileOperationResponse,
)
async def create_or_update_file(
    file_content: FileContent,
    thread_id: str = PathParam(description="Thread identifier"),
    session_id: str = PathParam(description="Session identifier"),
    file_path: str = PathParam(description="File path relative to session"),
    user_id: str = Depends(verify_resource_owner)
):
    """Create or update a file in a session."""
    try:
        # Check if file already exists
        file_exists = False
        try:
            storage.read_file(thread_id, session_id, file_path)
            file_exists = True
        except Exception as e:
            logger.debug(f"File {file_path} not found, will create new: {e}")

        # Write the file
        storage.write_file(
            thread_id=thread_id,
            session_id=session_id,
            path=file_path,
            content=file_content.content,
            content_type=file_content.content_type,
        )

        if file_exists:
            return FileOperationResponse(message="File updated", path=file_path)
        else:
            return FileOperationResponse(message="File created", path=file_path)

    except ArtifactsServiceException as e:
        raise map_to_http_exception(e)


@app.delete(
    "/threads/{thread_id}/sessions/{session_id}/files/{file_path:path}",
    response_model=FileOperationResponse,
)
async def delete_file(
    thread_id: str = PathParam(description="Thread identifier"),
    session_id: str = PathParam(description="Session identifier"),
    file_path: str = PathParam(description="File path relative to session"),
    user_id: str = Depends(verify_resource_owner)
):
    """Delete a file from a session."""
    try:
        storage.delete_file(thread_id, session_id, file_path)
        return FileOperationResponse(message="File deleted", path=file_path)
    except ArtifactsServiceException as e:
        raise map_to_http_exception(e)


@app.delete(
    "/threads/{thread_id}/sessions/{session_id}", response_model=FileOperationResponse
)
async def delete_session(
    thread_id: str = PathParam(description="Thread identifier"),
    session_id: str = PathParam(description="Session identifier"),
    user_id: str = Depends(verify_resource_owner)
):
    """Delete an entire session with all files."""
    try:
        storage.delete_session(thread_id, session_id)
        return FileOperationResponse(message="Session deleted")
    except ArtifactsServiceException as e:
        raise map_to_http_exception(e)


@app.delete("/threads/{thread_id}", response_model=FileOperationResponse)
async def delete_thread(
    thread_id: str = PathParam(description="Thread identifier"),
    user_id: str = Depends(verify_resource_owner)
):
    """Delete an entire thread with all sessions."""
    try:
        storage.delete_thread(thread_id)
        return FileOperationResponse(message="Thread deleted")
    except ArtifactsServiceException as e:
        raise map_to_http_exception(e)


# Export API Endpoints
# NOTE: These MUST be defined BEFORE the generic file path routes below
# to avoid route conflicts

# Store user settings in memory (in production, use a database)
user_settings = {}


@app.get("/threads/{thread_id}/sessions/{session_id}/export/single")
async def export_single_document(
    thread_id: str = PathParam(description="Thread identifier"),
    session_id: str = PathParam(description="Session identifier"),
    document_name: str = Query(description="Document name to export"),
    format: ExportFormat = Query(ExportFormat.MARKDOWN, description="Export format"),
    user_id: str = Depends(verify_resource_owner)
):
    """Export a single document."""
    try:
        # Select exporter based on format
        if format == ExportFormat.PDF:
            exporter = PDFExporter(storage.base_path)
        else:
            exporter = MarkdownExporter(storage.base_path)
        
        # Export document
        content = await exporter.export_single_document(
            thread_id, session_id, document_name, format
        )
        
        # Determine file extension and mime type
        if format == ExportFormat.PDF:
            ext = "pdf"
            media_type = "application/pdf"
        else:
            ext = "md"
            media_type = "text/markdown"
        
        # Format filename
        filename = exporter.format_filename(document_name, session_id, ext)
        
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


@app.get("/threads/{thread_id}/sessions/{session_id}/export/package")
async def export_package(
    thread_id: str = PathParam(description="Thread identifier"),
    session_id: str = PathParam(description="Session identifier"),
    package_type: PackageType = Query(PackageType.FINAL, description="Package type"),
    format: ExportFormat = Query(ExportFormat.MARKDOWN, description="Export format"),
    user_id: str = Depends(verify_resource_owner)
):
    """Export a package of documents as ZIP archive."""
    logger.info(f"Export package request: thread_id={thread_id}, session_id={session_id}, package_type={package_type}, format={format}, user_id={user_id}")
    
    try:
        # Log storage base path
        logger.debug(f"Storage base path: {storage.base_path}")
        
        # Check if session exists
        session_path = storage.base_path / thread_id / "sessions" / session_id
        logger.debug(f"Checking session path: {session_path}")
        
        if not session_path.exists():
            logger.error(f"Session path does not exist: {session_path}")
            raise FileNotFoundError(f"Session not found: {session_id}")
        
        # List files in session
        files = list(session_path.iterdir())
        logger.debug(f"Files in session: {[f.name for f in files]}")
        
        # Use ZIP exporter
        zip_exporter = ZIPExporter(storage.base_path)
        logger.debug(f"Created ZIPExporter with base_path: {storage.base_path}")
        
        # Export package
        content = await zip_exporter.export_session_archive(
            thread_id, session_id, package_type, format
        )
        logger.info(f"Successfully exported package, size: {len(content)} bytes")
        
        # Format filename
        filename = f"session_{session_id}_export.zip"
        
        return Response(
            content=content,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except FileNotFoundError as e:
        logger.error(f"File not found during export: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Export failed with exception: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


@app.get("/users/{user_id}/sessions/recent", response_model=List[SessionSummary])
async def get_recent_sessions(
    user_id: str = PathParam(description="User identifier"),
    limit: int = Query(5, max=5, description="Maximum number of sessions"),
    auth_user_id: str = Depends(require_auth)
):
    """Get list of recent sessions for export."""
    # Verify user can only access their own sessions
    if user_id != auth_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to other users' sessions is forbidden"
        )
    
    try:
        # Get user's thread (thread_id equals user_id in our system)
        threads_to_check = []
        try:
            thread_info = storage.get_thread_info(user_id)
            threads_to_check = [thread_info]
        except:
            # User has no threads yet
            return []
        
        sessions_list = []
        for thread in threads_to_check:
            for session in thread.sessions[:limit]:
                # Create session summary
                summary = SessionSummary(
                    thread_id=thread.thread_id,
                    session_id=session.session_id,
                    input_content=session.input_content,
                    question_preview=session.input_content[:30] + "..." 
                        if len(session.input_content) > 30 else session.input_content,
                    display_name=f"{session.input_content[:30]}... - {session.created.strftime('%d.%m.%Y')}",
                    created_at=session.created,
                    has_synthesized=False,  # Check if synthesized_material.md exists
                    has_questions=False,     # Check if questions.md exists
                    answers_count=0          # Count answer files
                )
                sessions_list.append(summary)
                
                if len(sessions_list) >= limit:
                    break
        
        return sessions_list
    except Exception as e:
        logger.error(f"Failed to get recent sessions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recent sessions: {str(e)}"
        )


@app.get("/users/{user_id}/export-settings", response_model=ExportSettings)
async def get_export_settings(
    user_id: str = PathParam(description="User identifier"),
    auth_user_id: str = Depends(require_auth)
):
    """Get user export settings."""
    # Verify user can only access their own settings
    if user_id != auth_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to other users' settings is forbidden"
        )
    
    # Return existing settings or create default
    if user_id not in user_settings:
        user_settings[user_id] = ExportSettings(user_id=user_id)
    
    return user_settings[user_id]


@app.put("/users/{user_id}/export-settings", response_model=ExportSettings)
async def update_export_settings(
    user_id: str = PathParam(description="User identifier"),
    settings: ExportSettings = ...,
    auth_user_id: str = Depends(require_auth)
):
    """Update user export settings."""
    # Verify user can only update their own settings
    if user_id != auth_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to other users' settings is forbidden"
        )
    
    settings.user_id = user_id
    settings.modified = datetime.now()
    user_settings[user_id] = settings
    return settings


# =============================================================================
# Materials API - get user materials with blockchain metadata
# =============================================================================

class MaterialResponse(BaseModel):
    """Response model for a single material."""
    id: str
    subject: Optional[str]
    grade: Optional[str]
    topic: Optional[str]
    title: Optional[str]
    content_hash: str
    ipfs_cid: Optional[str]
    word_count: Optional[int]
    status: str
    created_at: str
    updated_at: str
    author_id: str
    author_clerk_id: Optional[str]
    thread_id: str
    session_id: str
    file_path: str


class MaterialsListResponse(BaseModel):
    """Response model for list of materials."""
    materials: List[MaterialResponse]
    total: int
    page: int
    page_size: int


class UserStatsResponse(BaseModel):
    """Response model for user statistics."""
    totalMaterials: int
    publishedMaterials: int
    draftMaterials: int
    subjects: List[dict]


@app.get(
    "/api/materials/my",
    response_model=MaterialsListResponse,
    summary="Get my materials",
    description="Get all materials created by authenticated user with blockchain metadata"
)
async def get_my_materials(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    subject: Optional[str] = Query(None, description="Filter by subject"),
    grade: Optional[str] = Query(None, description="Filter by grade"),
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_user),
):
    """Get materials created by current user."""
    from web3_auth import get_db
    
    async for db in get_db():
        try:
            # Build query
            query = select(Material).where(Material.author_id == current_user.id)
            
            # Apply filters
            if subject:
                query = query.where(Material.subject == subject)
            if grade:
                query = query.where(Material.grade == grade)
            if status:
                query = query.where(Material.status == status)
            
            # Count total
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total = total_result.scalar()
            
            # Apply pagination and ordering
            query = query.order_by(Material.created_at.desc())
            query = query.offset((page - 1) * page_size).limit(page_size)
            
            # Execute query
            result = await db.execute(query)
            materials = result.scalars().all()
            
            # Convert to response model
            materials_response = [
                MaterialResponse(
                    id=str(m.id),
                    subject=m.subject,
                    grade=m.grade,
                    topic=m.topic,
                    title=m.title,
                    content_hash=m.content_hash,
                    ipfs_cid=m.ipfs_cid,
                    word_count=m.word_count,
                    status=m.status,
                    created_at=m.created_at.isoformat(),
                    updated_at=m.updated_at.isoformat(),
                    author_id=str(current_user.id),
                    author_clerk_id=current_user.clerk_user_id,
                    thread_id=m.thread_id,
                    session_id=m.session_id,
                    file_path=m.file_path
                )
                for m in materials
            ]
            
            return MaterialsListResponse(
                materials=materials_response,
                total=total,
                page=page,
                page_size=page_size
            )
            
        except Exception as e:
            logger.error(f"Error fetching materials: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch materials"
            )


@app.get(
    "/api/materials/all",
    response_model=MaterialsListResponse,
    summary="Get all published materials",
    description="Get all published materials from all users (public access)"
)
async def get_all_materials(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    subject: Optional[str] = Query(None, description="Filter by subject"),
    grade: Optional[str] = Query(None, description="Filter by grade"),
    status: Optional[str] = Query("published", description="Filter by status"),
):
    """Get all published materials (public endpoint)."""
    async for db in get_db():
        try:
            # Build query - only published materials by default
            query = select(Material).where(Material.status == status)
            
            # Apply filters
            if subject:
                query = query.where(Material.subject == subject)
            if grade:
                query = query.where(Material.grade == grade)
            
            # Count total
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await db.execute(count_query)
            total = total_result.scalar()
            
            # Apply pagination and ordering
            query = query.order_by(Material.created_at.desc())
            query = query.offset((page - 1) * page_size).limit(page_size)
            
            # Execute query
            result = await db.execute(query)
            materials = result.scalars().all()
            
            # Get materials with author info
            materials_response = []
            for m in materials:
                # Get author
                author_result = await db.execute(
                    select(User).where(User.id == m.author_id)
                )
                author = author_result.scalar_one_or_none()
                author_clerk_id = author.clerk_user_id if author else None
                
                materials_response.append(
                    MaterialResponse(
                        id=str(m.id),
                        subject=m.subject,
                        grade=m.grade,
                        topic=m.topic,
                        title=m.title,
                        content_hash=m.content_hash,
                        ipfs_cid=m.ipfs_cid,
                        word_count=m.word_count,
                        status=m.status,
                        created_at=m.created_at.isoformat(),
                        updated_at=m.updated_at.isoformat(),
                        author_id=str(m.author_id),
                        author_clerk_id=author_clerk_id,
                        thread_id=m.thread_id,
                        session_id=m.session_id,
                        file_path=m.file_path
                    )
                )
            
            return MaterialsListResponse(
                materials=materials_response,
                total=total,
                page=page,
                page_size=page_size
            )
            
        except Exception as e:
            logger.error(f"Error fetching all materials: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch materials"
            )


@app.get(
    "/api/materials/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get materials leaderboard",
    description="Get leaderboard of users by number of created materials and NFTs"
)
async def get_materials_leaderboard(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
):
    """Get leaderboard of users by number of created materials and NFTs."""
    async for db in get_db():
        try:
            # SQL query to get leaderboard data
            # First get total number of users with materials
            total_users_result = await db.execute(
                select(func.count(func.distinct(Material.author_id)))
                .where(Material.id.isnot(None))
            )
            total_users = total_users_result.scalar()
            
            # Main query for leaderboard
            leaderboard_query = select(
                User.id,
                User.clerk_user_id,
                func.count(Material.id).label('materials_count'),
                func.count(Material.id).label('total_score')
            ).select_from(
                User.__table__.join(Material.__table__, User.id == Material.author_id)
            ).group_by(
                User.id, User.clerk_user_id
            ).order_by(
                func.count(Material.id).desc()
            ).offset((page - 1) * page_size).limit(page_size)
            
            # Execute query
            result = await db.execute(leaderboard_query)
            leaderboard_data = result.fetchall()
            
            # Form response
            entries = []
            for rank_offset, row in enumerate(leaderboard_data):
                rank = (page - 1) * page_size + rank_offset + 1
                entries.append(LeaderboardEntry(
                    rank=rank,
                    userId=str(row.id),
                    clerkUserId=row.clerk_user_id,
                    materialsCount=row.materials_count,
                    totalScore=row.total_score
                ))
            
            return LeaderboardResponse(
                entries=entries,
                total=total_users,
                page=page,
                page_size=page_size
            )
            
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get leaderboard"
            )


@app.get(
    "/api/materials/{material_id}",
    summary="Get material by ID",
    description="Get specific material by ID (public for published, owner-only for drafts)"
)
async def get_material(
    material_id: str = PathParam(description="Material UUID"),
    include_content: bool = Query(True, description="Include full content in response"),
    current_user: Optional[User] = Depends(lambda: None),  # Optional auth
):
    """Get specific material by ID."""
    async for db in get_db():
        try:
            # Get material
            result = await db.execute(
                select(Material).where(Material.id == material_id)
            )
            material = result.scalar_one_or_none()
            
            if not material:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Material not found"
                )
            
            # Check viewing permissions
            user_id = str(current_user.id) if current_user else None
            if not await can_view_material(material, user_id, db):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have access to this material"
                )
            
            # Get material with permissions
            response_data = await get_material_with_permissions(
                material, user_id, db
            )
            
            # Optionally include content
            if include_content:
                response_data["content"] = material.content
            
            return JSONResponse(content=response_data)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching material: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch material"
            )


@app.get(
    "/api/materials/stats/subjects",
    summary="Get subject statistics",
    description="Get statistics grouped by subject for current user"
)
async def get_subject_stats(
    current_user: User = Depends(get_current_user),
):
    """Get materials statistics by subject."""
    async for db in get_db():
        try:
            # Query materials grouped by subject
            result = await db.execute(
                select(
                    Material.subject,
                    func.count(Material.id).label("count")
                )
                .where(Material.author_id == current_user.id)
                .group_by(Material.subject)
                .order_by(func.count(Material.id).desc())
            )
            
            stats = [
                {"subject": row.subject or "Unknown", "count": row.count}
                for row in result
            ]
            
            return {"subjects": stats}
            
        except Exception as e:
            logger.error(f"Error fetching subject stats: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to fetch statistics"
            )


@app.patch(
    "/api/materials/{material_id}",
    summary="Update material",
    description="Update existing material (only by owner)"
)
async def update_material(
    material_id: str = PathParam(description="Material UUID"),
    updates: MaterialUpdateRequest = ...,
    current_user: User = Depends(get_current_user),
):
    """Update material (only owner can edit)."""
    async for db in get_db():
        try:
            # Get material
            result = await db.execute(
                select(Material).where(Material.id == material_id)
            )
            material = result.scalar_one_or_none()
            
            if not material:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Material not found"
                )
            
            # Check ownership
            if not await check_material_ownership(material_id, str(current_user.id), db):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to edit this material"
                )
            
            # Validate status if provided
            if updates.status and updates.status not in ["draft", "published", "archived"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid status. Must be: draft, published, or archived"
                )
            
            # Update fields
            updated_fields = []
            
            if updates.title is not None:
                material.title = updates.title
                updated_fields.append("title")
            
            if updates.content is not None:
                # Validate content size (max 1MB)
                if len(updates.content.encode('utf-8')) > 1000000:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Content too large (max 1MB)"
                    )
                
                material.content = updates.content
                updated_fields.append("content")
                
                # Recalculate hash and word count
                hash_manager = ContentHashManager()
                material.content_hash = calculate_content_hash(updates.content)
                material.word_count = hash_manager.calculate_word_count(updates.content)
                
                # Update file on disk
                try:
                    file_full_path = storage.base_path / material.file_path
                    if file_full_path.exists():
                        with open(file_full_path, 'w', encoding='utf-8') as f:
                            f.write(updates.content)
                        logger.info(f"Updated material file on disk: {file_full_path}")
                except Exception as file_error:
                    logger.error(f"Failed to update file on disk: {file_error}")
            
            if updates.subject is not None:
                material.subject = updates.subject
                updated_fields.append("subject")
            
            if updates.grade is not None:
                material.grade = updates.grade
                updated_fields.append("grade")
            
            if updates.topic is not None:
                material.topic = updates.topic
                updated_fields.append("topic")
            
            if updates.status is not None:
                material.status = updates.status
                updated_fields.append("status")
            
            # Update timestamp
            material.updated_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(material)
            
            logger.info(
                f"Material {material_id} updated by {current_user.id}. "
                f"Updated fields: {', '.join(updated_fields)}"
            )
            
            # Return updated material with permissions
            response_data = await get_material_with_permissions(
                material, str(current_user.id), db
            )
            response_data["content"] = material.content
            
            return JSONResponse(content=response_data)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating material: {e}", exc_info=True)
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update material"
            )


@app.delete(
    "/api/materials/{material_id}",
    response_model=MaterialDeleteResponse,
    summary="Delete material",
    description="Delete material (only by owner)"
)
async def delete_material(
    material_id: str = PathParam(description="Material UUID"),
    current_user: User = Depends(get_current_user),
):
    """Delete material (only owner can delete)."""
    async for db in get_db():
        try:
            # Get material
            result = await db.execute(
                select(Material).where(Material.id == material_id)
            )
            material = result.scalar_one_or_none()
            
            if not material:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Material not found"
                )
            
            # Check ownership
            if not await check_material_ownership(material_id, str(current_user.id), db):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You don't have permission to delete this material"
                )
            
            # Store file path for deletion
            file_path = material.file_path
            
            # Delete from database
            await db.delete(material)
            await db.commit()
            
            # Optionally delete file from disk
            try:
                file_full_path = storage.base_path / file_path
                if file_full_path.exists():
                    file_full_path.unlink()
                    logger.info(f"Deleted material file from disk: {file_full_path}")
            except Exception as file_error:
                logger.warning(f"Failed to delete file from disk: {file_error}")
                # Don't fail the request if file deletion fails
            
            logger.info(
                f"Material {material_id} deleted by {current_user.id}"
            )
            
            return MaterialDeleteResponse(
                success=True,
                message="Material deleted successfully"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting material: {e}", exc_info=True)
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete material"
            )




@app.post(
    "/api/materials/bulk-classify",
    response_model=dict,
    summary="Bulk classify materials",
    description="Re-classify existing materials using AI"
)
async def bulk_classify_materials(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of materials to classify"),
    current_user: User = Depends(get_current_user)
):
    """Re-classify existing materials using AI."""
    async for db in get_db():
        try:
            # Get materials that need classification (no subject or generic subject)
            result = await db.execute(
                select(Material)
                .where(
                    (Material.subject.is_(None)) | 
                    (Material.subject == "Other") |
                    (Material.subject == "Unclassified")
                )
                .limit(limit)
                .order_by(Material.created_at.desc())
            )
            materials = result.scalars().all()
            
            if not materials:
                return {
                    "message": "No materials need classification",
                    "classified": 0,
                    "errors": 0
                }
            
            from services.material_classifier import get_classifier_service
            classifier = get_classifier_service()
            classified_count = 0
            error_count = 0
            
            for material in materials:
                try:
                    # Classify material
                    classification = await classifier.classify_material(
                        content=material.content,
                        input_query=material.input_query or ""
                    )
                    
                    # Update material
                    material.subject = classification.subject
                    material.grade = classification.grade
                    material.topic = classification.topic
                    material.updated_at = datetime.utcnow()
                    
                    classified_count += 1
                    logger.info(
                        f"Classified material {material.id}: "
                        f"subject={classification.subject}, "
                        f"grade={classification.grade}, "
                        f"topic={classification.topic}"
                    )
                    
                except Exception as e:
                    logger.error(f"Error classifying material {material.id}: {e}")
                    error_count += 1
            
            # Commit all changes
            await db.commit()
            
            return {
                "message": f"Bulk classification completed",
                "total_processed": len(materials),
                "classified": classified_count,
                "errors": error_count
            }
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Error during bulk classification: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to classify materials"
            )


# =============================================================================
# core Proxy API - proxying requests to core with authentication
# Async flow: POST returns 202 + thread_id immediately (workaround for Vercel ~120 sec limit),
# processing runs in background; client polls GET /api/process/result/{thread_id}.
# =============================================================================

async def _run_process_in_background(
    thread_id: str,
    core_data: Dict[str, Any],
    files_data: Optional[List[tuple]],
) -> None:
    """Call core in background and save result to _process_results."""
    core_url = "http://core:8000/process"
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            form_data = {k: v for k, v in core_data.items()}
            response = await client.post(core_url, data=form_data, files=files_data)
            if response.status_code == 200:
                result = response.json()
                async with _process_results_lock:
                    _process_results[thread_id] = {"status": "completed", "result": result}
                logger.info(f"Background process completed for thread {thread_id}")
            else:
                async with _process_results_lock:
                    _process_results[thread_id] = {
                        "status": "failed",
                        "error": response.text,
                        "status_code": response.status_code,
                    }
                logger.error(f"core returned error for {thread_id}: {response.status_code} - {response.text}")
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to core for {thread_id}: {e}")
        async with _process_results_lock:
            _process_results[thread_id] = {"status": "failed", "error": str(e)}
    except Exception as e:
        logger.error(f"Error in background process for {thread_id}: {e}", exc_info=True)
        async with _process_results_lock:
            _process_results[thread_id] = {"status": "failed", "error": str(e)}


@app.post("/api/process")
async def proxy_to_core(
    question: str = Form(..., description="Question or task for processing"),
    settings: Optional[str] = Form(None, description="JSON processing settings"),
    thread_id: Optional[str] = Form(None, description="Thread ID (optional)"),
    images: Optional[List[UploadFile]] = File(None, description="Images for processing"),
    current_user: User = Depends(get_current_user)
):
    """
    Starts processing in core. Returns 202 and thread_id immediately (workaround for Vercel ~120 sec timeout).
    Fetch result via GET /api/process/result/{thread_id}.
    """
    import uuid
    new_thread_id = thread_id or str(uuid.uuid4())
    try:
        logger.info(f"Proxy request to core for user {current_user.id}, thread_id={new_thread_id}")
        core_data = {
            "question": question,
            "user_id": str(current_user.id),
            "thread_id": new_thread_id,
        }
        if settings:
            core_data["settings"] = settings

        files_data = None
        if images:
            files_data = []
            for image in images:
                content = await image.read()
                files_data.append(("images", (image.filename or "image", content, image.content_type or "application/octet-stream")))

        async with _process_results_lock:
            _process_results[new_thread_id] = {"status": "pending"}

        asyncio.create_task(_run_process_in_background(new_thread_id, core_data, files_data))

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"thread_id": new_thread_id, "message": "Processing started. Poll GET /api/process/result/{thread_id} for result."},
        )
    except Exception as e:
        logger.error(f"Error starting process: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start process: {str(e)}",
        )


@app.get("/api/process/result/{thread_id}")
async def get_process_result(thread_id: str = PathParam(..., description="Thread ID from 202 response")):
    """
    Poll result after POST /api/process (202).
    Returns 202 if still processing, 200 with result when ready, 200 with error on failure.
    """
    async with _process_results_lock:
        entry = _process_results.get(thread_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown thread_id or result expired")
    if entry["status"] == "pending":
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"thread_id": thread_id, "status": "pending"})
    if entry["status"] == "completed":
        return JSONResponse(status_code=status.HTTP_200_OK, content=entry["result"])
    if entry["status"] == "failed":
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "thread_id": thread_id,
                "error": entry.get("error", "Unknown error"),
                "status_code": entry.get("status_code"),
            },
        )
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Invalid result state")


@app.get(
    "/api/user/my-stats",
    response_model=UserStatsResponse,
    summary="Get my statistics",
    description="Get statistics about current user's materials"
)
async def get_my_stats(
    current_user: User = Depends(get_current_user),
):
    """Get user statistics for materials."""
    async for db in get_db():
        try:
            # Count total number of user materials
            total_materials_result = await db.execute(
                select(func.count()).select_from(
                    select(Material).where(Material.author_id == current_user.id).subquery()
                )
            )
            total_materials = total_materials_result.scalar()
            
            # Count published materials
            published_materials_result = await db.execute(
                select(func.count()).select_from(
                    select(Material).where(
                        Material.author_id == current_user.id,
                        Material.status == "published"
                    ).subquery()
                )
            )
            published_materials = published_materials_result.scalar()
            
            # Count drafts
            draft_materials_result = await db.execute(
                select(func.count()).select_from(
                    select(Material).where(
                        Material.author_id == current_user.id,
                        Material.status == "draft"
                    ).subquery()
                )
            )
            draft_materials = draft_materials_result.scalar()
            
            # Statistics by subjects
            subjects_result = await db.execute(
                select(
                    Material.subject,
                    func.count(Material.id).label('count')
                )
                .where(Material.author_id == current_user.id)
                .group_by(Material.subject)
                .order_by(func.count(Material.id).desc())
            )
            subjects = [
                {"subject": row.subject or "Unknown", "count": row.count} 
                for row in subjects_result
            ]
            
            return UserStatsResponse(
                totalMaterials=total_materials,
                publishedMaterials=published_materials,
                draftMaterials=draft_materials,
                subjects=subjects
            )
            
        except Exception as e:
            logger.error(f"Error getting user stats: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get user statistics"
            )


def main():
    """Main entry point for running the server."""
    import uvicorn

    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
    )


if __name__ == "__main__":
    main()
