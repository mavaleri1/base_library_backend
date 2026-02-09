# Opik (Opic) — observability and online evaluation integration

This document describes how **Opik** (Comet’s observability platform for LLM applications) is integrated into the Base Library Backend: **what it is**, **how it’s wired into the system**, and **how it helps** in operations and product development.

> Naming note: you may see “Opic” in discussions, but the code and the official SDK use **Opik**.

## What is Opik

**Opik** is an observability platform for LLM/AI systems that collects:

- **Traces**: workflow/business-process executions (in our case: a LangGraph workflow run correlated by `thread_id`).
- **Spans**: steps within a trace (graph nodes, external calls, artifact saving, HITL feedback).
- **Input/Output** and **metadata**: what you need for search, analysis, debugging, and quality evaluation.
- (Optional) **Online Evaluation**: automated rules to evaluate production traces (judge models, metrics, sampling).

## How Opik is integrated into our system

### Integration point in the core workflow

Opik is integrated into the **core service** and is tied to the lifecycle of a `thread_id`:

- **Create a trace** on a “fresh run” (a new workflow) in `GraphManager`.
- **Attach the trace** into `cfg["metadata"]["opik_trace"]` so nodes can create spans.
- **Create one span per node** in the node base class (`BaseWorkflowNode`).
- **Log LLM calls** (messages, response, tokens, cost, latency) inside individual nodes.
- **Log external interactions** (Prompt Config Service, artifact saving, HITL feedback).
- **Update `trace.output`** during workflow finalization (success/interrupt) so the result is visible directly in the Traces table.

### Where this is implemented (key files)

- `Base-Library-Backend/core/services/opik_client.py`
  - SDK initialization (`Opik(...)`) and configuration (host/api_key/project).
  - Methods: `create_trace()`, `update_trace()`, `create_span()`, `update_span_data()`.
  - Logging for LLM calls (`log_llm_call()`), multimodal data (`log_multimodal_data()`), external services, and HITL feedback.
- `Base-Library-Backend/core/core/graph_manager.py`
  - Creates the `workflow_execution` trace and stores it in `active_traces[thread_id]`.
  - Injects `opik_trace` into `cfg["metadata"]`.
  - Creates an `artifacts_save` span when saving artifacts.
  - Updates `trace.output` in `_finalize_workflow()` (status/summary/snippet/response).
  - On continuation, logs HITL feedback as a `hitl_feedback` span.
- `Base-Library-Backend/core/nodes/base.py`
  - Creates a `node_<node_name>` span for the current node via `_get_opik_span()`.
  - Logs Prompt Config Service calls via the `external_prompt_config` span.
- `Base-Library-Backend/core/services/opik_langchain_callback.py`
  - LangChain callback (an additional path for automatic LLM-result logging).
- `Base-Library-Backend/test_opik_connection.py`
  - Simple smoke test: create a trace/span and log an LLM call.

## What data is sent to Opik

### Trace: `workflow_execution`

Created when a new workflow starts:

- **name**: `workflow_execution`
- **thread_id**: LangGraph thread identifier (our primary correlator)
- **metadata** (example):
  - `query` (short preview)
  - `image_count`
  - `session_id`
  - (optional) `learning_style`, `difficulty`, `learning_goal`, `subject`, `volume` from `user_settings`
- **input** (for the Traces table):
  - `query` (up to 500 chars)
  - `image_count`
  - `session_id`
  - (optional) `user_id`
  - (optional) `user_settings`: dict with `learning_style`, `learning_goal`, `difficulty`, `subject`, `volume` (only non-empty values)

At the end of the workflow, the trace is updated with `output` so the UI shows a meaningful result without opening spans:

- on **interrupt/HITL**: `status="interrupted"`, `next_step="waiting_for_user"`, `response/snippet` (when available)
- on **successful completion**: `status="completed"`, `summary`, `response/snippet`

### Spans (main types)

- **Graph nodes**: `node_<node_name>` (e.g. `node_generating_content`, `node_recognition_handwritten`, `node_synthesis_material`, …)
- **Prompt Config**: `external_prompt_config` (latency, which context keys were used)
- **LLM call**: data is written via `update_span` (messages/response/tokens/cost/latency)
- **Multimodal**: `image_paths` / `image_count` (no binary payloads)
- **Artifacts**: `artifacts_save` (which node, success, latency)
- **HITL feedback**: `hitl_feedback` (preview + full text within limits)

## How Opik helps

- **Production debugging**: quickly locate problematic runs by `thread_id`, inspect inputs/outputs, and see where quality dropped or latency spikes occur.
- **Cost and performance analytics**: tokens/cost/latency per node and per request type.
- **Quality control**: Online Evaluation can automatically score a sampled subset of production traces, helping catch regressions after prompt/model changes.
- **HITL observability**: understand where users intervene more often, what feedback they provide, and at which workflow steps.
- **Auditability and reproducibility**: traces/spans provide a single shared context for discussing specific cases.

## Configuration (enable/disable)

The integration is **graceful**: if Opik is not configured, the workflow continues to run and tracing is disabled.

Settings come from environment variables (see `Base-Library-Backend/core/config/settings.py`):

- `OPIK_API_KEY`: access key
- `OPIK_PROJECT_NAME`: project name (default: `base-library`)
- `OPIK_API_BASE_URL`: base URL (default: `https://api.opik.com`; when custom, it’s passed as `host`)
- `OPIK_ENABLED`: `true/false` to enable/disable

