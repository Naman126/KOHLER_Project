"""
constraint_engine.py
---------------------
Deterministic hard-constraint filtering. No LLM calls happen here.

Given the structured requirements JSON and the product catalog, this module
returns, for each required category, the list of products that survive
every HARD constraint (budget per-item ceiling is NOT enforced here -- that
is a combination-level concern handled by the optimizer -- but category,
required features, explicitly-hard finish, and basic clearance-vs-room
checks are enforced here).
"""

from typing import Dict, List, Tuple


def room_min_dimension_in(requirements: dict) -> float:
    bathroom = requirements.get("bathroom", {}) or {}
    length = bathroom.get("length_ft") or 0
    width = bathroom.get("width_ft") or 0
    if length and width:
        return min(length, width) * 12
    return float("inf")  # unknown room size -> don't reject on clearance


def product_passes_hard_constraints(product: dict, requirements: dict) -> Tuple[bool, List[str]]:
    """
    Returns (passes, reasons_for_rejection). If passes is True, reasons is empty.
    """
    reasons = []
    hard_constraints = requirements.get("hard_constraints", []) or []
    hard_set = {str(c).lower() for c in hard_constraints}

    # 1. Required features (if features are marked as a hard constraint)
    if "required_features" in hard_set or "features" in hard_set:
        required_features = requirements.get("preferences", {}).get("required_features") or []
        product_features = [f.lower() for f in product.get("features", [])]
        missing = [
            rf for rf in required_features
            if not any(rf.lower() in pf or pf in rf.lower() for pf in product_features)
        ]
        if missing:
            reasons.append(f"missing required feature(s): {', '.join(missing)}")

    # 2. Explicit hard finish requirement
    if "finish" in hard_set:
        wanted_finish = (requirements.get("preferences", {}) or {}).get("finish")
        if wanted_finish:
            wanted_finish_norm = wanted_finish.lower().replace(" ", "_")
            available = [f.lower() for f in product.get("finishes", [])]
            if wanted_finish_norm not in available:
                reasons.append(f"finish '{wanted_finish}' not available")

    # 3. Clearance vs. the room's shortest wall (a physically impossible fixture is always rejected,
    #    regardless of whether the user marked space as a hard constraint, since it cannot be installed)
    min_dim = room_min_dimension_in(requirements)
    clearance_needed = max(product.get("clearance_front_in", 0), product.get("clearance_side_in", 0))
    fixture_span = max(product.get("width_in", 0), product.get("depth_in", 0))
    if fixture_span > min_dim:
        reasons.append(
            f"fixture footprint ({fixture_span:.0f} in) exceeds the room's shortest wall ({min_dim:.0f} in)"
        )
    elif clearance_needed > min_dim:
        reasons.append(
            f"required clearance ({clearance_needed:.0f} in) exceeds the room's shortest wall ({min_dim:.0f} in)"
        )

    return (len(reasons) == 0, reasons)


def filter_by_category(
    catalog: List[dict],
    category: str,
    requirements: dict,
) -> Tuple[List[dict], List[Dict]]:
    """
    Returns (surviving_products, rejected_with_reasons) for one category.
    rejected_with_reasons is a list of {"product": name, "id": id, "reasons": [...]}
    """
    survivors = []
    rejected = []
    for p in catalog:
        if p.get("category") != category:
            continue
        ok, reasons = product_passes_hard_constraints(p, requirements)
        if ok:
            survivors.append(p)
        else:
            rejected.append({"id": p["id"], "name": p["name"], "reasons": reasons})
    return survivors, rejected


def filter_catalog(catalog: List[dict], requirements: dict) -> Tuple[Dict[str, List[dict]], Dict[str, List[Dict]]]:
    """
    Runs filter_by_category for every required category in the requirements.
    Returns (survivors_by_category, rejected_by_category).
    """
    required_categories = requirements.get("required_categories") or []
    survivors_by_category = {}
    rejected_by_category = {}

    for category in required_categories:
        survivors, rejected = filter_by_category(catalog, category, requirements)
        survivors_by_category[category] = survivors
        rejected_by_category[category] = rejected

    return survivors_by_category, rejected_by_category
