# article Service

The article Service manages the storage, organization, and export of generated educational materials. It provides comprehensive material management capabilities with authentication, content versioning, and multiple export formats.

## Service Overview

**Port**: 8001  
**Primary Role**: Material storage, management, and export functionality  
**Technology**: FastAPI + PostgreSQL + File System

### Key Features

- **Material Management**: Complete CRUD operations for educational content
- **Export Capabilities**: PDF and Markdown export with customizable templates
- **Content Versioning**: Track material changes and history
- **Search & Discovery**: Advanced content search and filtering
- **File Organization**: Thread and session-based content organization

## API Endpoints

### Material Management

#### Get All Published Materials (Public)
```http
GET /api/materials/all?page=1&page_size=20&subject=Mathematics&grade=Professional
```

**Response**:
```json
{
  "materials": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "author_id": "user-uuid",
      "author_wallet": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
      "thread_id": "thread-123",
      "session_id": "session-20251013_120000",
      "file_path": "path/to/material.md",
      "subject": "Mathematics",
      "grade": "Professional",
      "topic": "Linear Algebra",
      "content_hash": "8f3d9e2a1b4c5d6e...",
      "title": "Mathematics: Complete Guide for Beginners",
      "word_count": 487,
      "status": "published",
      "created_at": "2025-10-13T10:00:00Z",
      "updated_at": "2025-10-13T10:00:00Z"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

#### Get User's Materials
```http
GET /api/materials/my?status=draft&subject=Mathematics
Authorization: Bearer <JWT_TOKEN>
```

**Response**: Same format as above, but includes all user's materials (drafts, published, archived)

#### Get Specific Material
```http
GET /api/materials/{material_id}?include_content=true
```

**Response**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "author_id": "user-uuid",
  "author_wallet": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
  "thread_id": "thread-123",
  "session_id": "session-20251013_120000",
  "file_path": "path/to/material.md",
  "subject": "Mathematics",
  "grade": "Professional",
  "topic": "Linear Algebra",
  "content_hash": "8f3d9e2a1b4c5d6e...",
  "title": "Mathematics: Complete Guide for Beginners",
  "word_count": 487,
  "status": "published",
  "created_at": "2025-10-13T10:00:00Z",
  "updated_at": "2025-10-13T10:00:00Z",
  "can_edit": true,
  "content": "# Mathematics: Complete Guide for Beginners\n\n## Introduction\n\nMathematics is fundamental to understanding the world..."
}
```

#### Update Material
```http
PATCH /api/materials/{material_id}
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "title": "Updated Title",
  "content": "Updated content in markdown format",
  "subject": "Mathematics",
  "grade": "University",
  "topic": "Linear Algebra",
  "status": "published"
}
```

**Response**: Updated material object with new content and metadata

#### Delete Material
```http
DELETE /api/materials/{material_id}
Authorization: Bearer <JWT_TOKEN>
```

**Response**:
```json
{
  "success": true,
  "message": "Material deleted successfully"
}
```

### Statistics and Analytics

#### Get Subject Statistics
```http
GET /api/materials/stats/subjects
Authorization: Bearer <JWT_TOKEN>
```

**Response**:
```json
{
  "subjects": [
    {"subject": "Mathematics", "count": 15},
    {"subject": "Physics", "count": 8},
    {"subject": "Physics", "count": 3},
    {"subject": "Unknown", "count": 1}
  ]
}
```

### Export Functionality

#### Export to PDF
```http
POST /export/pdf/{thread_id}/{session_id}
Content-Type: application/json

{
  "include_materials": true,
  "include_questions": true,
  "include_answers": true,
  "template": "academic",
  "settings": {
    "page_size": "A4",
    "font_size": 12,
    "margins": "normal"
  }
}
```

**Response**: PDF file download or download URL

#### Export to Markdown
```http
POST /export/markdown/{thread_id}/{session_id}
Content-Type: application/json

{
  "include_materials": true,
  "include_questions": true,
  "include_answers": true,
  "format": "github",
  "include_toc": true
}
```

**Response**: Markdown file download or download URL

## Data Models

### Material Model

```python
class Material(Base):
    __tablename__ = "materials"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    author_id = Column(String, nullable=False, index=True)
    author_wallet = Column(String, nullable=False, index=True)
    thread_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    file_path = Column(String, nullable=False)
    
    # Content metadata
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False, index=True)
    word_count = Column(Integer, default=0)
    
    # Classification
    subject = Column(String, nullable=False, index=True)
    grade = Column(String, nullable=False, index=True)
    topic = Column(String, nullable=False, index=True)
    
    # Status and versioning
    status = Column(String, nullable=False, default="draft", index=True)
    version = Column(Integer, default=1)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index('idx_author_status', 'author_wallet', 'status'),
        Index('idx_subject_grade', 'subject', 'grade'),
        Index('idx_created_at', 'created_at'),
    )
```

### User Model

```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    wallet_address = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    email = Column(String, nullable=True)
    
    # Profile information
    learning_style = Column(String, default="visual")
    preferred_subjects = Column(JSON, default=list)
    difficulty_level = Column(String, default="intermediate")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
```

## File Organization

### Directory Structure

```
data/article/
├── {thread_id}/
│   ├── metadata.json
│   └── sessions/
│       └── {session_id}/
│           ├── session_metadata.json
│           ├── generated_material.md
│           ├── recognized_notes.md
│           ├── synthesized_material.md
│           ├── questions.md
│           └── questions_and_answers.md
```

### File Metadata

#### Thread Metadata
```json
{
  "thread_id": "thread-123",
  "user_id": "user-uuid",
  "wallet_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
  "created_at": "2025-10-13T10:00:00Z",
  "updated_at": "2025-10-13T10:00:00Z",
  "total_sessions": 5,
  "total_materials": 12
}
```

#### Session Metadata
```json
{
  "session_id": "session-20251013_120000",
  "thread_id": "thread-123",
  "created_at": "2025-10-13T10:00:00Z",
  "updated_at": "2025-10-13T10:00:00Z",
  "files": [
    "generated_material.md",
    "recognized_notes.md",
    "synthesized_material.md",
    "questions.md",
    "questions_and_answers.md"
  ],
  "status": "completed"
}
```

## Permission System

#### Access Control Matrix

| Material Status | Owner | Other Users | Anonymous |
|----------------|-------|-------------|-----------|
| `published`    | ✅    | ✅          | ✅        |
| `draft`        | ✅    | ❌          | ❌        |
| `archived`     | ✅    | ❌          | ❌        |

#### Permission Functions

```python
def check_material_ownership(user_wallet: str, material: Material) -> bool:
    """Check if user owns the material"""
    return user_wallet.lower() == material.author_wallet.lower()

def can_view_material(user_wallet: str, material: Material) -> bool:
    """Check if user can view the material"""
    if material.status == "published":
        return True
    return check_material_ownership(user_wallet, material)

def can_edit_material(user_wallet: str, material: Material) -> bool:
    """Check if user can edit the material"""
    return check_material_ownership(user_wallet, material)
```

## Export System

### PDF Export

The service provides comprehensive PDF export capabilities with multiple templates and customization options.

#### Export Templates

- **Academic**: University-style formatting with formal structure
- **Professional**: Business/corporate style with clean design
- **Minimalist**: Simple, clean design focused on content

#### PDF Configuration

```python
class PDFExportConfig:
    template: str = "academic"
    page_size: str = "A4"
    font_size: int = 12
    margins: str = "normal"
    include_toc: bool = True
    include_metadata: bool = True
    watermark: str = None
    header_footer: bool = True
```

#### PDF Generation Process

1. **Content Collection**: Gather all materials and metadata
2. **Template Selection**: Choose appropriate template
3. **Content Processing**: Convert Markdown to HTML
4. **PDF Generation**: Use WeasyPrint for PDF creation
5. **Quality Enhancement**: Optimize for print and digital viewing

### Markdown Export

Flexible Markdown export with multiple format options.

#### Export Formats

- **GitHub**: GitHub-flavored Markdown with enhanced features
- **GitLab**: GitLab-compatible Markdown formatting
- **Standard**: CommonMark standard compliance

#### Markdown Configuration

```python
class MarkdownExportConfig:
    format: str = "github"
    include_toc: bool = True
    include_metadata: bool = True
    code_highlighting: bool = True
    math_notation: bool = True
    cross_references: bool = True
```

## Content Management

### Content Versioning

The service tracks material changes and maintains version history.

```python
class MaterialVersion(Base):
    __tablename__ = "material_versions"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    material_id = Column(UUID, ForeignKey("materials.id"), nullable=False)
    version = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String, nullable=False)
    change_summary = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, nullable=False)
```

### Content Validation

```python
def validate_material_content(content: str) -> ValidationResult:
    """Validate material content"""
    
    # Length validation
    if len(content) > 1_000_000:  # 1MB limit
        return ValidationResult(valid=False, error="Content too large")
    
    # Markdown validation
    if not is_valid_markdown(content):
        return ValidationResult(valid=False, error="Invalid Markdown format")
    
    # Security validation
    if contains_malicious_content(content):
        return ValidationResult(valid=False, error="Content contains prohibited elements")
    
    return ValidationResult(valid=True)
```

## Search and Discovery

### Search Functionality

The service provides advanced search capabilities for discovering educational materials.

#### Search Parameters

```python
class MaterialSearchParams:
    query: str = None
    subject: str = None
    grade: str = None
    author: str = None
    date_from: datetime = None
    date_to: datetime = None
    status: str = "published"
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 20
```

#### Search Implementation

```python
async def search_materials(params: MaterialSearchParams) -> SearchResult:
    """Search materials with advanced filtering"""
    
    query = select(Material).where(Material.status == params.status)
    
    # Text search
    if params.query:
        query = query.where(
            or_(
                Material.title.ilike(f"%{params.query}%"),
                Material.content.ilike(f"%{params.query}%"),
                Material.topic.ilike(f"%{params.query}%")
            )
        )
    
    # Filter by subject
    if params.subject:
        query = query.where(Material.subject == params.subject)
    
    # Filter by grade
    if params.grade:
        query = query.where(Material.grade == params.grade)
    
    # Date range filtering
    if params.date_from:
        query = query.where(Material.created_at >= params.date_from)
    if params.date_to:
        query = query.where(Material.created_at <= params.date_to)
    
    # Sorting
    if params.sort_by == "created_at":
        query = query.order_by(Material.created_at.desc() if params.sort_order == "desc" else Material.created_at.asc())
    elif params.sort_by == "title":
        query = query.order_by(Material.title.asc() if params.sort_order == "asc" else Material.title.desc())
    
    # Pagination
    offset = (params.page - 1) * params.page_size
    query = query.offset(offset).limit(params.page_size)
    
    result = await database.execute(query)
    materials = result.scalars().all()
    
    return SearchResult(
        materials=materials,
        total=await count_materials(params),
        page=params.page,
        page_size=params.page_size
    )
```

## Performance Optimization

### Caching Strategy

The service implements multi-level caching for optimal performance.

#### Cache Layers

1. **Application Cache**: In-memory caching for frequently accessed data
2. **Redis Cache**: Distributed caching for session data and user profiles
3. **Database Query Cache**: Query result caching for expensive operations
4. **File System Cache**: Cached file operations and metadata

#### Cache Implementation

```python
class CacheManager:
    def __init__(self):
        self.redis_client = redis.Redis(host="localhost", port=6379, db=0)
        self.local_cache = {}
        self.cache_ttl = 3600  # 1 hour
    
    async def get_material(self, material_id: str) -> Optional[Material]:
        """Get material with caching"""
        
        # Check local cache first
        if material_id in self.local_cache:
            return self.local_cache[material_id]
        
        # Check Redis cache
        cached_data = await self.redis_client.get(f"material:{material_id}")
        if cached_data:
            material = Material.parse_raw(cached_data)
            self.local_cache[material_id] = material
            return material
        
        # Fetch from database
        material = await database.fetch_material(material_id)
        if material:
            # Cache the result
            await self.redis_client.setex(
                f"material:{material_id}",
                self.cache_ttl,
                material.json()
            )
            self.local_cache[material_id] = material
        
        return material
```

### Database Optimization

#### Indexing Strategy

```sql
-- Material table indexes
CREATE INDEX idx_materials_author_status ON materials(author_wallet, status);
CREATE INDEX idx_materials_subject_grade ON materials(subject, grade);
CREATE INDEX idx_materials_created_at ON materials(created_at);
CREATE INDEX idx_materials_content_hash ON materials(content_hash);

-- User table indexes
CREATE INDEX idx_users_wallet_address ON users(wallet_address);
CREATE INDEX idx_users_created_at ON users(created_at);

-- Session table indexes
CREATE INDEX idx_sessions_thread_id ON sessions(thread_id);
CREATE INDEX idx_sessions_created_at ON sessions(created_at);
```

#### Query Optimization

- **Connection Pooling**: Efficient database connection management
- **Query Batching**: Batch multiple queries for better performance
- **Lazy Loading**: Load related data only when needed
- **Query Analysis**: Regular query performance analysis and optimization

## Monitoring and Observability

### Metrics Collection

The service provides comprehensive metrics for monitoring and analysis.

#### Key Metrics

- **Request Metrics**: Request rates, response times, error rates
- **Material Metrics**: Creation rates, update frequencies, export usage
- **User Metrics**: Active users, authentication success rates
- **System Metrics**: Database performance, file system usage

#### Metrics Implementation

```python
class MetricsCollector:
    def __init__(self):
        self.prometheus_client = PrometheusClient()
    
    def record_material_created(self, subject: str, grade: str):
        """Record material creation metric"""
        self.prometheus_client.counter(
            "materials_created_total",
            labels={"subject": subject, "grade": grade}
        ).inc()
    
    def record_export_request(self, format: str, template: str):
        """Record export request metric"""
        self.prometheus_client.counter(
            "exports_requested_total",
            labels={"format": format, "template": template}
        ).inc()
    
    def record_api_response_time(self, endpoint: str, duration: float):
        """Record API response time"""
        self.prometheus_client.histogram(
            "api_response_time_seconds",
            labels={"endpoint": endpoint}
        ).observe(duration)
```

### Health Monitoring

#### Health Check Endpoints

```python
@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    
    health_status = {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "checks": {}
    }
    
    # Database health
    try:
        await database.execute("SELECT 1")
        health_status["checks"]["database"] = "ok"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "error"
    
    # File system health
    try:
        test_file = Path("data/article/health_check")
        test_file.write_text("health check")
        test_file.unlink()
        health_status["checks"]["filesystem"] = "ok"
    except Exception as e:
        health_status["checks"]["filesystem"] = f"error: {str(e)}"
        health_status["status"] = "error"
    
    # Redis health
    try:
        await redis_client.ping()
        health_status["checks"]["redis"] = "ok"
    except Exception as e:
        health_status["checks"]["redis"] = f"error: {str(e)}"
        health_status["status"] = "error"
    
    return health_status
```

## Next Steps

- [Prompt Config Service](./prompt-studio.md) - Dynamic prompt generation
- [Materials API Guide](../guides/materials-api.md) - Complete API usage guide
- [Export System Guide](../guides/export-system.md) - Export functionality guide
