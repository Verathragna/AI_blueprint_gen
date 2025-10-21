from __future__ import annotations

from typing import List

from backend.models.schema import Brief, LayoutResult
from backend.solver.costs import evaluate_cost, aggregate_cost
from backend.models.scene import from_brief_and_layout


def propose_variants(layout: LayoutResult | dict, brief: Brief | dict, k: int = 3) -> List[LayoutResult]:
    """Generate k simple heuristic variants by jittering room sizes/positions."""
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    variants: List[LayoutResult] = []
    for i in range(k):
        # shallow copy of rooms with small deterministic jitters
        rooms = []
        for idx, r in enumerate(layout.rooms):
            dx = (i + 1) * 5 * ((idx % 2) * 2 - 1)
            dy = (i + 1) * 3 * (((idx + 1) % 2) * 2 - 1)
            dw = (i + 1) * 4 * (1 if idx % 3 == 0 else -1)
            dh = (i + 1) * 4 * (-1 if idx % 3 == 0 else 1)
            x = max(0, min(r.x + dx, brief.building_w - 1))
            y = max(0, min(r.y + dy, brief.building_h - 1))
            w = max(1, min(r.w + dw, brief.building_w - x))
            h = max(1, min(r.h + dh, brief.building_h - y))
            rooms.append(type(r)(name=r.name, x=x, y=y, w=w, h=h))
        variants.append(LayoutResult(rooms=rooms, dropped=list(layout.dropped)))
    return variants


def score_layout(layout: LayoutResult | dict, brief: Brief | dict) -> float:
    """Higher is better. Uses negative weighted cost as score."""
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    scene = from_brief_and_layout(brief, layout)
    terms = evaluate_cost(scene, brief)
    total, _ = aggregate_cost(terms, brief)
    # penalize dropped rooms
    total += 10.0 * len(layout.dropped)
    return -total
