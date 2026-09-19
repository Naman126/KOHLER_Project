"""
requirement_extractor.py
-------------------------
Turns a natural-language bathroom brief into validated structured
requirements JSON.

Tries the LLM first (llm_service.py). If the LLM is unavailable, times out,
or returns something that doesn't validate against the expected schema,
this module falls back to a deterministic rule-based (regex) extractor so
the app NEVER crashes and always produces a usable requirements object
(section 20: robustness requirement).
"""

import re
from typing import List, Optional

from src import llm_service

VALID_CATEGORIES = {"smart_toilet", "shower", "faucet", "vanity"}

EMPTY_REQUIREMENTS = {
    "bathroom": {"length_ft": None, "width_ft": None, "unit": "ft"},
    "budget": {"amount": None, "currency": "INR"},
    "style": None,
    "required_categories": [],
    "preferences": {
        "finish": None,
        "sustainability": False,
        "smart_features": False,
        "desired_features": [],
        "required_features": [],
    },
    "hard_constraints": [],
    "soft_preferences": [],
}


def _deep_copy_empty() -> dict:
    import copy
    return copy.deepcopy(EMPTY_REQUIREMENTS)


def validate_and_normalize(candidate: dict) -> Optional[dict]:
    """
    Checks the candidate dict has the right shape and types.
    Fills in any missing keys with safe defaults rather than rejecting outright,
    since a partially-correct LLM response is still useful.
    Returns None only if candidate isn't even a dict.
    """
    if not isinstance(candidate, dict):
        return None

    result = _deep_copy_empty()

    bathroom = candidate.get("bathroom") or {}
    if isinstance(bathroom, dict):
        for key in ("length_ft", "width_ft"):
            val = bathroom.get(key)
            if isinstance(val, (int, float)) and val > 0:
                result["bathroom"][key] = float(val)

    budget = candidate.get("budget") or {}
    if isinstance(budget, dict):
        amount = budget.get("amount")
        if isinstance(amount, (int, float)) and amount > 0:
            result["budget"]["amount"] = float(amount)
        if isinstance(budget.get("currency"), str):
            result["budget"]["currency"] = budget["currency"]

    if isinstance(candidate.get("style"), str) and candidate["style"].strip():
        result["style"] = candidate["style"].strip().lower().replace(" ", "_")

    raw_categories = candidate.get("required_categories") or []
    if isinstance(raw_categories, list):
        result["required_categories"] = [c for c in raw_categories if c in VALID_CATEGORIES]

    prefs = candidate.get("preferences") or {}
    if isinstance(prefs, dict):
        if isinstance(prefs.get("finish"), str):
            result["preferences"]["finish"] = prefs["finish"].strip().lower().replace(" ", "_")
        result["preferences"]["sustainability"] = bool(prefs.get("sustainability", False))
        result["preferences"]["smart_features"] = bool(prefs.get("smart_features", False))
        if isinstance(prefs.get("desired_features"), list):
            result["preferences"]["desired_features"] = [str(f) for f in prefs["desired_features"]]
        if isinstance(prefs.get("required_features"), list):
            result["preferences"]["required_features"] = [str(f) for f in prefs["required_features"]]

    if isinstance(candidate.get("hard_constraints"), list):
        result["hard_constraints"] = [str(c) for c in candidate["hard_constraints"]]
    if isinstance(candidate.get("soft_preferences"), list):
        result["soft_preferences"] = [str(c) for c in candidate["soft_preferences"]]

    return result


# ---------------------------------------------------------------------------
# Rule-based fallback extractor (used when the LLM is unavailable/invalid)
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS = {
    "smart_toilet": ["smart toilet", "toilet", "bidet", "wc"],
    "shower": ["shower", "rain head", "rainhead"],
    "faucet": ["faucet", "tap"],
    "vanity": ["vanity", "sink cabinet", "washbasin cabinet"],
}

_STYLE_KEYWORDS = [
    "japanese_zen", "minimalist", "modern", "luxury", "classic",
]


def _fallback_dimensions(text: str):
    # matches patterns like "8 ft x 6 ft", "8x6 feet", "8 by 6"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:ft|feet)?\s*[x×by]\s*(\d+(?:\.\d+)?)\s*(?:ft|feet)?", text, re.IGNORECASE)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def _fallback_budget(text: str):
    # "3,00,000", "3 lakh", "Rs 300000", "budget of 3,00,000"
    lakh_match = re.search(r"(\d+(?:\.\d+)?)\s*lakh", text, re.IGNORECASE)
    if lakh_match:
        return float(lakh_match.group(1)) * 100000
    num_match = re.search(r"(?:rs\.?|inr|₹)\s*([\d,]+)", text, re.IGNORECASE)
    if num_match:
        return float(num_match.group(1).replace(",", ""))
    # bare large number with commas, e.g. 3,00,000
    bare_match = re.search(r"\b(\d{1,3}(?:,\d{2,3})+)\b", text)
    if bare_match:
        return float(bare_match.group(1).replace(",", ""))
    return None


def _fallback_style(text: str) -> Optional[str]:
    lowered = text.lower()
    for style in _STYLE_KEYWORDS:
        if style.replace("_", " ") in lowered or style in lowered:
            return style
    return None


def _fallback_categories(text: str) -> List[str]:
    lowered = text.lower()
    found = []
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            found.append(category)
    return found


def extract_requirements_fallback(user_text: str) -> dict:
    """Simple deterministic regex/keyword extractor. Never raises."""
    result = _deep_copy_empty()
    try:
        length, width = _fallback_dimensions(user_text)
        result["bathroom"]["length_ft"] = length
        result["bathroom"]["width_ft"] = width

        budget = _fallback_budget(user_text)
        result["budget"]["amount"] = budget

        result["style"] = _fallback_style(user_text)
        result["required_categories"] = _fallback_categories(user_text)

        lowered = user_text.lower()
        result["preferences"]["sustainability"] = any(
            kw in lowered for kw in ["water efficien", "water-sav", "sustainab", "eco"]
        )
        result["preferences"]["smart_features"] = any(
            kw in lowered for kw in ["smart", "app control", "bluetooth", "wifi", "wi-fi"]
        )
        if "matte black" in lowered:
            result["preferences"]["finish"] = "matte_black"
        elif "chrome" in lowered:
            result["preferences"]["finish"] = "polished_chrome"
        elif "black" in lowered:
            result["preferences"]["finish"] = "matte_black"
        elif "white" in lowered:
            result["preferences"]["finish"] = "white"

        if "compact" in lowered:
            result["preferences"]["desired_features"].append("compact")
        if "coordinated finish" in lowered:
            result["soft_preferences"].append("coordinated_finish")
    except Exception:
        # Absolute worst case: return the empty-but-valid structure so the app can still run
        # and prompt the user for the missing fields, instead of crashing.
        return _deep_copy_empty()
    return result


def extract_requirements(user_text: str) -> dict:
    """
    Public entry point used by the Streamlit app.
    Tries LLM extraction -> validates -> falls back to rule-based extraction
    if the LLM path fails at any step. Always returns a usable dict.
    """
    llm_candidate = llm_service.extract_requirements_via_llm(user_text)
    if llm_candidate is not None:
        validated = validate_and_normalize(llm_candidate)
        if validated is not None:
            return validated
    return extract_requirements_fallback(user_text)
