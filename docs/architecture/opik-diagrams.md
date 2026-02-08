# Opik — integration architecture diagrams

This document contains Mermaid diagrams showing **how Opik is integrated** into Base Library: where traces/spans are created, what data is sent, and how it can be used for Online Evaluation.

## 1) Opik in the overall architecture

```mermaid
graph TB
  subgraph "Client Layer"
    WEB[Web Frontend]
    API_CLIENT[API Client]
  end

  subgraph "API Gateway"
    NGINX[Nginx/Load Balancer]
  end

  subgraph "Core Services"
    CORE["core service<br/>(LangGraph)"]
    ARTICLE[article service]
    PROMPT[Prompt Config service]
  end

  subgraph "Data Layer"
    PG[(PostgreSQL)]
    REDIS[(Redis)]
    FS[File Storage]
  end

  subgraph "External / Observability"
    OPIK[Opik (Comet)<br/>Traces / Spans / Evaluation]
    LLM[LLM Providers<br/>OpenAI / DeepSeek / ...]
  end

  WEB --> NGINX --> CORE
  API_CLIENT --> NGINX --> CORE

  CORE --> PROMPT
  CORE --> ARTICLE
  CORE --> PG
  ARTICLE --> PG
  ARTICLE --> FS
  PROMPT --> PG
  PROMPT --> REDIS

  CORE --> LLM
  CORE --> OPIK
```

## 2) Trace lifecycle: `workflow_execution`

```mermaid
sequenceDiagram
  autonumber
  participant U as User/Client
  participant G as API Gateway
  participant C as core (GraphManager)
  participant O as Opik
  participant N as Workflow Nodes

  U->>G: POST /process (question + images?)
  G->>C: route request

  alt fresh run (no state.values)
    C->>O: create_trace(name="workflow_execution", thread_id, metadata, input)
    O-->>C: trace handle
    C->>C: cfg.metadata.opik_trace = trace
  else continuation (resume)
    C->>O: span hitl_feedback (if query present)
  end

  loop node execution (LangGraph)
    C->>N: call node(state, cfg)
    N->>O: create_span(name="node_<node_name>")
    N->>O: update_span(input/output/metadata) for LLM call, usage, latency
    N->>O: optional spans (external_prompt_config, multimodal, ...)
  end

  C->>O: artifacts_save span (per node when saving artifacts)
  C->>O: update_trace(output={status, snippet, response})
```

## 3) Span map: what is logged where

```mermaid
flowchart TB
  T["Trace: workflow_execution<br/>(thread_id)"]

  subgraph "Per-node spans"
    S1[node_generating_content]
    S2[node_recognition_handwritten]
    S3[node_synthesis_material]
    S4[node_edit_material]
    S5[node_generating_questions]
    S6[node_answer_question]
  end

  subgraph "Cross-cutting spans"
    P[external_prompt_config]
    A[artifacts_save]
    H[hitl_feedback]
  end

  T --> S1
  T --> S2
  T --> S3
  T --> S4
  T --> S5
  T --> S6

  T --> P
  T --> A
  T --> H
```

## 4) Online Evaluation: turning traces into metrics

```mermaid
flowchart LR
  PROD[Production traffic] --> TR["Opik Traces<br/>workflow_execution"]
  TR -->|sampling| RULES["Online Evaluation Rules<br/>(judge model + metric)"]
  RULES --> RES["Evaluation Results<br/>scores / labels"]
  RES --> DASH["Dashboards / Alerts"]
  RES --> QA["Quality monitoring<br/>regressions, drift"]
```

## 5) HITL: user feedback as part of the trace

```mermaid
sequenceDiagram
  autonumber
  participant U as User
  participant C as core (GraphManager)
  participant O as Opik

  U->>C: resume / feedback text
  C->>O: span hitl_feedback (node_name=current_node, feedback)
  O-->>C: stored
```

