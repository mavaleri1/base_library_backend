# core Core Service

The core Core Service is the main orchestration service that handles educational content generation using LangGraph workflows. It coordinates AI model interactions, manages workflow state, and provides the primary API for content generation.

## Service Overview

**Port**: 8000  
**Primary Role**: Content generation orchestration and workflow management  
**Technology**: FastAPI + LangGraph + PostgreSQL

### Key Features

- **LangGraph Workflow Engine**: Sophisticated content generation pipeline
- **Multi-AI Provider Support**: OpenAI, DeepSeek, and compatible services
- **Human-in-the-Loop (HITL)**: Interactive content refinement
- **SecurityGuard Integration**: AI-powered security validation
- **State Management**: Persistent workflow state and checkpointing
- **Image Processing**: OCR and image recognition capabilities

## API Endpoints

### Core Workflow Endpoints

#### Process Educational Content
```http
POST /process
Content-Type: application/json

{
  "thread_id": "optional-thread-id",
  "message": "Explain quantum mechanics for beginners",
  "image_paths": ["path/to/image1.jpg", "path/to/image2.jpg"]
}
```

**Response**:
```json
{
  "thread_id": "uuid-thread-id",
  "result": [
    "📚 **Materials ready:**\n\n📚 [Generated material](http://link)",
    "📸 For improved material quality, you can add notes or images.\n\nOptions:\n• Upload photos of notes or insert text\n• Write 'skip' to continue"
  ]
}
```

#### Upload Images for Processing
```http
POST /upload-images/{thread_id}
Content-Type: multipart/form-data

files: [image1.jpg, image2.png]
```

**Response**:
```json
{
  "thread_id": "uuid",
  "uploaded_files": [
    "/tmp/threads/uuid/image1.jpg",
    "/tmp/threads/uuid/image2.jpg"
  ],
  "message": "Successfully uploaded 2 images"
}
```

#### Get Thread State
```http
GET /state/{thread_id}
```

**Response**:
```json
{
  "thread_id": "uuid",
  "state": {
    "input_content": "Explain quantum mechanics",
    "generated_material": "...",
    "recognized_notes": "...",
    "synthesized_material": "...",
    "questions": ["Q1", "Q2"],
    "questions_and_answers": [],
    "edit_count": 1,
    "image_paths": []
  },
  "current_step": {
    "node": "recognition_handwritten",
    "description": "Handwritten note recognition"
  }
}
```

#### Delete Thread
```http
DELETE /thread/{thread_id}
```

**Response**:
```json
{
  "success": true,
  "message": "Thread deleted successfully"
}
```

### HITL Configuration Endpoints

#### Get HITL Configuration
```http
GET /api/hitl/{thread_id}
```

**Response**:
```json
{
  "recognition_handwritten": true,
  "edit_material": true,
  "generating_questions": true
}
```

#### Update Node Configuration
```http
PATCH /api/hitl/{thread_id}/node/{node_name}
Content-Type: application/json

{
  "enabled": false
}
```

#### Reset HITL Configuration
```http
POST /api/hitl/{thread_id}/reset
```

#### Bulk Configuration Update
```http
POST /api/hitl/{thread_id}/bulk
Content-Type: application/json

{
  "enable_all": false
}
```

### Health and Status

#### Health Check
```http
GET /health
```

**Response**:
```json
{
  "status": "ok",
  "timestamp": "2025-01-24T10:30:00Z",
  "version": "1.0.0"
}
```

## Workflow Architecture

### Workflow Nodes

The core service implements a 7-node workflow for comprehensive content generation:

```mermaid
graph TD
    A[Input Processing] --> B[Content Generation]
    B --> C{Images Provided?}
    C -->|Yes| D[Image Recognition]
    C -->|No| E[HITL: Add Images?]
    E -->|Yes| D
    E -->|No| F[Material Synthesis]
    D --> F
    F --> G[HITL: Edit Material]
    G -->|Edit| F
    G -->|Done| H[Question Generation]
    H --> I[HITL: Review Questions]
    I -->|Edit| H
    I -->|Done| J[Answer Generation]
    J --> K[Complete]
```

### Node Details

#### 1. Input Processing Node
- **Purpose**: Validates and processes user requests
- **Security**: SecurityGuard validation and threat detection
- **Output**: Sanitized input content and extracted metadata

#### 2. Content Generation Node
- **Purpose**: Creates educational material using AI models
- **AI Models**: Configurable provider selection (OpenAI, DeepSeek)
- **Output**: Structured educational content in Markdown format

#### 3. Image Recognition Node (HITL)
- **Purpose**: Processes uploaded images for text extraction
- **Technology**: Vision API for OCR processing
- **HITL Behavior**: Pauses if no images provided, allows user to add images

#### 4. Material Synthesis Node
- **Purpose**: Combines generated content with recognized text
- **Process**: Intelligent content merging and structure optimization
- **Output**: Enhanced educational material

#### 5. Edit Material Node (HITL)
- **Purpose**: Interactive content refinement
- **HITL Behavior**: Iterative editing with user feedback
- **Features**: Multiple edit cycles, improvement suggestions

#### 6. Question Generation Node (HITL)
- **Purpose**: Creates assessment questions
- **HITL Behavior**: Question review and modification
- **Types**: Multiple choice, short answer, problem solving

#### 7. Answer Generation Node
- **Purpose**: Provides comprehensive answers
- **Process**: Parallel answer generation for efficiency
- **Output**: Detailed explanations with examples

## Configuration

### Model Configuration

The service supports multiple AI providers with configurable models:

```yaml
# configs/graph.yaml
models:
  default:
    provider: deepseek
    model_name: "deepseek-chat"
    temperature: 0.1
    max_tokens: 4000
  
  vision:
    provider: openai
    model_name: "gpt-4o-mini"
    temperature: 0.1
    max_tokens: 2000
  
  structured:
    provider: openai
    model_name: "gpt-4o-mini"
    temperature: 0.1
    max_tokens: 2000
    response_format: "json_object"
```

### Provider Configuration

```yaml
# configs/providers.yaml
providers:
  openai:
    api_key: "${OPENAI_API_KEY}"
    base_url: "https://api.openai.com/v1"
    timeout: 30
  
  deepseek:
    api_key: "${DEEPSEEK_API_KEY}"
    base_url: "https://api.deepseek.com/v1"
    timeout: 30
```

### Prompt Configuration

```yaml
# configs/prompts.yaml
prompts:
  content_generation:
    system: |
      You are an expert educational content creator specializing in creating 
      clear, engaging, and comprehensive learning materials. Your goal is to 
      help students understand complex topics through well-structured content.
    
    user_template: |
      Create educational content about: {topic}
      Target audience: {audience}
      Difficulty level: {difficulty}
      Include: {requirements}
```

## Security Features

### SecurityGuard Integration

The service includes comprehensive security measures:

```python
class SecurityGuard:
    async def validate_input(self, content: str) -> SecurityResult:
        """Validate user input for security threats"""
        
        # Length validation
        if len(content) < 10:
            return SecurityResult(valid=False, reason="Content too short")
        
        # AI-based threat detection
        threat_score = await self.detect_threats(content)
        if threat_score > 0.85:
            return SecurityResult(valid=False, reason="Potential threat detected")
        
        # Content cleaning
        cleaned_content = await self.clean_content(content)
        
        return SecurityResult(valid=True, content=cleaned_content)
```

### Input Validation

- **Content Length**: Minimum 10 characters, maximum 10,000 characters
- **Character Validation**: Allowed character set validation
- **Pattern Detection**: Suspicious pattern identification
- **Educational Context**: Educational relevance validation

## State Management

### Workflow State

The service maintains comprehensive workflow state:

```python
class WorkflowState:
    # Input data
    input_content: str
    image_paths: List[str]
    thread_id: str
    session_id: str
    
    # Generated content
    generated_material: str
    recognized_notes: str
    synthesized_material: str
    questions: List[str]
    questions_and_answers: List[Dict]
    
    # Workflow control
    current_node: str
    edit_count: int
    hitl_config: Dict
    
    # Metadata
    created_at: datetime
    updated_at: datetime
    user_id: str
```

### State Persistence

- **Database Storage**: PostgreSQL for persistent state
- **Checkpointing**: Regular state saves during workflow execution
- **Recovery**: Automatic recovery from last checkpoint
- **Cleanup**: Automatic cleanup of completed workflows

## Performance Optimization

### Parallel Processing

The service optimizes performance through:

- **Parallel Answer Generation**: Simultaneous answer creation for multiple questions
- **Async Operations**: Non-blocking I/O operations
- **Connection Pooling**: Efficient database connection management
- **Caching**: Frequently accessed data caching

### Resource Management

- **Memory Optimization**: Efficient memory usage patterns
- **CPU Optimization**: Workload distribution across nodes
- **I/O Optimization**: Efficient file and network operations
- **Timeout Management**: Proper timeout handling for external services

## Monitoring & Observability

### Metrics Collection

The service provides comprehensive metrics:

- **Workflow Metrics**: Node execution times, success rates
- **AI Metrics**: Token usage, model performance, costs
- **User Metrics**: Request rates, user engagement
- **System Metrics**: CPU, memory, disk usage

### Logging

Structured logging with correlation IDs:

```python
logger.info(
    "Workflow node completed",
    extra={
        "thread_id": thread_id,
        "node": node_name,
        "duration": execution_time,
        "user_id": user_id,
        "correlation_id": correlation_id
    }
)
```

### Health Monitoring

- **Health Checks**: Regular health endpoint monitoring
- **Dependency Checks**: External service availability
- **Performance Monitoring**: Response time and throughput tracking
- **Error Tracking**: Comprehensive error logging and alerting

## Integration Points

### External Services

The service integrates with:

- **article Service**: Material storage and retrieval
- **Prompt Config Service**: Dynamic prompt generation
- **AI Providers**: OpenAI, DeepSeek, and compatible services

### Service Communication

```python
# article Service Integration
async def store_material(thread_id: str, content: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{article_SERVICE_URL}/api/materials",
            json={"thread_id": thread_id, "content": content},
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        return response.json()

# Prompt Config Service Integration
async def get_personalized_prompt(user_id: str, context: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{PROMPT_CONFIG_SERVICE_URL}/api/prompts/generate",
            params={"user_id": user_id, "context": context},
            headers={"Authorization": f"Bearer {jwt_token}"}
        )
        return response.json()
```

## Error Handling

### Error Types

1. **Input Validation Errors**: Invalid or malicious input
2. **AI Service Errors**: Model failures or rate limits
3. **Workflow Errors**: Node execution failures
4. **Storage Errors**: Database or file system issues
5. **Network Errors**: Service communication failures

### Error Recovery

- **Retry Logic**: Automatic retry for transient errors
- **Fallback Strategies**: Alternative processing paths
- **Graceful Degradation**: Partial functionality maintenance
- **User Notification**: Clear error messages and guidance

## Development & Testing

### Local Development

```bash
# Install dependencies
pip install -e .

# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost/core"
export OPENAI_API_KEY="your-api-key"

# Run migrations
alembic upgrade head

# Start development server
uvicorn core.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing

```bash
# Run unit tests
pytest tests/

# Run integration tests
pytest tests/integration/

# Run with coverage
pytest --cov=core tests/
```

## Next Steps

- [article Service](./article.md) - Material storage and export
- [Prompt Config Service](./prompt-studio.md) - Dynamic prompt generation
- [API Reference](../api-reference/core.md) - Complete API documentation
- [HITL Workflow Guide](../guides/hitl-workflow.md) - Human-in-the-Loop implementation
