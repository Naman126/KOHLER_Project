"""
recommendation_engine.py
--------------------------
Orchestrates the deterministic pipeline:
  requirements -> constraint_engine (hard filter) -> optimizer (rank) -> result

Also builds the explainability payload and requests a natural-language
explanation from llm_service (with a deterministic fallback so the app
never shows a blank or broken explanation if the LLM call fails).
"""

from typing import Dict, List, Optional

from src import llm_service
from src.constraint_engine import filter_catalog
from src.optimizer import optimize


def _fallback_explanation(context: dict) -> str:
    """Deterministic, template-based explanation used if the LLM is unavailable."""
    picks = context["selected_products"]
    total = context["total_cost"]
    budget = context["budget"]
    remaining = budget - total if budget else None
    scores = context["scores"]["components"]

    lines = []
    style = context.get("style") or "your requested"
    lines.append(
        f"This configuration was selected because it satisfies every required product category "
        f"within your budget of ₹{budget:,.0f}, using ₹{total:,.0f} and leaving "
        f"{'₹{:,.0f} remaining'.format(remaining) if remaining is not None else 'no fixed budget set'}. "
        f"It scored {scores['style_match']:.0f}/100 on style match for a {style} theme, "
        f"{scores['space_compatibility']:.0f}/100 on space compatibility for your room, and "
        f"{scores['sustainability_score']:.0f}/100 on water efficiency."
    )
    lines.append("")
    lines.append("Selected products:")
    for p in picks:
        lines.append(f"- {p['category'].replace('_', ' ').title()}: {p['name']} (₹{p['price_inr']:,})")

    rejected = context.get("notable_rejections") or []
    if rejected:
        lines.append("")
        lines.append("Why not other options?")
        for r in rejected[:3]:
            reason = r["reasons"][0] if r.get("reasons") else "did not meet a hard requirement"
            lines.append(f"- {r['name']}: rejected because {reason}.")

    return "\n".join(lines)


def build_design(catalog: List[dict], requirements: dict, weights: Optional[Dict[str, float]] = None) -> Dict:
    """
    Full deterministic pipeline. Returns a dict describing either:
      - a successful design (status="ok") with products, cost, scores, explanation, rejections
      - a no-feasible-combination result (status="infeasible") with reasons, so the UI can show
        a helpful message instead of crashing.
    """
    required_categories = requirements.get("required_categories") or []
    if not required_categories:
        return {
            "status": "error",
            "message": "No product categories were recognized in your request. "
                       "Please specify at least one of: smart toilet, shower, faucet, vanity.",
        }

    survivors_by_category, rejected_by_category = filter_catalog(catalog, requirements)

    empty_categories = [c for c, opts in survivors_by_category.items() if len(opts) == 0]
    if empty_categories:
        return {
            "status": "infeasible",
            "message": (
                f"No products satisfy your hard constraints for: {', '.join(empty_categories)}. "
                f"Try relaxing a required feature, finish, or checking your room dimensions."
            ),
            "rejected_by_category": rejected_by_category,
        }

    opt_result = optimize(survivors_by_category, requirements, weights=weights)

    if not opt_result["feasible"]:
        # Find the cheapest fully-feasible-by-constraints combination to report the overage
        cheapest = opt_result["over_budget_examples"][0] if opt_result["over_budget_examples"] else None
        budget = (requirements.get("budget") or {}).get("amount") or 0
        if cheapest:
            overage = cheapest["total_cost"] - budget
            message = (
                f"No combination fits within your budget of ₹{budget:,.0f}. "
                f"The lowest-cost feasible combination costs ₹{cheapest['total_cost']:,.0f}, "
                f"which is ₹{overage:,.0f} over budget. Consider raising the budget or "
                f"switching a required category to a more economical style."
            )
        else:
            message = "No feasible combination could be found within the given constraints."
        return {
            "status": "infeasible",
            "message": message,
            "closest_combination": cheapest,
            "rejected_by_category": rejected_by_category,
        }

    best = opt_result["top_combinations"][0]
    budget = (requirements.get("budget") or {}).get("amount") or 0

    # Collect a few notable rejected alternatives (one per required category, if any)
    notable_rejections = []
    for category in required_categories:
        rejects = rejected_by_category.get(category, [])
        if rejects:
            notable_rejections.append(rejects[0])
    # Also surface the closest infeasible (over-budget) alternative combination, if one exists
    over_budget_alt = None
    if opt_result["over_budget_examples"]:
        alt = opt_result["over_budget_examples"][0]
        over_budget_alt = {
            "name": " + ".join(p["name"] for p in alt["products"]),
            "reasons": [f"total configuration exceeded budget by ₹{alt['total_cost'] - budget:,.0f}"],
        }
    if over_budget_alt:
        notable_rejections.append(over_budget_alt)

    explanation_context = {
        "requirements": requirements,
        "selected_products": best["products"],
        "total_cost": best["total_cost"],
        "budget": budget,
        "style": requirements.get("style"),
        "scores": {"final_score": best["final_score"], "components": best["components"]},
        "notable_rejections": notable_rejections,
    }

    explanation = llm_service.generate_explanation_via_llm(explanation_context)
    if not explanation:
        explanation = _fallback_explanation(explanation_context)

    return {
        "status": "ok",
        "selected_products": best["products"],
        "total_cost": best["total_cost"],
        "budget": budget,
        "remaining_budget": budget - best["total_cost"] if budget else None,
        "scores": {"final_score": best["final_score"], "components": best["components"]},
        "explanation": explanation,
        "notable_rejections": notable_rejections,
        "alternatives": opt_result["top_combinations"][1:4],  # next-best options
        "total_combinations_evaluated": opt_result["total_combinations_evaluated"],
    }
