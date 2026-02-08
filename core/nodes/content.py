"""
Educational material generation node.
Adapted from generating_content_node in main.ipynb for production architecture.
"""

import logging
from typing import Literal, Union
from langchain_core.messages import SystemMessage
from langgraph.types import Command

from ..core.state import GeneralState
from .base import BaseWorkflowNode
from ..services.opik_client import get_opik_client
from ..utils.llm_usage import extract_usage_from_response


logger = logging.getLogger(__name__)


class ContentGenerationNode(BaseWorkflowNode):
    """
    Educational material generation node based on exam question.
    Determines next transition: if images exist - to recognition, if not - to generating_questions.
    """

    def __init__(self):
        super().__init__(logger)
        self.model = self.create_model()

    def get_node_name(self) -> str:
        """Returns node name for configuration lookup"""
        return "generating_content"
    
    def _build_context_from_state(self, state) -> dict:
        """Builds context for prompt from workflow state"""
        return {
            "input_content": state.input_content if hasattr(state, 'input_content') else "",
            "input_content": state.input_content if hasattr(state, 'input_content') else ""
        }

    async def __call__(
        self, state: GeneralState, config
    ) -> Union[
        Command[Literal["recognition_handwritten"]],
        Command[Literal["generating_questions"]],
    ]:
        """
        Generates educational material based on exam question.

        Args:
            state: Current state with exam question
            config: LangGraph configuration

        Returns:
            Command with transition to image recognition or question generation
        """
        thread_id = config["configurable"]["thread_id"]
        logger.info(f"Starting content generation for thread {thread_id}")

        # Get personalized prompt from service
        prompt_content = await self.get_system_prompt(state, config)

        messages = [SystemMessage(content=prompt_content)]

        # Get Opik span for logging
        span = self._get_opik_span(config)
        
        # Generate material
        logger.debug(f"Generating content for question: {state.input_content[:100]}...")
        import time
        start_time = time.time()
        response = await self.model.ainvoke(messages)
        latency = (time.time() - start_time) * 1000  # ms

        # Log LLM call to Opik (with usage and cost when available)
        if self.opik.is_enabled() and span:
            try:
                tokens_used, cost = extract_usage_from_response(response)
                model_config = self.get_model_config()
                self.opik.log_llm_call(
                    span=span,
                    model_name=model_config.model_name,
                    provider=model_config.provider,
                    messages=[{"role": "system", "content": prompt_content}],
                    response=response.content,
                    tokens_used=tokens_used,
                    cost=cost,
                    latency=latency
                )
                logger.debug(f"✅ Logged LLM call to Opik for thread {thread_id}")
            except Exception as e:
                logger.warning(f"Failed to log to Opik: {e}")

        logger.info(f"Content generated successfully for thread {thread_id}")

        return Command(
            goto="recognition_handwritten",
            update={
                "generated_material": response.content,
            },
        )
