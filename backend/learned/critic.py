from __future__ import annotations

from typing import Dict

from backend.models.schema import Brief, LayoutResult
from backend.solver.costs import evaluate_cost, aggregate_cost
from backend.geometry.openings import apply_openings
from backend.geometry.stairs import ensure_stairs
from backend.models.scene import from_brief_and_layout


class Critic:
    """Learned critic stub: combines weighted soft cost with simple daylight heuristics."""

    def score(self, brief: Brief | dict, layout: LayoutResult | dict) -> float:
        if not isinstance(brief, Brief):
            brief = Brief(**brief)
        if not isinstance(layout, LayoutResult):
            layout = LayoutResult(**layout)
        # Build scene and ensure openings/stairs for daylight estimation
        scene = from_brief_and_layout(brief, layout)
        scene = apply_openings(scene)
        scene = ensure_stairs(scene)
        # Base soft costs
        terms = evaluate_cost(scene, brief)
        total, _ = aggregate_cost(terms, brief)
        # Daylight: penalize rooms without any windows
        daylight_penalty = 0.0
        for f in scene.floors:
            for sp in f.spaces:
                win_count = sum(1 for op in sp.openings if op.opening_type.name == 'WINDOW')
                if win_count == 0:
                    daylight_penalty += 1.0
        return -(total + 0.5 * daylight_penalty)
