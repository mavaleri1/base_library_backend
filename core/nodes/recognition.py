"""
Educational notes processing node.
Simple logic without HITL: processes images if available, requests once if not.
"""

import base64
import logging
from typing import List
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
from langgraph.types import Command, interrupt

from ..core.state import GeneralState
from .base import BaseWorkflowNode
from ..services.opik_client import get_opik_client
from ..utils.llm_usage import extract_usage_from_response


logger = logging.getLogger(__name__)


def load_images_as_base64(image_paths: List[str]) -> List[str]:
    """
    Loads images in base64 format.

    Args:
        image_paths: List of image paths

    Returns:
        List of base64 image strings
    """
    base64_images = []
    for image_path in image_paths:
        try:
            with open(image_path, "rb") as image_file:
                base64_string = base64.b64encode(image_file.read()).decode("utf-8")
                base64_images.append(base64_string)
                logger.info(f"Loaded image: {image_path}")
        except Exception as e:
            logger.error(f"Failed to load image {image_path}: {e}")

    return base64_images


class RecognitionNode(BaseWorkflowNode):
    """
    Educational notes processing node with support for:
    - Processing notes in any format (images or text)
    - Direct text notes input
    - Minimum text length validation
    - Skipping processing at user's request
    """
    
    MIN_TEXT_LENGTH = 50  # Minimum length for valid note text

    def __init__(self):
        super().__init__(logger)
        self.model = self.create_model()

    def get_node_name(self) -> str:
        """Returns node name for configuration lookup"""
        return "recognition_handwritten"
    
    def _build_context_from_state(self, state) -> dict:
        """Builds context for prompt from workflow state"""
        return {
            # Recognition node does not require context from state for prompt
        }

    async def __call__(self, state: GeneralState, config) -> Command:
        """
        Main recognition node logic.

        Args:
            state: Current state with potential image_paths
            config: LangGraph configuration

        Returns:
            Command with transition to next node
        """
        thread_id = config["configurable"]["thread_id"]
        logger.info(f"Starting recognition processing for thread {thread_id}")

        # Case 1: Images available - process them
        if state.image_paths:
            logger.info(
                f"Found {len(state.image_paths)} images, processing recognition"
            )

            try:
                # Process images
                recognized_text = await self._process_images(state.image_paths, state, config)

                if recognized_text:
                    logger.info(
                        f"Successfully recognized text from images for thread {thread_id}"
                    )
                    return Command(
                        goto="synthesis_material",
                        update={"recognized_notes": recognized_text},
                    )
                else:
                    logger.warning(
                        f"Failed to recognize text from images for thread {thread_id}"
                    )
                    # Skip synthesis on recognition error
                    return Command(
                        goto="generating_questions",
                        update={
                            "recognized_notes": "",
                            "synthesized_material": state.generated_material
                        }
                    )

            except Exception as e:
                logger.error(f"Error processing images for thread {thread_id}: {e}")
                # Skip synthesis in case of error
                return Command(
                    goto="generating_questions",
                    update={
                        "recognized_notes": "",
                        "synthesized_material": state.generated_material
                    }
                )

        # Case 2: No images - request notes from user
        logger.info(f"No images found for thread {thread_id}, requesting notes from user")

        # Request notes from user (images or text)
        message_content = (
            "📸 To improve material quality, you can add notes from classes.\n\n"
            "Action options:\n"
            "• Send photos of notes or paste text (at least 50 characters)\n"
            "• Materials accepted in any format (excluded .webp)\n"
            "• Write 'skip' to continue without notes"
        )

        # Make interrupt to get user response
        interrupt_json = {"message": [message_content]}
        user_response = interrupt(interrupt_json)

        # Process user response
        # Check text length - less than 50 characters means skip
        cleaned_text = user_response.strip()
        if len(cleaned_text) < self.MIN_TEXT_LENGTH:
            logger.info(f"Text too short ({len(cleaned_text)} chars), user wants to skip notes for thread {thread_id}")
            # Text too short - user wants to skip
            return Command(
                goto="generating_questions",
                update={
                    "recognized_notes": "",
                    "synthesized_material": state.generated_material,  # Use generated_material as final
                },
            )
        
        # Text sufficient length - use as recognized notes
        logger.info(f"Received text notes ({len(cleaned_text)} chars) for thread {thread_id}, proceeding to synthesis")
        return Command(
            goto="synthesis_material",
            update={"recognized_notes": cleaned_text}
        )

    async def _process_images(self, image_paths: List[str], state: GeneralState, config) -> str:
        """
        Processes images using GPT-4-vision.

        Args:
            image_paths: List of image paths
            state: Workflow state
            config: LangGraph configuration

        Returns:
            Recognized text or empty string on error
        """
        import time
        start_time = time.time()
        try:
            # Load images in base64
            base64_images = load_images_as_base64(image_paths)
            if not base64_images:
                logger.error("Failed to load any images for recognition")
                return ""

            # Get personalized prompt from service
            system_content = await self.get_system_prompt(state, config)

            # Get Opik span for logging
            span = self._get_opik_span(config)
            
            # Log multimodal data to Opik
            if self.opik.is_enabled() and span:
                try:
                    self.opik.log_multimodal_data(
                        span=span,
                        image_paths=image_paths,
                        metadata={"image_count": len(image_paths)}
                    )
                    logger.debug(f"✅ Logged multimodal data to Opik")
                except Exception as e:
                    logger.debug(f"Failed to log multimodal data to Opik: {e}")

            # Create content with images for GPT-4-vision
            user_content = [
                {
                    "type": "text",
                    "text": "Here are handwritten notes images for recognition:",
                }
            ]

            for base64_img in base64_images:
                user_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{base64_img}"},
                    }
                )

            # Create messages for model
            messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=user_content),
            ]

            # Send request to model
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
                        messages=[
                            {"role": "system", "content": system_content},
                            {"role": "user", "content": f"[Multimodal: {len(image_paths)} images]"}
                        ],
                        response=response.content,
                        tokens_used=tokens_used,
                        cost=cost,
                        latency=latency
                    )
                    logger.debug(f"✅ Logged LLM call to Opik for recognition")
                except Exception as e:
                    logger.warning(f"Failed to log to Opik: {e}")

            # Normalize response to string
            raw_content = response.content
            if raw_content is None:
                raw_content = ""
            content_str = (str(raw_content) if raw_content else "").strip()

            # Process response (remove reasoning section)
            if "[END OF REASONING]" in content_str:
                content = content_str.split("[END OF REASONING]")[1].strip()
                if not content:
                    logger.warning(
                        "Content after [END OF REASONING] was empty, using full response. "
                        "Raw response length: %d chars",
                        len(content_str),
                    )
                    logger.debug(
                        "Raw response (first 200 / last 200): %s ... %s",
                        content_str[:200] if len(content_str) > 200 else content_str,
                        content_str[-200:] if len(content_str) > 200 else "",
                    )
                    content = content_str
            else:
                content = content_str

            # Validation of recognized text from handwritten notes
            if self.security_guard and content:
                content = await self.validate_input(content)

            elapsed = time.time() - start_time
            if len(content) == 0:
                logger.warning(
                    "Image recognition returned 0 chars. Raw response length: %d. "
                    "First 200 chars: %s",
                    len(content_str),
                    content_str[:200] if content_str else "(empty)",
                )
            if elapsed > 5.0:
                logger.warning(f"Image recognition completed in {elapsed:.2f}s (slow), text length: {len(content)} chars")
            else:
                logger.info(f"Image recognition completed in {elapsed:.2f}s, text length: {len(content)} chars")
            
            return content

        except Exception as e:
            logger.error(f"Error in image processing: {e}")
            return ""
