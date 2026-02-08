# Prompt Config Service

The Prompt Config Service provides dynamic prompt generation and personalization capabilities for the Base Library Backend. It manages user profiles, prompt templates, and context-aware prompt generation to optimize AI interactions.

## Service Overview

**Port**: 8002  
**Primary Role**: Dynamic prompt generation and personalization  
**Technology**: FastAPI + PostgreSQL + Redis

### Key Features

- **User Profile Management**: Comprehensive user preference tracking
- **Dynamic Prompt Generation**: Context-aware prompt creation
- **Template Management**: Configurable prompt templates
- **Caching System**: High-performance prompt caching
- **A/B Testing**: Prompt optimization through experimentation
- **Multi-language Support**: Internationalization capabilities

## API Endpoints

### User Profile Management

#### Create User Profile
```http
POST /api/profiles
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "user_id": "user-uuid",
  "username": "john_doe",
  "email": "john@example.com",
  "learning_style": "visual",
  "preferred_subjects": ["Mathematics", "Physics"],
  "difficulty_level": "intermediate",
  "language_preference": "en"
}
```

**Response**:
```json
{
  "id": "user-uuid",
  "username": "john_doe",
  "email": "john@example.com",
  "learning_style": "visual",
  "preferred_subjects": ["Mathematics", "Physics"],
  "difficulty_level": "intermediate",
  "language_preference": "en",
  "created_at": "2025-10-13T10:00:00Z",
  "updated_at": "2025-10-13T10:00:00Z"
}
```

#### Get User Profile
```http
GET /api/profiles/{user_id}
Authorization: Bearer <JWT_TOKEN>
```

**Response**: User profile object

#### Update User Profile
```http
PATCH /api/profiles/{user_id}
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "learning_style": "kinesthetic",
  "preferred_subjects": ["Mathematics", "Physics", "Chemistry"],
  "difficulty_level": "advanced"
}
```

**Response**: Updated user profile object

#### Delete User Profile
```http
DELETE /api/profiles/{user_id}
Authorization: Bearer <JWT_TOKEN>
```

**Response**:
```json
{
  "success": true,
  "message": "Profile deleted successfully"
}
```

### Prompt Template Management

#### Get Available Templates
```http
GET /api/prompts/templates?category=content_generation&language=en
```

**Response**:
```json
{
  "templates": [
    {
      "id": "content_gen_visual",
      "name": "Visual Content Generation",
      "category": "content_generation",
      "description": "Template optimized for visual learners",
      "language": "en",
      "variables": ["topic", "difficulty", "learning_style"],
      "is_active": true,
      "created_at": "2025-10-13T10:00:00Z"
    }
  ]
}
```

#### Get Template Details
```http
GET /api/prompts/templates/{template_id}
```

**Response**:
```json
{
  "id": "content_gen_visual",
  "name": "Visual Content Generation",
  "category": "content_generation",
  "template": "You are an expert educational content creator specializing in visual learning. Create engaging content about {topic} for {difficulty} level students with a {learning_style} learning preference. Include diagrams, charts, and visual examples where appropriate.",
  "variables": ["topic", "difficulty", "learning_style"],
  "metadata": {
    "target_audience": "visual_learners",
    "content_type": "educational",
    "optimization_goal": "engagement"
  },
  "is_active": true,
  "created_at": "2025-10-13T10:00:00Z",
  "updated_at": "2025-10-13T10:00:00Z"
}
```

#### Create Custom Template
```http
POST /api/prompts/templates
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "name": "Custom Math Template",
  "category": "content_generation",
  "template": "Create a comprehensive math lesson about {topic} for {grade} students. Focus on {learning_style} learning with practical examples.",
  "variables": ["topic", "grade", "learning_style"],
  "metadata": {
    "subject": "mathematics",
    "optimization_goal": "comprehension"
  }
}
```

### Prompt Generation

#### Generate Personalized Prompt
```http
POST /api/prompts/generate
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "user_id": "user-uuid",
  "context": {
    "topic": "quantum mechanics",
    "difficulty": "beginner",
    "content_type": "lesson",
    "session_id": "session-123"
  },
  "template_id": "content_gen_visual",
  "custom_variables": {
    "additional_context": "Focus on practical applications"
  }
}
```

**Response**:
```json
{
  "prompt_id": "prompt-uuid",
  "generated_prompt": "You are an expert educational content creator specializing in visual learning. Create engaging content about quantum mechanics for beginner level students with a visual learning preference. Focus on practical applications. Include diagrams, charts, and visual examples where appropriate.",
  "template_used": "content_gen_visual",
  "variables_applied": {
    "topic": "quantum mechanics",
    "difficulty": "beginner",
    "learning_style": "visual",
    "additional_context": "Focus on practical applications"
  },
  "cache_key": "prompt:user-uuid:content_gen_visual:hash123",
  "expires_at": "2025-10-13T11:00:00Z"
}
```

#### Batch Prompt Generation
```http
POST /api/prompts/generate/batch
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "requests": [
    {
      "user_id": "user-uuid",
      "context": {"topic": "algebra", "difficulty": "intermediate"},
      "template_id": "content_gen_visual"
    },
    {
      "user_id": "user-uuid",
      "context": {"topic": "geometry", "difficulty": "advanced"},
      "template_id": "content_gen_visual"
    }
  ]
}
```

**Response**:
```json
{
  "results": [
    {
      "prompt_id": "prompt-uuid-1",
      "generated_prompt": "...",
      "template_used": "content_gen_visual",
      "variables_applied": {"topic": "algebra", "difficulty": "intermediate"}
    },
    {
      "prompt_id": "prompt-uuid-2",
      "generated_prompt": "...",
      "template_used": "content_gen_visual",
      "variables_applied": {"topic": "geometry", "difficulty": "advanced"}
    }
  ],
  "total_generated": 2,
  "cache_hits": 0,
  "cache_misses": 2
}
```

### A/B Testing

#### Create A/B Test
```http
POST /api/ab-tests
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "name": "Visual vs Textual Prompts",
  "description": "Compare visual and textual prompt effectiveness",
  "template_a": "content_gen_visual",
  "template_b": "content_gen_textual",
  "traffic_split": 0.5,
  "target_metrics": ["engagement", "comprehension", "completion_rate"],
  "duration_days": 30
}
```

**Response**:
```json
{
  "test_id": "ab-test-uuid",
  "name": "Visual vs Textual Prompts",
  "status": "active",
  "traffic_split": 0.5,
  "participants": 0,
  "created_at": "2025-10-13T10:00:00Z",
  "expires_at": "2025-11-12T10:00:00Z"
}
```

#### Get A/B Test Results
```http
GET /api/ab-tests/{test_id}/results
Authorization: Bearer <JWT_TOKEN>
```

**Response**:
```json
{
  "test_id": "ab-test-uuid",
  "status": "completed",
  "results": {
    "template_a": {
      "participants": 150,
      "metrics": {
        "engagement": 0.85,
        "comprehension": 0.78,
        "completion_rate": 0.92
      }
    },
    "template_b": {
      "participants": 150,
      "metrics": {
        "engagement": 0.72,
        "comprehension": 0.81,
        "completion_rate": 0.88
      }
    }
  },
  "winner": "template_a",
  "confidence_level": 0.95,
  "statistical_significance": true
}
```

## Data Models

### User Profile Model

```python
class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, nullable=True)
    email = Column(String, nullable=True)
    
    # Learning preferences
    learning_style = Column(String, default="visual")  # visual, auditory, kinesthetic, reading
    preferred_subjects = Column(JSON, default=list)
    difficulty_level = Column(String, default="intermediate")  # beginner, intermediate, advanced
    language_preference = Column(String, default="en")
    
    # Content preferences
    content_length_preference = Column(String, default="medium")  # short, medium, long
    example_preference = Column(String, default="practical")  # theoretical, practical, mixed
    format_preference = Column(String, default="structured")  # structured, conversational, technical
    
    # Behavioral data
    total_sessions = Column(Integer, default=0)
    average_session_duration = Column(Float, default=0.0)
    preferred_time_of_day = Column(String, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active = Column(DateTime, nullable=True)
```

### Prompt Template Model

```python
class PromptTemplate(Base):
    __tablename__ = "prompt_templates"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False, index=True)  # content_generation, question_generation, etc.
    description = Column(Text, nullable=True)
    
    # Template content
    template = Column(Text, nullable=False)
    variables = Column(JSON, nullable=False)  # List of variable names
    metadata = Column(JSON, default=dict)  # Additional template metadata
    
    # Configuration
    language = Column(String, default="en", index=True)
    is_active = Column(Boolean, default=True, index=True)
    priority = Column(Integer, default=0)  # Higher priority templates are preferred
    
    # Usage statistics
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, default=0.0)
    average_rating = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String, nullable=True)
```

### Generated Prompt Model

```python
class GeneratedPrompt(Base):
    __tablename__ = "generated_prompts"
    
    id = Column(UUID, primary_key=True, default=uuid4)
    user_id = Column(UUID, ForeignKey("user_profiles.id"), nullable=False, index=True)
    template_id = Column(String, ForeignKey("prompt_templates.id"), nullable=False)
    
    # Generated content
    generated_prompt = Column(Text, nullable=False)
    variables_applied = Column(JSON, nullable=False)
    context = Column(JSON, nullable=True)
    
    # Caching
    cache_key = Column(String, nullable=True, index=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Usage tracking
    usage_count = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    
    # Performance metrics
    response_time = Column(Float, nullable=True)
    user_rating = Column(Integer, nullable=True)  # 1-5 scale
    effectiveness_score = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

## Prompt Generation Engine

### Template Processing

The service uses a sophisticated template processing engine that combines user profiles, context, and templates to generate personalized prompts.

```python
class PromptGenerator:
    def __init__(self):
        self.template_engine = Jinja2TemplateEngine()
        self.cache_manager = CacheManager()
        self.profile_analyzer = ProfileAnalyzer()
    
    async def generate_prompt(
        self,
        user_id: str,
        template_id: str,
        context: Dict[str, Any],
        custom_variables: Dict[str, Any] = None
    ) -> GeneratedPrompt:
        """Generate personalized prompt"""
        
        # Get user profile
        profile = await self.get_user_profile(user_id)
        
        # Get template
        template = await self.get_template(template_id)
        
        # Check cache first
        cache_key = self.generate_cache_key(user_id, template_id, context)
        cached_prompt = await self.cache_manager.get(cache_key)
        if cached_prompt:
            return cached_prompt
        
        # Prepare variables
        variables = await self.prepare_variables(profile, context, custom_variables)
        
        # Generate prompt
        generated_prompt = self.template_engine.render(template.template, variables)
        
        # Create prompt record
        prompt = GeneratedPrompt(
            user_id=user_id,
            template_id=template_id,
            generated_prompt=generated_prompt,
            variables_applied=variables,
            context=context,
            cache_key=cache_key,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        
        # Save and cache
        await self.save_prompt(prompt)
        await self.cache_manager.set(cache_key, prompt, ttl=3600)
        
        return prompt
    
    async def prepare_variables(
        self,
        profile: UserProfile,
        context: Dict[str, Any],
        custom_variables: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Prepare variables for template rendering"""
        
        variables = {
            # User profile variables
            "learning_style": profile.learning_style,
            "difficulty_level": profile.difficulty_level,
            "language_preference": profile.language_preference,
            "content_length_preference": profile.content_length_preference,
            "example_preference": profile.example_preference,
            "format_preference": profile.format_preference,
            
            # Context variables
            "topic": context.get("topic", ""),
            "difficulty": context.get("difficulty", profile.difficulty_level),
            "content_type": context.get("content_type", "lesson"),
            "session_id": context.get("session_id", ""),
            
            # Custom variables
            **(custom_variables or {})
        }
        
        # Apply profile-based transformations
        variables = await self.profile_analyzer.transform_variables(profile, variables)
        
        return variables
```

### Template Engine

The service uses Jinja2 for flexible template processing with custom filters and functions.

```python
class Jinja2TemplateEngine:
    def __init__(self):
        self.env = Environment(
            loader=DictLoader({}),
            extensions=['jinja2.ext.do']
        )
        
        # Add custom filters
        self.env.filters['format_difficulty'] = self.format_difficulty
        self.env.filters['format_learning_style'] = self.format_learning_style
        self.env.filters['add_examples'] = self.add_examples
    
    def render(self, template: str, variables: Dict[str, Any]) -> str:
        """Render template with variables"""
        template_obj = self.env.from_string(template)
        return template_obj.render(**variables)
    
    def format_difficulty(self, difficulty: str) -> str:
        """Format difficulty level for prompts"""
        difficulty_map = {
            "beginner": "introductory level suitable for newcomers",
            "intermediate": "intermediate level for those with basic knowledge",
            "advanced": "advanced level for experienced learners"
        }
        return difficulty_map.get(difficulty, difficulty)
    
    def format_learning_style(self, style: str) -> str:
        """Format learning style for prompts"""
        style_map = {
            "visual": "visual learners who benefit from diagrams, charts, and visual examples",
            "auditory": "auditory learners who prefer spoken explanations and discussions",
            "kinesthetic": "kinesthetic learners who learn through hands-on activities and practical examples",
            "reading": "reading/writing learners who prefer text-based explanations and written materials"
        }
        return style_map.get(style, style)
    
    def add_examples(self, content: str, preference: str) -> str:
        """Add examples based on user preference"""
        if preference == "practical":
            return f"{content}\n\nInclude practical, real-world examples that demonstrate the concepts in action."
        elif preference == "theoretical":
            return f"{content}\n\nFocus on theoretical foundations and mathematical derivations."
        else:
            return f"{content}\n\nProvide a balanced mix of theoretical concepts and practical examples."
```

## Caching System

### Multi-Level Caching

The service implements a sophisticated caching system to optimize performance and reduce database load.

```python
class CacheManager:
    def __init__(self):
        self.redis_client = redis.Redis(host="localhost", port=6379, db=0)
        self.local_cache = {}
        self.cache_ttl = {
            "prompts": 3600,      # 1 hour
            "profiles": 1800,     # 30 minutes
            "templates": 7200,    # 2 hours
            "ab_tests": 300       # 5 minutes
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        
        # Check local cache first
        if key in self.local_cache:
            return self.local_cache[key]
        
        # Check Redis cache
        cached_data = await self.redis_client.get(key)
        if cached_data:
            try:
                value = json.loads(cached_data)
                self.local_cache[key] = value
                return value
            except json.JSONDecodeError:
                return None
        
        return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        
        # Determine TTL
        if ttl is None:
            ttl = self.cache_ttl.get(key.split(":")[0], 3600)
        
        # Set in local cache
        self.local_cache[key] = value
        
        # Set in Redis cache
        try:
            serialized_value = json.dumps(value, default=str)
            await self.redis_client.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.error(f"Failed to set cache key {key}: {e}")
            return False
    
    def generate_cache_key(self, *args) -> str:
        """Generate cache key from arguments"""
        key_parts = [str(arg) for arg in args]
        return ":".join(key_parts)
```

### Cache Invalidation

```python
class CacheInvalidator:
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
    
    async def invalidate_user_cache(self, user_id: str):
        """Invalidate all cache entries for a user"""
        pattern = f"prompts:{user_id}:*"
        keys = await self.cache_manager.redis_client.keys(pattern)
        if keys:
            await self.cache_manager.redis_client.delete(*keys)
        
        # Clear local cache
        for key in list(self.cache_manager.local_cache.keys()):
            if key.startswith(f"prompts:{user_id}:"):
                del self.cache_manager.local_cache[key]
    
    async def invalidate_template_cache(self, template_id: str):
        """Invalidate cache entries for a template"""
        pattern = f"*:{template_id}:*"
        keys = await self.cache_manager.redis_client.keys(pattern)
        if keys:
            await self.cache_manager.redis_client.delete(*keys)
```

## A/B Testing Framework

### Test Management

The service includes a comprehensive A/B testing framework for optimizing prompt effectiveness.

```python
class ABTestManager:
    def __init__(self):
        self.database = Database()
        self.metrics_collector = MetricsCollector()
    
    async def create_test(
        self,
        name: str,
        description: str,
        template_a: str,
        template_b: str,
        traffic_split: float = 0.5,
        target_metrics: List[str] = None,
        duration_days: int = 30
    ) -> ABTest:
        """Create new A/B test"""
        
        test = ABTest(
            name=name,
            description=description,
            template_a=template_a,
            template_b=template_b,
            traffic_split=traffic_split,
            target_metrics=target_metrics or ["engagement", "comprehension"],
            status="active",
            expires_at=datetime.utcnow() + timedelta(days=duration_days)
        )
        
        await self.database.save(test)
        return test
    
    async def assign_user_to_test(self, user_id: str, test_id: str) -> str:
        """Assign user to A or B variant"""
        
        # Use consistent hashing for stable assignment
        hash_input = f"{user_id}:{test_id}"
        hash_value = hashlib.md5(hash_input.encode()).hexdigest()
        hash_int = int(hash_value[:8], 16)
        
        test = await self.database.get_test(test_id)
        if hash_int % 100 < test.traffic_split * 100:
            variant = "A"
        else:
            variant = "B"
        
        # Record assignment
        assignment = TestAssignment(
            test_id=test_id,
            user_id=user_id,
            variant=variant,
            assigned_at=datetime.utcnow()
        )
        
        await self.database.save(assignment)
        return variant
    
    async def record_metric(
        self,
        test_id: str,
        user_id: str,
        metric_name: str,
        value: float
    ):
        """Record metric for A/B test"""
        
        metric = TestMetric(
            test_id=test_id,
            user_id=user_id,
            metric_name=metric_name,
            value=value,
            recorded_at=datetime.utcnow()
        )
        
        await self.database.save(metric)
    
    async def analyze_results(self, test_id: str) -> TestResults:
        """Analyze A/B test results"""
        
        test = await self.database.get_test(test_id)
        assignments = await self.database.get_assignments(test_id)
        metrics = await self.database.get_metrics(test_id)
        
        # Calculate metrics for each variant
        variant_a_metrics = {}
        variant_b_metrics = {}
        
        for metric in metrics:
            assignment = next(
                (a for a in assignments if a.user_id == metric.user_id),
                None
            )
            if assignment:
                if assignment.variant == "A":
                    if metric.metric_name not in variant_a_metrics:
                        variant_a_metrics[metric.metric_name] = []
                    variant_a_metrics[metric.metric_name].append(metric.value)
                else:
                    if metric.metric_name not in variant_b_metrics:
                        variant_b_metrics[metric.metric_name] = []
                    variant_b_metrics[metric.metric_name].append(metric.value)
        
        # Calculate statistics
        results = TestResults(
            test_id=test_id,
            variant_a_metrics=self.calculate_statistics(variant_a_metrics),
            variant_b_metrics=self.calculate_statistics(variant_b_metrics),
            statistical_significance=self.calculate_significance(
                variant_a_metrics, variant_b_metrics
            ),
            winner=self.determine_winner(variant_a_metrics, variant_b_metrics)
        )
        
        return results
```

## Performance Optimization

### Database Optimization

#### Indexing Strategy

```sql
-- User profiles indexes
CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_user_profiles_learning_style ON user_profiles(learning_style);
CREATE INDEX idx_user_profiles_difficulty ON user_profiles(difficulty_level);

-- Prompt templates indexes
CREATE INDEX idx_prompt_templates_category ON prompt_templates(category);
CREATE INDEX idx_prompt_templates_language ON prompt_templates(language);
CREATE INDEX idx_prompt_templates_active ON prompt_templates(is_active);

-- Generated prompts indexes
CREATE INDEX idx_generated_prompts_user ON generated_prompts(user_id);
CREATE INDEX idx_generated_prompts_template ON generated_prompts(template_id);
CREATE INDEX idx_generated_prompts_cache_key ON generated_prompts(cache_key);
CREATE INDEX idx_generated_prompts_created_at ON generated_prompts(created_at);
```

#### Query Optimization

```python
class OptimizedQueries:
    async def get_user_profile_with_cache(self, user_id: str) -> Optional[UserProfile]:
        """Get user profile with caching"""
        
        # Check cache first
        cache_key = f"profile:{user_id}"
        cached_profile = await self.cache_manager.get(cache_key)
        if cached_profile:
            return UserProfile.parse_obj(cached_profile)
        
        # Query database
        profile = await self.database.execute(
            select(UserProfile)
            .where(UserProfile.id == user_id)
            .options(selectinload(UserProfile.preferences))
        )
        
        if profile:
            # Cache the result
            await self.cache_manager.set(cache_key, profile.dict())
        
        return profile
    
    async def get_templates_by_category(self, category: str) -> List[PromptTemplate]:
        """Get templates by category with caching"""
        
        cache_key = f"templates:{category}"
        cached_templates = await self.cache_manager.get(cache_key)
        if cached_templates:
            return [PromptTemplate.parse_obj(t) for t in cached_templates]
        
        # Query database
        templates = await self.database.execute(
            select(PromptTemplate)
            .where(
                and_(
                    PromptTemplate.category == category,
                    PromptTemplate.is_active == True
                )
            )
            .order_by(PromptTemplate.priority.desc())
        )
        
        # Cache the result
        await self.cache_manager.set(cache_key, [t.dict() for t in templates])
        
        return templates
```

### Memory Management

```python
class MemoryManager:
    def __init__(self):
        self.local_cache = {}
        self.max_cache_size = 1000
        self.cache_access_times = {}
    
    def cleanup_cache(self):
        """Clean up least recently used cache entries"""
        if len(self.local_cache) > self.max_cache_size:
            # Sort by access time and remove oldest entries
            sorted_items = sorted(
                self.cache_access_times.items(),
                key=lambda x: x[1]
            )
            
            # Remove 20% of oldest entries
            remove_count = len(sorted_items) // 5
            for key, _ in sorted_items[:remove_count]:
                if key in self.local_cache:
                    del self.local_cache[key]
                if key in self.cache_access_times:
                    del self.cache_access_times[key]
    
    def get_with_tracking(self, key: str) -> Optional[Any]:
        """Get value with access time tracking"""
        if key in self.local_cache:
            self.cache_access_times[key] = time.time()
            return self.local_cache[key]
        return None
```

## Monitoring and Observability

### Metrics Collection

```python
class MetricsCollector:
    def __init__(self):
        self.prometheus_client = PrometheusClient()
    
    def record_prompt_generation(self, template_id: str, user_id: str, duration: float):
        """Record prompt generation metrics"""
        self.prometheus_client.histogram(
            "prompt_generation_duration_seconds",
            labels={"template_id": template_id}
        ).observe(duration)
        
        self.prometheus_client.counter(
            "prompts_generated_total",
            labels={"template_id": template_id}
        ).inc()
    
    def record_cache_hit(self, cache_type: str):
        """Record cache hit"""
        self.prometheus_client.counter(
            "cache_hits_total",
            labels={"cache_type": cache_type}
        ).inc()
    
    def record_cache_miss(self, cache_type: str):
        """Record cache miss"""
        self.prometheus_client.counter(
            "cache_misses_total",
            labels={"cache_type": cache_type}
        ).inc()
    
    def record_ab_test_participation(self, test_id: str, variant: str):
        """Record A/B test participation"""
        self.prometheus_client.counter(
            "ab_test_participants_total",
            labels={"test_id": test_id, "variant": variant}
        ).inc()
```

### Health Monitoring

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
    
    # Redis health
    try:
        await redis_client.ping()
        health_status["checks"]["redis"] = "ok"
    except Exception as e:
        health_status["checks"]["redis"] = f"error: {str(e)}"
        health_status["status"] = "error"
    
    # Cache performance
    cache_hit_rate = await calculate_cache_hit_rate()
    health_status["checks"]["cache_performance"] = {
        "hit_rate": cache_hit_rate,
        "status": "ok" if cache_hit_rate > 0.8 else "warning"
    }
    
    return health_status
```

## Next Steps

- [core Service](./core.md) - Main orchestration service
- [article Service](./article.md) - Material storage and export
- [API Reference](../api-reference/prompt-studio.md) - Complete API documentation
- [A/B Testing Guide](../guides/ab-testing.md) - A/B testing implementation
