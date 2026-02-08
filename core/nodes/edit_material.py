"""
Node for iterative editing of synthesized material.
Minimal MVP integration based on working code from Jupyter notebook.
"""

import logging
import html
import re
from typing import Optional, Tuple
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.types import interrupt, Command
from fuzzysearch import find_near_matches

from .base import BaseWorkflowNode
from ..core.state import GeneralState, ActionDecision, EditDetails, EditMessageDetails
# from ..utils.utils import render_system_prompt
from ..services.hitl_manager import get_hitl_manager
from ..services.opik_client import get_opik_client


class EditMaterialNode(BaseWorkflowNode):
    """
    Node for editing synthesized material.
    Uses HITL pattern for iterative edits.
    """

    def __init__(self, logger: logging.Logger = None):
        super().__init__(logger)
        self.model = self.create_model()  # Initialize on first call

    def get_node_name(self) -> str:
        """Returns node name for configuration"""
        return "edit_material"
    
    def _build_context_from_state(self, state) -> dict:
        """Builds context for prompt from workflow state"""
        context = {}
        
        if hasattr(state, 'synthesized_material'):
            context['generated_material'] = state.synthesized_material
            
        return context

    def get_model(self):
        """Returns model for LLM access"""
        return self.model

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for comparison:
        - HTML unescape (&#39; → ', &amp; → &, &quot; → ")
        - Normalize whitespace (multiple spaces → single space)
        - Normalize line endings (CRLF → LF)
        - Remove trailing whitespace from lines
        """
        if not text:
            return text
        
        # HTML unescape
        normalized = html.unescape(text)
        
        # Normalize line endings (CRLF → LF)
        normalized = normalized.replace('\r\n', '\n').replace('\r', '\n')
        
        # Normalize multiple spaces to single space (but preserve line breaks)
        # Split by lines, normalize each line, then rejoin
        lines = normalized.split('\n')
        normalized_lines = []
        for line in lines:
            # Replace multiple spaces/tabs with single space
            line = re.sub(r'[ \t]+', ' ', line)
            # Remove trailing whitespace
            line = line.rstrip()
            normalized_lines.append(line)
        
        normalized = '\n'.join(normalized_lines)
        
        return normalized

    def fuzzy_find_and_replace(
        self, document: str, target: str, replacement: str, threshold: float = 0.85
    ) -> Tuple[str, bool, Optional[str], float]:
        """
        Fuzzy search and replace text in document.
        Uses text normalization to handle HTML entities and whitespace differences.

        Returns: (new_document, success, found_text, similarity)
        """
        # Edge case: empty strings
        if not target or not document:
            return document, False, None, 0.0

        # Normalize replacement to remove HTML entities before inserting into document
        normalized_replacement = self._normalize_text(replacement)
        if normalized_replacement != replacement:
            self.logger.debug(
                f"Normalized replacement (removed HTML entities): "
                f"length changed from {len(replacement)} to {len(normalized_replacement)}"
            )

        # Normalize both texts for comparison
        normalized_document = self._normalize_text(document)
        normalized_target = self._normalize_text(target)
        
        # For short strings - try exact match first (both normalized and original)
        if len(target) < 10:
            # Try normalized first
            if normalized_target in normalized_document:
                idx = normalized_document.index(normalized_target)
                # Find corresponding position in original document
                # This is approximate but should work for short strings
                orig_idx = self._find_original_position(document, normalized_document, idx)
                if orig_idx >= 0:
                    new_doc = document[:orig_idx] + normalized_replacement + document[orig_idx + len(target):]
                    return new_doc, True, target, 1.0
            # Fallback to original
            if target in document:
                idx = document.index(target)
                new_doc = document[:idx] + normalized_replacement + document[idx + len(target):]
                return new_doc, True, target, 1.0
            return document, False, None, 0.0

        # Calculate distance
        max_distance = max(1, int(len(normalized_target) * (1 - threshold)))

        # For very long strings, increase max_distance proportionally but with reasonable limits
        if len(normalized_target) > 1000:
            # For very long strings (>1000), allow up to 100 chars distance
            max_distance = min(max_distance, 100)
        elif len(normalized_target) > 100:
            # For long strings, allow more distance: up to 1% of length or 50 chars, whichever is smaller
            proportional_distance = max(max_distance, min(int(len(normalized_target) * 0.01), 50))
            max_distance = proportional_distance

        # Search in normalized text first
        try:
            matches = find_near_matches(normalized_target, normalized_document, max_l_dist=max_distance)
        except Exception as e:
            self.logger.error(f"Fuzzy search error: {e}")
            return document, False, None, 0.0

        if not matches:
            # Fallback: try without normalization
            self.logger.debug("No match found with normalization, trying without normalization")
            try:
                matches = find_near_matches(target, document, max_l_dist=max_distance)
            except Exception as e:
                self.logger.error(f"Fuzzy search error (fallback): {e}")
                return document, False, None, 0.0
            
            if not matches:
                return document, False, None, 0.0
            
            # Use original document for replacement
            match = matches[0]
            similarity = max(0.0, 1 - (match.dist / len(target))) if len(target) > 0 else (1.0 if match.dist == 0 else 0.0)
            new_document = document[:match.start] + normalized_replacement + document[match.end:]
            return new_document, True, match.matched, similarity

        # Take first match from normalized search
        match = matches[0]

        # Calculate similarity
        if len(normalized_target) > 0:
            similarity = max(0.0, 1 - (match.dist / len(normalized_target)))
        else:
            similarity = 1.0 if match.dist == 0 else 0.0

        # Find corresponding position in original document
        # This is approximate: find the normalized match position, then map back
        orig_start = self._find_original_position(document, normalized_document, match.start)
        orig_end = self._find_original_position(document, normalized_document, match.end)
        
        if orig_start >= 0 and orig_end >= orig_start:
            # Replace in original document
            new_document = document[:orig_start] + normalized_replacement + document[orig_end:]
            # Extract found text from original document for return
            found_text = document[orig_start:orig_end]
            return new_document, True, found_text, similarity
        else:
            # Fallback: use normalized positions (less accurate but should work)
            self.logger.warning("Could not map normalized positions to original, using approximate mapping")
            new_document = document[:match.start] + normalized_replacement + document[match.end:]
            return new_document, True, match.matched, similarity

    def _find_original_position(self, original: str, normalized: str, normalized_pos: int) -> int:
        """
        Find the approximate position in original text corresponding to normalized position.
        Uses character counting approach that accounts for normalization differences.
        """
        if normalized_pos >= len(normalized):
            return len(original)
        
        if normalized_pos == 0:
            return 0
        
        # Normalize the original to see the mapping
        orig_normalized = self._normalize_text(original)
        
        # If lengths match after normalization, positions should align
        # Use a simple heuristic: count normalized characters up to position
        # by walking through original and tracking normalized length
        norm_len = 0
        for i, char in enumerate(original):
            # Estimate normalized length contribution of this character
            # HTML entities contribute 1 char after unescape
            # Whitespace normalization is handled line-by-line
            char_norm = html.unescape(char)
            if char_norm:
                # Count this character (whitespace normalization happens per line)
                # For simplicity, count all non-newline chars
                if char_norm != '\n':
                    norm_len += 1
                else:
                    norm_len += 1  # Newline counts as 1
            else:
                # HTML entity that becomes empty? Shouldn't happen but handle it
                continue
            
            if norm_len >= normalized_pos:
                return i
        
        # Fallback: if we haven't reached the position, return end
        return len(original)

    async def handle_edit_action(
        self, state: GeneralState, action: EditDetails, messages: list
    ) -> Command:
        """Handle edit action"""
        document = state.synthesized_material

        # Log detailed information before search
        self.logger.info(
            f"Attempting edit: old_text length={len(action.old_text)}, "
            f"document length={len(document)}, "
            f"new_text length={len(action.new_text)}"
        )
        
        # Log normalized versions for debugging
        normalized_old = self._normalize_text(action.old_text)
        normalized_doc = self._normalize_text(document)
        self.logger.debug(
            f"Normalized old_text (first 200 chars): {normalized_old[:200]}"
        )
        self.logger.debug(
            f"Normalized document (first 200 chars): {normalized_doc[:200]}"
        )
        
        # Check if normalization changed anything
        if normalized_old != action.old_text:
            self.logger.debug("Normalization changed old_text (likely HTML entities present)")
        if normalized_doc != document:
            self.logger.debug("Normalization changed document (likely whitespace differences)")

        # Use fuzzy_find_and_replace
        new_document, success, found_text, similarity = self.fuzzy_find_and_replace(
            document, action.old_text, action.new_text
        )

        if not success:
            # Text not found - log detailed information
            self.logger.warning(
                f"Text not found: '{action.old_text[:50]}...' "
                f"(similarity: {similarity:.2f}, "
                f"old_text length: {len(action.old_text)}, "
                f"document length: {len(document)})"
            )
            
            # Log what was actually searched
            self.logger.debug(
                f"Normalized old_text sample: '{normalized_old[:100]}...'"
            )
            self.logger.debug(
                f"Normalized document sample: '{normalized_doc[:100]}...'"
            )

            error_msg = "Could not find the specified text fragment. Please specify which section to remove or change."
            messages.append(SystemMessage(content=f"[EDIT ERROR]: {error_msg}"))

            return Command(
                goto="edit_material",
                update={
                    "feedback_messages": messages,
                    "needs_user_input": True,  # Request user input with error message
                    "agent_message": error_msg,  # Show error in modal
                    "last_action": "edit_error",
                },
            )

        # Successful editing
        edit_count = state.edit_count + 1
        self.logger.info(f"Edit #{edit_count} applied (similarity: {similarity:.2f})")

        messages.append(
            SystemMessage(
                content=f"[EDIT SUCCESS #{edit_count}]: Replaced text (similarity: {similarity:.2f})"
            )
        )

        # Update state
        update_dict = {
            "synthesized_material": new_document,
            "feedback_messages": messages,
            "edit_count": edit_count,
            "needs_user_input": not action.continue_editing,
            "last_action": "edit",
        }

        # If not continuing autonomously, set message
        if not action.continue_editing:
            update_dict["agent_message"] = "Edit applied. What other changes are needed?"

        return Command(goto="edit_material", update=update_dict)

    async def handle_message_action(
        self, state: GeneralState, action: EditMessageDetails, messages: list
    ) -> Command:
        """Handle user message"""
        messages.append(AIMessage(content=action.content))

        return Command(
            goto="edit_material",
            update={
                "feedback_messages": messages,
                "needs_user_input": True,
                "agent_message": action.content,
                "last_action": "message",
            },
        )

    async def handle_complete_action(self, state: GeneralState) -> Command:
        """Complete editing"""
        self.logger.info("Edit session completed")

        return Command(
            goto="generating_questions",  # Move to next node
            update={
                "needs_user_input": True,  # Reset flag for next node
                "agent_message": None,
                "last_action": "complete",
                "feedback_messages": [],
            },
        )

    async def __call__(self, state: GeneralState, config: RunnableConfig) -> Command:
        """
        Main editing node logic.
        Handles cycle: input request -> analysis -> action -> repeat
        """
        thread_id = config.get("configurable", {}).get("thread_id", "unknown")
        self.logger.debug(f"EditMaterialNode called for thread {thread_id}")

        # Check HITL settings
        hitl_manager = get_hitl_manager()
        hitl_enabled = hitl_manager.is_enabled("edit_material", thread_id)
        self.logger.info(f"HITL for edit_material: {hitl_enabled}")

        # Get message history
        messages = state.feedback_messages.copy() if state.feedback_messages else []

        # Check if there's material to edit
        if not state.synthesized_material:
            self.logger.warning("No synthesized material to edit")
            return Command(
                goto="generating_questions",
                update={"agent_message": "No material to edit"},
            )

        # If HITL disabled, skip this node
        if not hitl_enabled:
            self.logger.info("HITL disabled for edit_material, skipping to next node")
            return Command(
                goto="generating_questions",
                update={
                    "agent_message": "Material accepted without editing (autonomous mode)",
                    "last_action": "skip_hitl",
                },
            )

        # Request user input if needed
        if state.needs_user_input:
            msg_to_user = state.agent_message or "Which changes to make to the material? "

            # Use interrupt to get input
            interrupt_data = {"message": [msg_to_user]}
            user_feedback = interrupt(interrupt_data)

            if user_feedback:
                # Validate edit request in HITL cycle
                if self.security_guard:
                    user_feedback = await self.validate_input(user_feedback)

                messages.append(HumanMessage(content=user_feedback))

                # Reset flags and continue processing
                return Command(
                    goto="edit_material",
                    update={
                        "feedback_messages": messages,
                        "agent_message": None,
                        "needs_user_input": False,
                    },
                )

        # Get personalized prompt from service with additional context
        extra_context = {
            "template_variant": "initial",
            "generated_material": state.synthesized_material if hasattr(state, 'synthesized_material') else ""
        }
        system_prompt = await self.get_system_prompt(state, config, extra_context)

        # Get Opik span for logging
        span = self._get_opik_span(config)
        
        # Step 1: Determine action type
        model = self.get_model()
        import time
        start_time = time.time()
        decision = await model.with_structured_output(ActionDecision).ainvoke(
            [SystemMessage(content=system_prompt)] + messages
        )
        latency = (time.time() - start_time) * 1000  # ms

        # Log LLM call to Opik
        if self.opik.is_enabled() and span:
            try:
                model_config = self.get_model_config()
                self.opik.log_llm_call(
                    span=span,
                    model_name=model_config.model_name,
                    provider=model_config.provider,
                    messages=[{"role": "system", "content": system_prompt}],
                    response=decision.model_dump_json(),
                    latency=latency
                )
            except Exception as e:
                self.logger.debug(f"Failed to log decision to Opik: {e}")

        self.logger.debug(f"Action decision: {decision.action_type}")
        messages.append(AIMessage(content=decision.model_dump_json()))

        # Step 2: Execute action based on type
        if decision.action_type == "edit":
            start_time = time.time()
            details = await model.with_structured_output(EditDetails).ainvoke(
                [SystemMessage(content=system_prompt)] + messages
            )
            latency = (time.time() - start_time) * 1000  # ms
            
            # Log LLM call to Opik
            if self.opik.is_enabled() and span:
                try:
                    model_config = self.get_model_config()
                    self.opik.log_llm_call(
                        span=span,
                        model_name=model_config.model_name,
                        provider=model_config.provider,
                        messages=[{"role": "system", "content": system_prompt}],
                        response=details.model_dump_json(),
                        latency=latency
                    )
                except Exception as e:
                    self.logger.debug(f"Failed to log edit details to Opik: {e}")

            self.logger.info(f"Edit details: {details.model_dump_json()}")

            return await self.handle_edit_action(state, details, messages)

        elif decision.action_type == "message":
            start_time = time.time()
            details = await model.with_structured_output(EditMessageDetails).ainvoke(
                [SystemMessage(content=system_prompt)] + messages
            )
            latency = (time.time() - start_time) * 1000  # ms
            
            # Log LLM call to Opik
            if self.opik.is_enabled() and span:
                try:
                    model_config = self.get_model_config()
                    self.opik.log_llm_call(
                        span=span,
                        model_name=model_config.model_name,
                        provider=model_config.provider,
                        messages=[{"role": "system", "content": system_prompt}],
                        response=details.model_dump_json(),
                        latency=latency
                    )
                except Exception as e:
                    self.logger.debug(f"Failed to log message details to Opik: {e}")
            
            self.logger.info(f"Edit message details: {details.model_dump_json()}")
            return await self.handle_message_action(state, details, messages)

        elif decision.action_type == "complete":
            return await self.handle_complete_action(state)

        # Should not happen, but just in case
        self.logger.error(f"Unknown action type: {decision.action_type}")
        return Command(
            goto="edit_material",
            update={
                "needs_user_input": True,
                "agent_message": "An error occurred. Please try again.",
            },
        )
