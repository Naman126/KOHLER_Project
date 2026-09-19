# Prompts Documentation — KOHLER AI BathPlanner

All prompts below live in `src/llm_service.py` as constants. This document explains
each one's purpose, schema, and safety rules for submission review.

## 1. Requirement Extraction Prompt

**Purpose:** Convert a free-text bathroom brief into structured JSON. Runs once per
"Generate My Bathroom" click (on the natural-language box, if filled in).

**Model input:** the user's raw natural-language text.

**Output schema:**
```json
{
  "bathroom": {"length_ft": null, "width_ft": null, "unit": "ft"},
  "budget": {"amount": null, "currency": "INR"},
  "style": null,
  "required_categories": [],
  "preferences": {
    "finish": null,
    "sustainability": false,
    "smart_features": false,
    "desired_features": [],
    "required_features": []
  },
  "hard_constraints": [],
  "soft_preferences": []
}
```

**Safety rules enforced in the prompt:**
1. Never invent missing values — use null/empty.
2. Return JSON only, no prose or markdown fences.
3. Normalize dimensions to feet.
4. Normalize budget to INR when Rs/₹/lakh notation is used.
5. Separate hard constraints from soft preferences.
6. Never recommend or name a product at this stage.

**Post-processing:** `src/requirement_extractor.py::validate_and_normalize` re-checks
every field's type before use. Anything malformed is discarded (defaulted to
null/empty), never trusted blindly. If the LLM call fails entirely (no key, network
error, invalid JSON), `extract_requirements_fallback` (regex/keyword based) is used
instead — see README section 5.

## 2. Conversational Redesign Prompt

**Purpose:** Turn a follow-up instruction (e.g. "make it more luxurious without
increasing my budget") into an updated requirements JSON, reusing the same schema
as the extraction prompt.

**Model input:** the current requirements JSON + the modification text.

**Safety rules:** same JSON-only, no-invented-products rules as extraction. The
output is re-validated with the same `validate_and_normalize` function before the
deterministic engine re-runs. If the LLM is unavailable, a minimal keyword-based
fallback (in `app.py`) makes a best-effort adjustment (e.g. "luxury" → sets
`style = "luxury"`) so the redesign button always does something rather than
silently failing.

## 3. Explanation Prompt

**Purpose:** Write the "Why this design?" and "Why not alternatives?" text shown in
the UI, in plain, friendly language.

**Model input:** a JSON context object containing ONLY numbers and product names
already produced by the deterministic engine — the selected products, total cost,
budget, compatibility scores, and rejection reasons for notable alternatives.

**Safety rules:**
- The model must only reference numbers/products it was given — it cannot invent a
  product, price, or spec, because none exist in its input beyond what the
  deterministic engine already decided.
- Output is plain text (not JSON), 120–180 words plus short rejection bullets.

**Fallback:** `src/recommendation_engine.py::_fallback_explanation` builds an
equivalent template-based explanation from the same context object if the LLM call
fails, so the UI is never left without an explanation.

## 4. Design Principle Recap

No prompt in this system is ever allowed to select a product, set a price, or decide
feasibility. Every prompt's output is either (a) validated and merged into the
requirements object that feeds the deterministic engine, or (b) generated *after*
the deterministic engine has already committed to a decision, purely to phrase that
decision in natural language.
