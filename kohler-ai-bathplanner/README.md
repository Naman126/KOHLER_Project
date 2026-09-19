# KOHLER AI BathPlanner

An AI-assisted bathroom design prototype built for the KOHLER-MITWPU AI Research Lab
selection challenge. It converts a natural-language bathroom brief into a structured
requirements object, deterministically filters and optimizes a local KOHLER product
catalog against space/budget/style constraints, generates a scaled 2D floor plan, and
explains its recommendations in plain language — with support for conversational
redesign ("make it more luxurious without increasing my budget").

> **This is a prototype for a hackathon/selection challenge, not a production
> KOHLER product.** The 20-item product catalog uses real KOHLER product and
> collection names, but all prices and any dimensions not published by KOHLER
> are **estimated placeholder values for demo purposes only**. See
> `data/kohler_products.json → _meta` for the disclosure.

## 1. Critical design principle

The LLM is **never** allowed to invent a product, price, spec, or make the final
budget/space decision. It is used only for:

1. Turning natural language into structured JSON (`src/requirement_extractor.py`)
2. Turning a redesign request into an updated structured JSON
3. Writing the human-readable explanation of a decision *after* the deterministic
   engine has already made it

All filtering, scoring, optimization, budget math, and clearance checks are plain
Python (`src/constraint_engine.py`, `src/optimizer.py`, `src/scoring.py`). If the
LLM is unavailable, misconfigured, or returns invalid JSON, the app **falls back
to deterministic rule-based logic** instead of crashing — see Section 5.

## 2. Architecture

```
USER
 ↓
STREAMLIT UI (app.py)
 ↓
LLM REQUIREMENT EXTRACTION (src/llm_service.py + src/requirement_extractor.py)
 ↓
VALIDATED STRUCTURED REQUIREMENTS JSON
 ↓
DETERMINISTIC CONSTRAINT ENGINE (src/constraint_engine.py)
 ↓
KOHLER PRODUCT CATALOG (data/kohler_products.json)
 ↓
OPTIMIZATION + SCORING (src/optimizer.py, src/scoring.py)
 ↓
RECOMMENDATION ENGINE (src/recommendation_engine.py)
 ├─ Product recommendations
 ├─ Cost / budget analysis
 ├─ Compatibility scores
 └─ 2D layout (src/layout_generator.py)
 ↓
LLM EXPLANATION (falls back to a template if unavailable)
 ↓
FINAL DESIGN shown in Streamlit
 ↓
CONVERSATIONAL REDESIGN (loops back to the constraint engine)
```

## 3. Repository structure

```
kohler-ai-bathplanner/
├── app.py                      # Streamlit UI
├── requirements.txt
├── README.md
├── .env.example
├── data/
│   └── kohler_products.json    # 20-item prototype catalog (5 per category)
├── src/
│   ├── llm_service.py          # All LLM calls live here, and only here
│   ├── requirement_extractor.py# LLM extraction + validation + rule-based fallback
│   ├── constraint_engine.py    # Hard-constraint filtering (category/feature/finish/clearance)
│   ├── recommendation_engine.py# Orchestrates filter → optimize → explain
│   ├── optimizer.py            # Exhaustive cartesian-product budget optimizer
│   ├── scoring.py              # Transparent 0-100 weighted compatibility formula
│   └── layout_generator.py     # Deterministic 2D floor plan (matplotlib)
├── prompts/
│   └── prompts_documentation.md
├── presentation/                # Put your 4-slide PDF here for submission
├── demo/                         # Put your demo video link here for submission
└── screenshots/
```

## 4. Setup & run instructions

```bash
# 1. Clone/enter the project
cd kohler-ai-bathplanner

# 2. Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
cp .env.example .env
# then edit .env and paste your ANTHROPIC_API_KEY

# 5. Run the app
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

**No API key?** The app still runs end-to-end — it automatically switches to a
deterministic rule-based extractor (regex/keyword matching for dimensions, budget,
style, categories) so you can demo the full pipeline offline. A banner in the UI
tells you which mode is active.

## 5. Robustness / error handling

Per the spec's "must not crash" requirement, the app handles:

| Situation | Behavior |
|---|---|
| No API key set | Falls back to rule-based requirement extraction |
| LLM returns malformed/non-JSON output | Caught and validated; falls back to rule-based extraction |
| LLM network/timeout error | Caught in `llm_service._call_llm`; returns `None`, caller falls back |
| No dimensions given | Space score defaults to neutral (50); floor plan shows a prompt instead of crashing |
| No budget given | Budget fit treated as unconstrained rather than dividing by zero |
| No feasible product combination | UI shows a clear "infeasible" message with the specific overage or missing category, not a stack trace |
| LLM tries to invent a product | Impossible by construction — the LLM never outputs product data, only requirement/preference JSON. All product data always comes from `data/kohler_products.json`. |

## 6. Compatibility scoring formula

```
final_score = 0.30 * budget_fit
             + 0.25 * space_compatibility
             + 0.20 * style_match
             + 0.15 * feature_match
             + 0.10 * sustainability_score
```

All component scores are 0-100. Weights are configurable via the `weights` argument
to `src.scoring.compute_scores` / `src.optimizer.optimize`. Hard constraints (category,
required features, explicit finish, physical clearance vs. room size) are always
enforced **before** scoring — a product that fails a hard constraint is removed from
consideration entirely, never merely down-scored.

## 7. Test scenarios

Three scenarios you can paste into the natural-language box to demonstrate robustness:

1. **Normal feasible design** —
   `"My bathroom is 8 x 6 feet. My budget is Rs 3,00,000. I want a minimalist Japanese Zen bathroom with a smart toilet, shower, faucet and vanity. Prioritize water efficiency."`
2. **Budget-constrained design** —
   `"My bathroom is 6 x 5 feet. My budget is Rs 1,20,000. I want a modern bathroom with a smart toilet, shower, faucet and vanity."`
   (Demonstrates the "no feasible combination" path and the specific overage message.)
3. **Impossible / no-feasible design** —
   `"My bathroom is 4 x 3 feet. My budget is Rs 50,000. I need a smart toilet with a heated seat, bidet, and app control, plus a shower and vanity."`
   (Demonstrates hard clearance/budget rejection with explicit reasons.)

After any of these, try the redesign box: `"Make it more luxurious without increasing my budget"`.

## 8. What was intentionally left out of this MVP

Per the spec's scope guidance: no 3D renderer, no custom ML model training/fine-tuning,
no mobile app, no microservices, no authentication, no real-time e-commerce or live
KOHLER inventory integration, and no large-scale product scraping. The focus is a
reliable constraint engine, transparent scoring, and a readable 2D layout.

## 9. Submission deliverables checklist

- [x] GitHub repository — this codebase
- [x] Working Streamlit prototype
- [x] Prompts documentation — `prompts/prompts_documentation.md`
- [ ] Demo video (1-3 min) — record after running locally, link in `demo/demo_video_link.txt`
- [ ] 4-slide presentation PDF — put in `presentation/`
