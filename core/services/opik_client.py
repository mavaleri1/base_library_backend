"""
Opik client for tracing LLM calls and workflow execution.

Uses the official Opik Python SDK for tracing.
Documentation: https://www.comet.com/docs/opik/reference/python-sdk/overview
"""

import logging
from typing import Optional, Dict, Any, List
from opik import Opik

from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class OpikClient:
    """
    Client for Opik observability platform.
    
    Wrapper around the official Opik Python SDK for convenient use
    in LangGraph workflow context.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.client: Optional[Opik] = None
        
        if self.settings.is_opik_configured():
            try:
                # Initialize Opik client
                # Documentation: https://www.comet.com/docs/opik/reference/python-sdk/overview
                # Correct signature: Opik(project_name, workspace, host, api_key, ...)
                # host is used instead of api_base_url
                
                # Convert api_base_url to host format
                # If api_base_url = "https://api.opik.com", host should be "https://www.comet.com/opik/api"
                # Usually default host is used, so we just pass api_key and project_name
                host = None
                if self.settings.opik_api_base_url and self.settings.opik_api_base_url != "https://api.opik.com":
                    # If custom URL is used, convert it to host format
                    # Opik expects format like "https://www.comet.com/opik/api"
                    host = self.settings.opik_api_base_url.replace("/api", "") if "/api" in self.settings.opik_api_base_url else self.settings.opik_api_base_url
                
                # Create Opik client with correct parameters
                # Do NOT use api_base_url — it is not in the API!
                init_params = {
                    "project_name": self.settings.opik_project_name,
                    "api_key": self.settings.opik_api_key,
                }
                # Add host only if not None
                if host:
                    init_params["host"] = host
                
                self.client = Opik(**init_params)
                logger.info("✅ Opik client initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Opik client: {e}")
                logger.error(f"   API Key: {'SET' if self.settings.opik_api_key else 'NOT SET'}")
                logger.error(f"   Project: {self.settings.opik_project_name}")
                logger.error(f"   Host: {self.settings.opik_api_base_url}")
                import traceback
                logger.debug(traceback.format_exc())
                self.client = None
        else:
            logger.warning("⚠️ Opik not configured, tracing disabled")
    
    def is_enabled(self) -> bool:
        """Check if Opik is enabled and configured"""
        return self.client is not None
    
    def create_trace(
        self,
        name: str,
        thread_id: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        input: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """Create a new trace for workflow execution."""
        if not self.is_enabled():
            return None

        try:
            # Opik trace() accepts: name, thread_id, metadata, input, output, tags, ...
            trace_metadata = metadata or {}
            if user_id:
                trace_metadata["user_id"] = user_id

            kwargs = {
                "name": name,
                "thread_id": thread_id,
                "metadata": trace_metadata,
            }
            if input is not None:
                kwargs["input"] = input

            trace = self.client.trace(**kwargs)
            return trace
        except Exception as e:
            logger.error(f"Failed to create trace: {e}")
            return None

    def update_trace(
        self,
        trace: Any,
        output: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update an existing trace with output (e.g. after workflow completes).
        Uses trace.update() or trace.end() so that output is sent to Opik API and shown in UI.
        """
        if not self.is_enabled() or not trace or output is None:
            return
        try:
            # Opik SDK: use update() or end() to send output to API (assigning trace.output is not enough)
            if hasattr(trace, "update"):
                trace.update(output=output)
                logger.debug("Updated trace output via trace.update()")
            elif hasattr(trace, "end"):
                trace.end(output=output)
                logger.debug("Updated trace output via trace.end()")
            elif hasattr(trace, "output"):
                trace.output = output
                logger.debug("Set trace.output (fallback)")
            else:
                logger.warning(
                    "Cannot update trace output: trace has no 'update', 'end' or 'output'"
                )
                return
            # Ensure buffered data is sent (important for async/short-lived flows)
            if hasattr(self.client, "flush"):
                self.client.flush()
        except Exception as e:
            logger.error(f"Failed to update trace output: {e}")
            logger.debug("%s", __import__("traceback").format_exc())

    def create_span(
        self,
        trace: Any,
        name: str,
        node_name: str,
        input_data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """Create a span for a workflow node"""
        if not self.is_enabled() or not trace:
            return None
        
        try:
            span = trace.span(
                name=name,
                metadata={
                    "node_name": node_name,
                    **(metadata or {})
                }
            )
            return span
        except Exception as e:
            logger.error(f"Failed to create span: {e}")
            return None
    
    def log_llm_call(
        self,
        span: Any,
        model_name: str,
        provider: str,
        messages: List[Dict[str, Any]],
        response: str,
        tokens_used: Optional[Dict[str, int]] = None,
        cost: Optional[float] = None,
        latency: Optional[float] = None
    ) -> None:
        """Log LLM call to Opik"""
        if not self.is_enabled() or not span:
            return
        
        try:
            # Span object has update_span() methods for updating data
            # For logging LLM calls it's better to use update_span() with input/output
            # Or create a new span with type='llm'
            # Try to update the existing span
            span_metadata = span.metadata if hasattr(span, 'metadata') else {}
            span_metadata.update({
                "model_name": model_name,
                "provider": provider,
                "latency_ms": latency
            })
            
            # Update span with LLM data
            # Use update_span via client, since span may not have a direct update method
            if hasattr(span, 'id') and hasattr(span, 'trace_id'):
                self.client.update_span(
                    id=span.id,
                    trace_id=span.trace_id,
                    parent_span_id=getattr(span, 'parent_span_id', None),
                    project_name=self.settings.opik_project_name,
                    input={
                        "model": model_name,
                        "provider": provider,
                        "messages": messages
                    },
                    output={
                        "response": response,
                        "tokens": tokens_used or {},
                        "cost": cost,
                        "latency_ms": latency
                    },
                    metadata=span_metadata,
                    model=model_name,
                    provider=provider,
                    total_cost=cost,
                    usage=tokens_used
                )
            else:
                # If span has no id/trace_id, log via metadata
                logger.warning("Span object doesn't have id/trace_id, cannot update LLM call data")
        except Exception as e:
            logger.error(f"Failed to log LLM call: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def log_multimodal_data(
        self,
        span: Any,
        image_paths: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log multimodal data (images) to Opik"""
        if not self.is_enabled() or not span:
            return
        
        try:
            # Update span with multimodal data info
            # Use update_span to add input with image paths
            if hasattr(span, 'id') and hasattr(span, 'trace_id'):
                span_metadata = span.metadata if hasattr(span, 'metadata') else {}
                span_metadata.update({
                    "attachment_count": len(image_paths),
                    **(metadata or {})
                })
                
                self.client.update_span(
                    id=span.id,
                    trace_id=span.trace_id,
                    parent_span_id=getattr(span, 'parent_span_id', None),
                    project_name=self.settings.opik_project_name,
                    input={"image_paths": image_paths},
                    metadata=span_metadata
                )
            else:
                logger.warning("Span object doesn't have id/trace_id, cannot log multimodal data")
        except Exception as e:
            logger.error(f"Failed to log multimodal data: {e}")
            import traceback
            logger.debug(traceback.format_exc())

    def update_span_data(
        self,
        span: Any,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        metadata_extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update span with input/output and optional metadata (e.g. for external service calls)."""
        if not self.is_enabled() or not span:
            return
        try:
            if hasattr(span, "id") and hasattr(span, "trace_id"):
                span_metadata = getattr(span, "metadata", None) or {}
                if metadata_extra:
                    span_metadata.update(metadata_extra)
                kwargs = {
                    "id": span.id,
                    "trace_id": span.trace_id,
                    "project_name": self.settings.opik_project_name,
                    "parent_span_id": getattr(span, "parent_span_id", None),
                }
                if input_data is not None:
                    kwargs["input"] = input_data
                if output_data is not None:
                    kwargs["output"] = output_data
                if span_metadata:
                    kwargs["metadata"] = span_metadata
                self.client.update_span(**kwargs)
        except Exception as e:
            logger.debug(f"Failed to update span data: {e}")

    def log_external_service_call(
        self,
        trace: Any,
        service_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        latency_ms: Optional[float] = None,
    ) -> Optional[Any]:
        """Create a span for an external service call (e.g. Prompt Config, Artifacts) and log input/output."""
        if not self.is_enabled() or not trace:
            return None
        span = self.create_span(
            trace=trace,
            name=f"external_{service_name}",
            node_name=service_name,
            metadata={"service": service_name},
        )
        if not span:
            return None
        meta = {"latency_ms": latency_ms} if latency_ms is not None else {}
        self.update_span_data(
            span,
            input_data=input_data,
            output_data=output_data,
            metadata_extra=meta,
        )
        return span

    def log_hitl_feedback(
        self,
        trace: Any,
        node_name: str,
        feedback_text: str,
        metadata_extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log HITL user feedback as a span on the trace (for observability)."""
        if not self.is_enabled() or not trace:
            return
        try:
            span = self.create_span(
                trace=trace,
                name="hitl_feedback",
                node_name=node_name,
                metadata={
                    "hitl_node": node_name,
                    "feedback_preview": (feedback_text[:500] + "…") if len(feedback_text) > 500 else feedback_text,
                    **(metadata_extra or {}),
                },
            )
            if span:
                self.update_span_data(
                    span,
                    input_data={"node": node_name, "feedback": feedback_text[:2000]},
                    output_data={"logged": True},
                )
        except Exception as e:
            logger.debug(f"Failed to log HITL feedback: {e}")


# Global Opik client instance
_opik_client: Optional[OpikClient] = None


def get_opik_client() -> OpikClient:
    """Get global Opik client instance"""
    global _opik_client
    if _opik_client is None:
        _opik_client = OpikClient()
    return _opik_client

