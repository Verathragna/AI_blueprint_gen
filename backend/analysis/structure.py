from __future__ import annotations

from typing import Dict, List, Tuple

from backend.models.scene import Building


def analyze_structure(building: Building) -> Dict[str, object]:
    """Heuristic structural analysis: span limits and alignment across floors.
    Returns dict with recommended_system, span_stats, alignment_score, warnings.
    """
    # Span thresholds in mm
    systems = {
        "joists": 6000,
        "trusses": 9000,
        "steel": 12000,
    }
    spans: List[float] = []
    for f in building.floors:
        for sp in f.spaces:
            spans.append(max(sp.rect.w, sp.rect.h))
    spans.sort()
    p95 = spans[int(0.95 * (len(spans) - 1))] if spans else 0.0
    # choose smallest system that accommodates p95
    recommended = "joists"
    for name, lim in systems.items():
        if p95 <= lim:
            recommended = name
            break
        recommended = name

    # alignment score: compare vertical grid lines across floors
    def floor_grid_x(floor) -> List[float]:
        xs: List[float] = []
        for sp in floor.spaces:
            xs.append(sp.rect.x)
            xs.append(sp.rect.x + sp.rect.w)
        return sorted(set(xs))

    def score_alignment(base: List[float], other: List[float], tol: float = 50.0) -> float:
        if not base or not other:
            return 0.0
        m = 0
        for x in base:
            if any(abs(x - y) <= tol for y in other):
                m += 1
        return m / len(base)

    align_scores: List[float] = []
    if building.floors:
        base = floor_grid_x(building.floors[0])
        for f in building.floors[1:]:
            align_scores.append(score_alignment(base, floor_grid_x(f)))
    alignment_score = sum(align_scores) / len(align_scores) if align_scores else 1.0

    warnings: List[str] = []
    # warn if any span exceeds recommended system by >10%
    lim = systems[recommended]
    for s in spans:
        if s > lim * 1.1:
            warnings.append(f"Span {int(s)} exceeds recommended {recommended} limit {lim}")
            break

    return {
        "recommended_system": recommended,
        "span_stats": {"p95": p95, "max": max(spans) if spans else 0.0},
        "alignment_score": alignment_score,
        "warnings": warnings,
    }
