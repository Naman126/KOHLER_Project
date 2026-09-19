"""
layout_generator.py
---------------------
Generates a simple, readable 2D floor plan (to scale) for the selected
products, using a deterministic rule-based placement strategy:
  - Vanity along the back wall, centered
  - Shower in a back corner
  - Smart toilet along the side wall
  - Faucet is drawn as part of the vanity (not placed separately)

This is intentionally simple (per spec section 14: "avoid building a full
CAD or 3D engine"). No LLM involvement -- purely geometric placement based
on each product's declared width/depth in inches.
"""

import io
from typing import List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches


CATEGORY_COLORS = {
    "smart_toilet": "#8ecae6",
    "shower": "#a2d2ff",
    "vanity": "#ffb703",
    "faucet": "#fb8500",
}

CATEGORY_LABELS = {
    "smart_toilet": "Smart Toilet",
    "shower": "Shower",
    "vanity": "Vanity",
    "faucet": "Faucet",
}


def _place_fixtures(products: List[dict], room_w_in: float, room_l_in: float):
    """
    Simple deterministic placement along the back wall (shower + vanity side
    by side) and the toilet along the front-right wall. Widths are scaled
    down proportionally -- never overlapped -- whenever the fixtures don't
    both fit within the room's width at their catalog dimensions.

    Returns a list of dicts: {category, name, x, y, w, d}
    """
    placements = []
    by_category = {p["category"]: p for p in products}

    margin = 4  # inches of wall margin
    gap = 3  # inches of clear gap between adjacent fixtures

    shower = by_category.get("shower")
    vanity = by_category.get("vanity")

    shower_w = min(shower["width_in"], room_w_in * 0.55) if shower else 0
    shower_d = min(shower["depth_in"], room_l_in * 0.5) if shower else 0
    vanity_w = min(vanity["width_in"], room_w_in - 2 * margin) if vanity else 0
    vanity_d = min(vanity["depth_in"], room_l_in * 0.3) if vanity else 0

    # Scale both down proportionally if they wouldn't fit side by side without overlapping
    available_width = room_w_in - 2 * margin - gap
    combined = shower_w + vanity_w
    if combined > available_width > 0:
        scale = available_width / combined
        shower_w *= scale
        vanity_w *= scale

    if shower:
        placements.append({
            "category": "shower", "name": shower["name"],
            "x": margin, "y": room_l_in - shower_d - margin,
            "w": shower_w, "d": shower_d,
        })

    if vanity:
        x = margin + shower_w + gap if shower else margin
        placements.append({
            "category": "vanity", "name": vanity["name"],
            "x": x, "y": room_l_in - vanity_d - margin,
            "w": vanity_w, "d": vanity_d,
        })

    if "smart_toilet" in by_category:
        t = by_category["smart_toilet"]
        w = min(t["width_in"], room_w_in * 0.3)
        d = min(t["depth_in"], room_l_in * 0.4)
        x = room_w_in - w - margin
        y = margin
        placements.append({
            "category": "smart_toilet", "name": t["name"],
            "x": x, "y": y, "w": w, "d": d,
        })

    return placements


def generate_layout_png(
    products: List[dict],
    room_length_ft: float,
    room_width_ft: float,
    title: str = "2D Bathroom Floor Plan",
) -> Optional[bytes]:
    """
    Returns PNG image bytes of the floor plan, or None if room dimensions
    are missing/invalid (caller should show a friendly message instead).
    """
    if not room_length_ft or not room_width_ft or room_length_ft <= 0 or room_width_ft <= 0:
        return None

    room_l_in = room_length_ft * 12
    room_w_in = room_width_ft * 12

    fig, ax = plt.subplots(figsize=(6, 6 * room_l_in / room_w_in if room_w_in else 6))

    # Room boundary
    ax.add_patch(patches.Rectangle((0, 0), room_w_in, room_l_in, fill=False, edgecolor="black", linewidth=2))

    placements = _place_fixtures(products, room_w_in, room_l_in)
    for item in placements:
        color = CATEGORY_COLORS.get(item["category"], "#cccccc")
        ax.add_patch(patches.Rectangle(
            (item["x"], item["y"]), item["w"], item["d"],
            facecolor=color, edgecolor="black", linewidth=1.2, alpha=0.85,
        ))
        label = CATEGORY_LABELS.get(item["category"], item["category"])
        ax.text(
            item["x"] + item["w"] / 2, item["y"] + item["d"] / 2,
            f"{label}\n{item['w']:.0f}\"×{item['d']:.0f}\"",
            ha="center", va="center", fontsize=8, wrap=True,
        )

    # Faucet annotation on the vanity, if present
    faucet = next((p for p in products if p["category"] == "faucet"), None)
    vanity_placement = next((pl for pl in placements if pl["category"] == "vanity"), None)
    if faucet and vanity_placement:
        ax.text(
            vanity_placement["x"] + vanity_placement["w"] / 2,
            vanity_placement["y"] + vanity_placement["d"] + 4,
            f"Faucet: {faucet['name']}",
            ha="center", va="bottom", fontsize=7, style="italic",
        )

    ax.set_xlim(-6, room_w_in + 6)
    ax.set_ylim(-6, room_l_in + 6)
    ax.set_aspect("equal")
    ax.set_title(
        f"{title}\nRoom: {room_length_ft:.0f} ft (length) × {room_width_ft:.0f} ft (width) "
        f"— drawn to scale in inches"
    )
    ax.set_xlabel("inches")
    ax.set_ylabel("inches")
    ax.grid(True, linestyle="--", alpha=0.3)

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
