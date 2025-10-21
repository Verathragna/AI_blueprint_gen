from __future__ import annotations

from typing import Dict, List

from backend.models.scene import Building


def analyze_facade(building: Building) -> Dict[str, object]:
    """Site/Facade heuristics: window-to-wall ratios per facade (N,E,S,W)."""
    W, H = building.width, building.height
    # Per-facade window length approximations
    win = {"N": 0.0, "S": 0.0, "E": 0.0, "W": 0.0}
    for f in building.floors:
        for sp in f.spaces:
            x0, y0, w, h = sp.rect.x, sp.rect.y, sp.rect.w, sp.rect.h
            # classify window openings by facade
            for op in sp.openings:
                # top edge -> North (y==0), bottom -> South, left -> West (x==0), right -> East
                if abs(op.at.y - 0.0) < 1e-6:
                    win["N"] += op.w
                elif abs(op.at.y - H) < 1e-6:
                    win["S"] += op.w
                elif abs(op.at.x - 0.0) < 1e-6:
                    win["W"] += op.w
                elif abs(op.at.x - W) < 1e-6:
                    win["E"] += op.w
    perim = 2 * (W + H)
    total_win = sum(win.values())
    wwr_overall = total_win / perim if perim > 0 else 0.0
    wwr = {k: (win[k] / (W if k in ("N", "S") else H) if (W if k in ("N","S") else H) > 0 else 0.0) for k in win}

    suggestions: List[str] = []
    if wwr_overall < 0.15:
        suggestions.append("Overall WWR low; consider adding windows for daylight.")
    if wwr_overall > 0.45:
        suggestions.append("Overall WWR high; consider shading or reducing glazing for energy.")
    if wwr.get("W", 0.0) > 0.4:
        suggestions.append("High west-facing glazing; consider shading to reduce heat gain.")

    return {"wwr_overall": wwr_overall, "wwr_facade": wwr, "suggestions": suggestions}
