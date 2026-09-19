"""
scoring.py
----------
Deterministic, transparent compatibility scoring for a product combination.

This module contains NO calls to any LLM. Every number produced here is
computed from plain Python arithmetic on the structured requirements and
the local product catalog, so the score can always be explained and
reproduced. This is the "Critical Design Principle" from the spec:
the LLM never makes hard product/space/budget decisions.

All component scores are 0-100. The final score is a configurable weighted
sum of the components (default weights follow the spec's suggested formula).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


DEFAULT_WEIGHTS = {
    "budget_fit": 0.30,
    "space_compatibility": 0.25,
    "style_match": 0.20,
    "feature_match": 0.15,
    "sustainability_score": 0.10,
}


@dataclass
class ComponentScores:
    budget_fit: float
    space_compatibility: float
    style_match: float
    feature_match: float
    sustainability_score: float

    def as_dict(self) -> Dict[str, float]:
        return {
            "budget_fit": round(self.budget_fit, 1),
            "space_compatibility": round(self.space_compatibility, 1),
            "style_match": round(self.style_match, 1),
            "feature_match": round(self.feature_match, 1),
            "sustainability_score": round(self.sustainability_score, 1),
        }


def normalize_weights(weights: Optional[Dict[str, float]]) -> Dict[str, float]:
    """Ensure weights are present and sum to 1.0 (renormalizes if needed)."""
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)
    total = sum(w.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {k: v / total for k, v in w.items()}


def score_budget_fit(total_cost: float, budget: float) -> float:
    """
    100 = uses the budget efficiently without going over.
    Scales down sharply once the combination exceeds budget.
    """
    if budget <= 0:
        return 0.0
    if total_cost <= budget:
        # Reward combinations that use a healthy fraction of the budget
        # (very low usage isn't penalized much, but using ~70-100% scores highest)
        usage_ratio = total_cost / budget
        return max(0.0, min(100.0, 60 + 40 * usage_ratio))
    # Over budget: hard penalty proportional to overage percentage
    overage_ratio = (total_cost - budget) / budget
    return max(0.0, 100 - overage_ratio * 200)


def score_space_compatibility(products: List[dict], room_length_ft: float, room_width_ft: float) -> float:
    """
    Approximates whether the selected fixtures plus their required clearances
    plausibly fit in the given room footprint. This is a simplified
    footprint/clearance heuristic, not a true 2D bin-packing solver.
    """
    if room_length_ft <= 0 or room_width_ft <= 0:
        return 50.0  # unknown room size -> neutral score

    room_area_in2 = (room_length_ft * 12) * (room_width_ft * 12)
    used_area_in2 = 0.0
    max_clearance_violation = 0.0
    room_min_dim_in = min(room_length_ft, room_width_ft) * 12

    for p in products:
        footprint = p["width_in"] * p["depth_in"]
        clearance_needed = max(p.get("clearance_front_in", 0), p.get("clearance_side_in", 0))
        used_area_in2 += footprint
        # Penalize if a single required clearance is larger than the room's shortest wall
        if clearance_needed > room_min_dim_in:
            max_clearance_violation += (clearance_needed - room_min_dim_in)

    area_ratio = used_area_in2 / room_area_in2 if room_area_in2 else 1.0
    # A healthy bathroom layout uses roughly 35-65% of floor area for fixtures + clearances combined
    if area_ratio <= 0.65:
        area_score = 100 - (area_ratio / 0.65) * 20  # 80-100 for well within space
    else:
        overshoot = area_ratio - 0.65
        area_score = max(0.0, 80 - overshoot * 300)

    clearance_penalty = min(60.0, max_clearance_violation * 2)
    return max(0.0, min(100.0, area_score - clearance_penalty))


def score_style_match(products: List[dict], target_style: Optional[str]) -> float:
    """Fraction of selected products whose style list contains the target style."""
    if not target_style:
        return 70.0  # no style requested -> neutral-positive default
    target_style = target_style.lower().replace(" ", "_")
    if not products:
        return 0.0
    hits = sum(1 for p in products if target_style in [s.lower() for s in p.get("styles", [])])
    return 100.0 * hits / len(products)


def score_feature_match(products: List[dict], desired_features: List[str], smart_preferred: bool) -> float:
    """Checks how many desired features/preferences are actually present."""
    checks = []
    desired = [f.lower() for f in (desired_features or [])]

    for p in products:
        p_features = [f.lower() for f in p.get("features", [])]
        if desired:
            matched = sum(1 for d in desired if any(d in pf or pf in d for pf in p_features))
            checks.append(matched / max(1, len(desired)))
        if smart_preferred:
            checks.append(1.0 if p.get("smart") else 0.0)

    if not checks:
        return 70.0  # no explicit feature preferences -> neutral-positive default
    return 100.0 * (sum(checks) / len(checks))


def score_sustainability(products: List[dict], water_efficiency_preferred: bool) -> float:
    """Average water_efficiency_score (1-5) normalized to 0-100."""
    if not products:
        return 0.0
    avg = sum(p.get("water_efficiency_score", 3) for p in products) / len(products)
    base = (avg / 5.0) * 100.0
    if water_efficiency_preferred:
        return base  # already reflects it directly
    return base


def compute_scores(
    products: List[dict],
    total_cost: float,
    budget: float,
    room_length_ft: float,
    room_width_ft: float,
    target_style: Optional[str],
    desired_features: List[str],
    smart_preferred: bool,
    water_efficiency_preferred: bool,
    weights: Optional[Dict[str, float]] = None,
) -> Dict:
    """Compute all component scores + the final weighted score for one combination."""
    w = normalize_weights(weights)

    components = ComponentScores(
        budget_fit=score_budget_fit(total_cost, budget),
        space_compatibility=score_space_compatibility(products, room_length_ft, room_width_ft),
        style_match=score_style_match(products, target_style),
        feature_match=score_feature_match(products, desired_features, smart_preferred),
        sustainability_score=score_sustainability(products, water_efficiency_preferred),
    )

    final_score = (
        w["budget_fit"] * components.budget_fit
        + w["space_compatibility"] * components.space_compatibility
        + w["style_match"] * components.style_match
        + w["feature_match"] * components.feature_match
        + w["sustainability_score"] * components.sustainability_score
    )

    return {
        "final_score": round(max(0.0, min(100.0, final_score)), 1),
        "components": components.as_dict(),
        "weights_used": w,
    }
