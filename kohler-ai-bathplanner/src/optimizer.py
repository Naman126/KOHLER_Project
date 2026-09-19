"""
optimizer.py
------------
Deterministic combination optimizer.

Given the surviving products per required category (already hard-filtered
by constraint_engine.py), this module generates every combination
(one product per required category), computes cost + compatibility score
for each via scoring.py, and returns the ranked list of feasible
combinations plus a summary of near-miss combinations that were rejected
for exceeding budget.

For a ~20-product prototype catalog with 4 categories and up to 5 options
each, a full cartesian product is at most 5^4 = 625 combinations, which is
trivial to search exhaustively. No external optimization library is needed
(per spec section 13: "do not over-engineer this").
"""

import itertools
from typing import Dict, List, Optional

from src.scoring import compute_scores


def generate_combinations(survivors_by_category: Dict[str, List[dict]]) -> List[List[dict]]:
    """Cartesian product across categories: one product from each required category."""
    categories = list(survivors_by_category.keys())
    option_lists = [survivors_by_category[c] for c in categories]
    if not option_lists or any(len(opts) == 0 for opts in option_lists):
        return []
    return [list(combo) for combo in itertools.product(*option_lists)]


def optimize(
    survivors_by_category: Dict[str, List[dict]],
    requirements: dict,
    weights: Optional[Dict[str, float]] = None,
    top_n: int = 5,
) -> Dict:
    """
    Returns a dict:
      {
        "feasible": bool,
        "top_combinations": [ {products, total_cost, scores}, ... ]  # ranked, best first
        "over_budget_examples": [ {products, total_cost, overage}, ... ]  # for explainability
        "empty_categories": [category, ...]  # categories with zero surviving products
      }
    """
    bathroom = requirements.get("bathroom", {}) or {}
    budget_info = requirements.get("budget", {}) or {}
    room_length_ft = bathroom.get("length_ft") or 0
    room_width_ft = bathroom.get("width_ft") or 0
    budget = budget_info.get("amount") or 0

    preferences = requirements.get("preferences", {}) or {}
    target_style = requirements.get("style")
    desired_features = preferences.get("desired_features") or preferences.get("required_features") or []
    smart_preferred = bool(preferences.get("smart_features"))
    water_pref = bool(preferences.get("sustainability") or preferences.get("water_efficiency"))

    empty_categories = [c for c, opts in survivors_by_category.items() if len(opts) == 0]
    combinations = generate_combinations(survivors_by_category)

    scored_all = []
    for combo in combinations:
        total_cost = sum(p["price_inr"] for p in combo)
        result = compute_scores(
            products=combo,
            total_cost=total_cost,
            budget=budget,
            room_length_ft=room_length_ft,
            room_width_ft=room_width_ft,
            target_style=target_style,
            desired_features=desired_features,
            smart_preferred=smart_preferred,
            water_efficiency_preferred=water_pref,
            weights=weights,
        )
        scored_all.append({
            "products": combo,
            "total_cost": total_cost,
            "within_budget": total_cost <= budget if budget else True,
            **result,
        })

    feasible = [c for c in scored_all if c["within_budget"]]
    infeasible = [c for c in scored_all if not c["within_budget"]]

    feasible.sort(key=lambda c: c["final_score"], reverse=True)
    infeasible.sort(key=lambda c: c["total_cost"])  # closest-to-budget first

    return {
        "feasible": len(feasible) > 0,
        "top_combinations": feasible[:top_n],
        "over_budget_examples": infeasible[:3],
        "empty_categories": empty_categories,
        "total_combinations_evaluated": len(scored_all),
    }
