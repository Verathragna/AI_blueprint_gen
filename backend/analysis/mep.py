from __future__ import annotations

from typing import Dict, List, Tuple
import math

from backend.models.scene import Building, Space, Point


def analyze_mep(building: Building) -> Dict[str, object]:
    """MEP heuristics: stack wet rooms, estimate distances to stack, suggest chases.
    Returns dict with stack_point, avg_distance, has_mechanical, suggestions, chases.
    """
    wet_keywords = ("bath", "toilet", "wc", "kitchen", "laundry")
    wets: List[Space] = []
    for f in building.floors:
        for sp in f.spaces:
            if any(k in sp.name.lower() for k in wet_keywords):
                wets.append(sp)
    if not wets:
        return {"stack_point": None, "avg_distance": 0.0, "has_mechanical": False, "suggestions": [], "chases": []}

    # stack point at mean of wet centroids on first floor
    cx = sum(sp.rect.x + sp.rect.w / 2 for sp in wets) / len(wets)
    cy = sum(sp.rect.y + sp.rect.h / 2 for sp in wets) / len(wets)
    # distances
    dists: List[float] = []
    for sp in wets:
        sx = sp.rect.x + sp.rect.w / 2
        sy = sp.rect.y + sp.rect.h / 2
        dists.append(abs(sx - cx) + abs(sy - cy))
    avg_d = sum(dists) / len(dists)

    # chases: reserve a vertical chase rectangle at stack x across floors
    chases: List[Dict[str, float]] = []
    chase_w = 200.0
    for f in building.floors:
        chases.append({"floor_elev": f.elevation, "x": cx - chase_w / 2, "y": 0.0, "w": chase_w, "h": building.height})

    has_mech = any("mech" in sp.name.lower() for f in building.floors for sp in f.spaces)
    suggestions: List[str] = []
    if avg_d > 4000.0:
        suggestions.append("Wet rooms are far from stack; consider clustering or adding branch stacks.")
    if not has_mech:
        suggestions.append("Add a mechanical/utility room with access to exterior and stack.")

    return {"stack_point": {"x": cx, "y": cy}, "avg_distance": avg_d, "has_mechanical": has_mech, "suggestions": suggestions, "chases": chases}
