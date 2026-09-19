"""
llm_service.py
---------------
All LLM calls in the system live here, and ONLY here. Per the spec's
"Critical Design Principle", the LLM is used exclusively for:
  1. Natural-language requirement extraction -> structured JSON
  2. Turning a natural-language redesign request into updated preferences
  3. Writing human-readable explanations of decisions already made by
     the deterministic engine (scoring.py / optimizer.py / constraint_engine.py)

The LLM NEVER invents product names, prices, or specs, and its raw output
is always validated before use (see requirement_extractor.py). If the LLM
call fails or returns invalid JSON, callers fall back to a safe rule-based
extractor so the app never crashes (FR / section 20 robustness requirement).

Uses the Anthropic Messages API via the `anthropic` Python SDK.
Set ANTHROPIC_API_KEY in your environment (see .env.example).
"""

import json
import os
from typing import Optional

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

EXTRACTION_SYSTEM_PROMPT = """You are the requirement extraction component of a bathroom design system.
Convert the customer's natural-language request into valid JSON.

Extract:
- bathroom length and width
- unit
- budget and currency
- style/theme
- required product categories
- preferred finish
- sustainability preference
- smart-feature preference
- other explicit constraints

Rules:
1. Never invent missing values. Use null or empty arrays/objects when information is missing.
2. Return JSON only. No prose, no markdown code fences, no commentary.
3. Normalize dimensions to feet (length_ft, width_ft as numbers).
4. Normalize budget to a plain number in INR if the user explicitly uses Rs/INR/lakh notation.
   (1 lakh = 100000). If currency is unclear, still extract the number and set currency accordingly.
5. Separate hard constraints (things that MUST be true) from soft preferences (nice-to-haves).
6. Do not recommend, name, or price any product in this step. That is not your job.
7. required_categories must only use these exact values when applicable: "smart_toilet", "shower", "faucet", "vanity".

Return exactly this JSON shape and nothing else:
{
  "bathroom": {"length_ft": number|null, "width_ft": number|null, "unit": "ft"},
  "budget": {"amount": number|null, "currency": "INR"},
  "style": string|null,
  "required_categories": [string],
  "preferences": {
    "finish": string|null,
    "sustainability": boolean,
    "smart_features": boolean,
    "desired_features": [string],
    "required_features": [string]
  },
  "hard_constraints": [string],
  "soft_preferences": [string]
}
"""

REDESIGN_SYSTEM_PROMPT = """You are the conversational redesign component of a bathroom design system.
You receive the CURRENT structured requirements JSON and a natural-language modification request.
Return an UPDATED requirements JSON in exactly the same shape as the input, with only the fields
implied by the modification request changed. Do not invent unrelated changes.
Do not recommend, name, or price any product. Return JSON only, no prose, no markdown fences.
"""

EXPLANATION_SYSTEM_PROMPT = """You are the explanation component of a bathroom design system.
You will be given the customer's requirements, the deterministically-selected product combination,
its cost/budget numbers, its compatibility scores (already computed by code), and a list of notable
rejected alternatives with reasons. Write a short, clear, friendly explanation (120-180 words) of why
this combination was chosen, referencing the actual numbers you were given. Then include 1-3 short
bullet points on why specific alternatives were rejected, using only the reasons provided to you.
Do not invent any product, price, or spec that was not given to you. Return plain text, not JSON.
"""


def _get_client():
    """Lazily creates an Anthropic client. Returns None if the SDK or API key is unavailable."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        return anthropic.Anthropic(api_key=api_key)
    except Exception:
        return None


def _call_llm(system_prompt: str, user_message: str, max_tokens: int = 1000) -> Optional[str]:
    """
    Returns the model's raw text response, or None on any failure
    (missing key, missing package, network error, API error).
    Callers MUST handle a None return gracefully -- never let this crash the app.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        return "\n".join(parts).strip()
    except Exception:
        # Network error, auth error, rate limit, malformed response, etc.
        # Deliberately swallow here -- the caller falls back to deterministic/rule-based logic.
        return None


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def extract_requirements_via_llm(user_text: str) -> Optional[dict]:
    """Returns a parsed dict on success, or None if the LLM is unavailable or output is invalid."""
    raw = _call_llm(EXTRACTION_SYSTEM_PROMPT, user_text)
    if raw is None:
        return None
    try:
        return json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        return None


def apply_redesign_via_llm(current_requirements: dict, modification_text: str) -> Optional[dict]:
    """Returns an updated requirements dict, or None if the LLM is unavailable or output is invalid."""
    user_message = (
        f"CURRENT REQUIREMENTS JSON:\n{json.dumps(current_requirements)}\n\n"
        f"MODIFICATION REQUEST:\n{modification_text}"
    )
    raw = _call_llm(REDESIGN_SYSTEM_PROMPT, user_message)
    if raw is None:
        return None
    try:
        return json.loads(_strip_code_fences(raw))
    except json.JSONDecodeError:
        return None


def generate_explanation_via_llm(context: dict) -> Optional[str]:
    """Returns explanation text, or None if the LLM is unavailable."""
    user_message = json.dumps(context)
    return _call_llm(EXPLANATION_SYSTEM_PROMPT, user_message, max_tokens=500)


def is_llm_available() -> bool:
    return _get_client() is not None
