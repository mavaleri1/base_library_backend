"""
Material synthesis node.
Combines generated material and recognized notes into final document.
If no notes exist - simply uses generated_material.
"""

import logging
from typing import Literal
from langchain_core.messages import SystemMessage
from langgraph.types import Command

from ..core.state import GeneralState
from .base import BaseWorkflowNode
from ..services.opik_client import get_opik_client
from ..utils.llm_usage import extract_usage_from_response


logger = logging.getLogger(__name__)


class SynthesisNode(BaseWorkflowNode):
    """
    Material synthesis node based on generated content and recognized notes.
    Simple node without HITL logic - direct transition to question generation.
    """

    def __init__(self):
        super().__init__(logger)
        self.model = self.create_model()

    def get_node_name(self) -> str:
        """Returns node name for configuration lookup"""
        return "synthesis_material"
    
    def _build_context_from_state(self, state) -> dict:
        """Builds context for prompt from workflow state"""
        context = {}
        
        if hasattr(state, 'input_content'):
            context['input_content'] = state.input_content
        
        if hasattr(state, 'recognized_notes'):
            context['handwritten_notes'] = state.recognized_notes
        
        if hasattr(state, 'generated_material'):
            context['generated_material'] = state.generated_material
            
        return context

    async def __call__(
        self, state: GeneralState, config
    ) -> Command[Literal["edit_material"]]:
        """
        Synthesizes final material from generated_material and recognized_notes.

        Args:
            state: Current state with generated_material and potentially recognized_notes
            config: LangGraph configuration

        Returns:
            Command with transition to question generation and updated state
        """
        thread_id = config["configurable"]["thread_id"]
        logger.info(f"Starting synthesis for thread {thread_id}")

        # Check if synthesized_material is already set (e.g., if recognition was skipped)
        if state.synthesized_material:
            logger.info(
                f"Synthesized material already set for thread {thread_id}, skipping synthesis"
            )
            return Command(
                goto="edit_material",
                update={},  # Don't update anything, material already exists
            )

        # Check for base material presence
        if not state.generated_material:
            logger.error(f"No generated material found for thread {thread_id}")
            raise ValueError("Missing generated material for synthesis")

        # Determine if there are recognized notes
        has_recognized_notes = bool(
            state.recognized_notes and state.recognized_notes.strip()
        )

        if has_recognized_notes:
            logger.info(
                f"Synthesizing with both generated material and recognized notes for thread {thread_id}"
            )

            # Get personalized prompt from service
            prompt_content = await self.get_system_prompt(state, config)

            # Get Opik span for logging
            span = self._get_opik_span(config)
            
            # Generate synthesized material
            messages = [SystemMessage(content=prompt_content)]
            import time
            start_time = time.time()
            response = await self.model.ainvoke(messages)
            latency = (time.time() - start_time) * 1000  # ms
            synthesized_material = response.content
            
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
                    logger.debug(f"✅ Logged LLM call to Opik for synthesis")
                except Exception as e:
                    logger.warning(f"Failed to log to Opik: {e}")

            logger.info(
                f"Successfully synthesized material with notes for thread {thread_id}"
            )
        else:
            logger.info(
                f"No recognized notes found, using generated material as synthesis for thread {thread_id}"
            )

            # If no recognized notes, use generated material as is
            synthesized_material = state.generated_material

        # Update state
        update_data = {"synthesized_material": synthesized_material}

        logger.info(
            f"Synthesis completed for thread {thread_id}. "
            f"Material length: {len(synthesized_material)} chars, "
            f"Had notes: {has_recognized_notes}"
        )

        return Command(goto="edit_material", update=update_data)
