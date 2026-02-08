"""
Extract token usage and optional cost from LangChain LLM responses for Opik logging.
"""

from typing import Any, Dict, Optional, Tuple


def extract_usage_from_response(response: Any) -> Tuple[Optional[Dict[str, int]], Optional[float]]:
    """
    Extract token usage and optionally cost from a LangChain AIMessage or similar response.

    Handles:
    - response_metadata["usage"] (OpenAI-style: prompt_tokens, completion_tokens, total_tokens)
    - response_metadata["token_usage"] (alternative key)
    - usage_metadata (LangChain UsageMetadata)

    Returns:
        (tokens_used, cost): tokens_used is {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}
        or None; cost is float or None if not available.
    """
    tokens_used: Optional[Dict[str, int]] = None
    cost: Optional[float] = None

    if response is None:
        return None, None

    # Prefer usage_metadata (LangChain structured)
    if hasattr(response, "usage_metadata") and response.usage_metadata is not None:
        um = response.usage_metadata
        if hasattr(um, "input_tokens") and hasattr(um, "output_tokens"):
            tokens_used = {
                "prompt_tokens": getattr(um, "input_tokens", 0) or 0,
                "completion_tokens": getattr(um, "output_tokens", 0) or 0,
                "total_tokens": (getattr(um, "input_tokens", 0) or 0) + (getattr(um, "output_tokens", 0) or 0),
            }
        if hasattr(um, "total_tokens") and um.total_tokens is not None:
            tokens_used["total_tokens"] = um.total_tokens

    # Fallback: response_metadata
    if tokens_used is None and hasattr(response, "response_metadata") and response.response_metadata:
        meta = response.response_metadata
        usage = meta.get("usage") or meta.get("token_usage")
        if isinstance(usage, dict):
            tokens_used = {
                "prompt_tokens": usage.get("prompt_tokens", 0) or 0,
                "completion_tokens": usage.get("completion_tokens", 0) or 0,
                "total_tokens": usage.get("total_tokens", 0) or 0,
            }
            if not tokens_used["total_tokens"] and (tokens_used["prompt_tokens"] or tokens_used["completion_tokens"]):
                tokens_used["total_tokens"] = tokens_used["prompt_tokens"] + tokens_used["completion_tokens"]

    if tokens_used and (tokens_used.get("prompt_tokens") or tokens_used.get("completion_tokens")):
        cost = _estimate_cost_from_usage(tokens_used, response)
    else:
        tokens_used = None

    return tokens_used, cost


def _estimate_cost_from_usage(usage: Dict[str, int], response: Any) -> Optional[float]:
    """
    Rough cost estimate (USD) from token counts and model.
    Uses public list prices per 1K tokens; returns None if model unknown.
    """
    model = None
    if hasattr(response, "response_metadata") and response.response_metadata:
        model = response.response_metadata.get("model_name") or response.response_metadata.get("model")
    if not model and hasattr(response, "name"):
        model = getattr(response, "name", None)

    prompt_tokens = usage.get("prompt_tokens", 0) or 0
    completion_tokens = usage.get("completion_tokens", 0) or 0
    if not model or (not prompt_tokens and not completion_tokens):
        return None

    # Approximate USD per 1M tokens (input, output) — update as needed for your models
    pricing: Dict[str, Tuple[float, float]] = {
        "gpt-4o": (2.50, 10.00),
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4-turbo": (10.00, 30.00),
        "gpt-4": (30.00, 60.00),
        "gpt-3.5-turbo": (0.50, 1.50),
    }
    model_lower = (model or "").lower()
    price_in, price_out = None, None
    for key, (p_in, p_out) in pricing.items():
        if key in model_lower:
            price_in, price_out = p_in, p_out
            break
    if price_in is None:
        return None

    cost = (prompt_tokens / 1_000_000.0) * price_in + (completion_tokens / 1_000_000.0) * price_out
    return round(cost, 6)
