"""Settings configuration for Artifacts Service."""

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Artifacts Service settings."""

    model_config = SettingsConfigDict(
        env_prefix="ARTIFACTS_",
        env_file=[".env.local", ".env"],
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore additional fields
    )

    # Server settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8001, description="Server port")

    # Storage settings
    data_path: Path = Field(
        default=Path("./data/artifacts"), description="Base path for artifacts storage"
    )

    # Limits
    max_file_size: int = Field(
        default=10485760,  # 10MB
        description="Maximum file size in bytes",
    )
    max_files_per_thread: int = Field(
        default=100, description="Maximum number of files per thread"
    )

    # Security
    allowed_content_types: list[str] = Field(
        default=["text/markdown", "application/json", "text/plain"],
        description="Allowed content types",
    )
    max_path_depth: int = Field(default=3, description="Maximum path depth for files")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    
    # Database settings
    database_url: Optional[str] = Field(
        default=None,
        description="PostgreSQL database URL",
        alias="DATABASE_URL"
    )
    
    # Authentication settings
    bot_api_key: Optional[str] = Field(
        default=None,
        description="API key for bot service authentication"
    )
    jwt_secret_key: str = Field(
        default="your-secret-key-keep-it-secret-and-change-in-production",
        description="Secret key for JWT token generation"
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT encoding algorithm"
    )
    jwt_expiration_minutes: int = Field(
        default=60 * 24,  # 24 hours
        description="JWT token expiration time in minutes"
    )
    auth_code_expiration_minutes: int = Field(
        default=5,
        description="Auth code expiration time in minutes"
    )

    # Clerk authentication settings
    clerk_jwks_url: Optional[str] = Field(
        default=None,
        description="Clerk JWKS URL for JWT verification"
    )
    clerk_issuer: Optional[str] = Field(
        default=None,
        description="Clerk JWT issuer"
    )
    clerk_audience: Optional[str] = Field(
        default=None,
        description="Clerk JWT audience (optional)"
    )

    # CORS origins (comma-separated, e.g. for Vercel: https://app.vercel.app)
    cors_origins: str = Field(
        default="http://localhost:5174,http://localhost:3001,http://127.0.0.1:5174,http://127.0.0.1:3000,http://127.0.0.1:3001",
        description="Comma-separated allowed CORS origins (ARTIFACTS_CORS_ORIGINS or CORS_ORIGINS)",
    )


# Global settings instance
_settings = None

def get_settings() -> Settings:
    """Get global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

# Backward compatibility
settings = get_settings()
