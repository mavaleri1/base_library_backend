"""
Opik callback handler for LangChain integration.

Uses LangChain callback system for automatic tracing of LLM calls.
Documentation: https://www.comet.com/docs/opik/integrations/langchain
"""

from typing import Any, Dict, List, Optional
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from .opik_client import get_opik_client


class OpikLangChainCallback(BaseCallbackHandler):
    """Callback handler for LangChain to log to Opik"""
    
    def __init__(self, span, node_name: str):
        super().__init__()
        self.opik = get_opik_client()
        self.span = span
        self.node_name = node_name
        self.messages: List[Dict[str, Any]] = []
        self.response: Optional[str] = None
        self.start_time: Optional[float] = None
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any
    ) -> None:
        """Called when LLM starts"""
        import time
        self.start_time = time.time()
        
        # Convert prompts to messages format
        self.messages = [{"role": "user", "content": prompt} for prompt in prompts]
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM ends"""
        import time
        
        if not self.span or not self.opik.is_enabled():
            return
        
        # Extract response
        if response.generations and len(response.generations) > 0:
            self.response = response.generations[0][0].text
        
        # Calculate latency
        latency = None
        if self.start_time:
            latency = (time.time() - self.start_time) * 1000  # ms
        
        # Extract token usage
        token_usage = {}
        if response.llm_output and "token_usage" in response.llm_output:
            token_usage = response.llm_output["token_usage"]
        
        # Log to Opik
        self.opik.log_llm_call(
            span=self.span,
            model_name=serialized.get("name", "unknown"),
            provider=self._extract_provider(serialized),
            messages=self.messages,
            response=self.response or "",
            tokens_used=token_usage,
            latency=latency
        )
    
    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        """Called when LLM errors"""
        if not self.span or not self.opik.is_enabled():
            return
        
        try:
            self.span.log(
                name="llm_error",
                input={"error": str(error)},
                metadata={"node_name": self.node_name}
            )
        except Exception as e:
            pass  # Silently fail to not break workflow
    
    def _extract_provider(self, serialized: Dict[str, Any]) -> str:
        """Extract provider name from serialized model"""
        # Try to extract from model name or config
        name = serialized.get("name", "").lower()
        if "openai" in name or "gpt" in name:
            return "openai"
        elif "deepseek" in name:
            return "deepseek"
        return "unknown"


