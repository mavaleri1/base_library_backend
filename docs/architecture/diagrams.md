# Architecture Diagrams

This page demonstrates how to use Mermaid diagrams in Base Library documentation.

## Application Structure

```mermaid
graph TD
    A[App] --> B[Layout]
    B --> C[Navigation]
    B --> D[Main Content]
    D --> E[Page Components]
    E --> F[Feature Components]
    F --> G[UI Components]
    G --> H[Base Components]
```

## Backend Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        A[React App]
        B[UI Components]
    end
    
    subgraph "API Gateway"
        D[Express Server]
        E[Authentication]
        F[Rate Limiting]
    end
    
    subgraph "Microservices"
        G[Core Service]
        H[Article Service]
        I[Prompt Studio]
        J[AI Service]
    end
    
    subgraph "Data Layer"
        K[PostgreSQL]
        L[Redis Cache]
        M[File Storage]
    end
    
    subgraph "External Services"
        N[AI Models]
    end
    
    A --> D
    B --> D
    D --> E
    D --> F
    D --> G
    D --> H
    D --> I
    G --> K
    H --> K
    I --> K
    J --> K
    G --> L
    H --> L
    I --> L
    J --> M
    J --> N
```

## Content Generation Workflow

```mermaid
flowchart LR
    A[User Input] --> B[Content Request]
    B --> C[AI Processing]
    C --> D[Content Generation]
    D --> E[Quality Check]
    E --> F{Valid?}
    F -->|Yes| G[Save Content]
    F -->|No| H[Regenerate]
    H --> C
    G --> I[Return to User]
    I --> J[User Review]
    J --> K{Approve?}
    K -->|Yes| L[Publish]
    K -->|No| M[Edit Request]
    M --> B
```

## Database Schema

```mermaid
erDiagram
    USERS {
        uuid id PK
        string user_id
        string username
        timestamp created_at
    }
    
    ARTICLES {
        uuid id PK
        uuid author_id FK
        string title
        text content
        string status
        timestamp created_at
    }
    
    PROMPTS {
        uuid id PK
        string name
        text template
        json parameters
        timestamp created_at
    }
    
    USERS ||--o{ ARTICLES : creates
    PROMPTS ||--o{ ARTICLES : uses
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "Production Environment"
        subgraph "Load Balancer"
            LB[Nginx]
        end
        
        subgraph "Application Servers"
            APP1[App Server 1]
            APP2[App Server 2]
            APP3[App Server 3]
        end
        
        subgraph "Database Cluster"
            DB1[Primary DB]
            DB2[Replica DB]
            CACHE[Redis Cluster]
        end
        
        subgraph "Storage"
            S3[Object Storage]
            CDN[CDN]
        end
    end
    
    subgraph "External Services"
        AI[AI Services]
        MONITOR[Monitoring]
    end
    
    LB --> APP1
    LB --> APP2
    LB --> APP3
    
    APP1 --> DB1
    APP2 --> DB1
    APP3 --> DB1
    
    DB1 --> DB2
    APP1 --> CACHE
    APP2 --> CACHE
    APP3 --> CACHE
    
    APP1 --> S3
    APP2 --> S3
    APP3 --> S3
    
    S3 --> CDN
    
    APP1 --> AI
    APP2 --> AI
    APP3 --> AI
    
    MONITOR --> APP1
    MONITOR --> APP2
    MONITOR --> APP3
```
