from __future__ import annotations

from typing import Dict, Tuple

from backend.models.graphs import build_graphs
from backend.models.scene import Building
from backend.models.schema import Brief, LayoutResult, SoftObjectives, SoftWeights


def _weights(brief: Brief) -> SoftWeights:
    return brief.weights or SoftWeights()


def evaluate_cost(building: Building, brief: Brief) -> Dict[str, float]:
    """Compute soft costs; lower is better. Returns dict of term->value.
    Terms:
      - adjacency_missing: sum over preferred pairs not adjacent
      - bedroom_privacy: penalties for bedrooms adjacent to living/kitchen
      - aspect_ratio_deviation: sum of |ratio - target| beyond tolerance
      - area_target_deviation: normalized deviation from target areas
    """
    graphs = build_graphs(building)
    room_adj = graphs.get("room_adjacency")

    # name->space lookup (first floor only)
    if not building.floors:
        return {}
    spaces = building.floors[0].spaces
    by_name: Dict[str, str] = {}
    for sp in spaces:
        # If duplicate names, last wins (MVP simplicity)
        by_name[sp.name] = sp.id

    soft = brief.soft or SoftObjectives()
    W = _weights(brief)

    terms: Dict[str, float] = {
        "adjacency_missing": 0.0,
        "bedroom_privacy": 0.0,
        "aspect_ratio_deviation": 0.0,
        "area_target_deviation": 0.0,
        "hub_distance": 0.0,
    }

    # adjacency preferences
    prefs = soft.adjacency[:]
    # support legacy tuples
    prefs += [type("AP", (), {"a": a, "b": b}) for (a, b) in brief.adjacency_preferences]
    for pref in prefs:
        a_id = by_name.get(pref.a)
        b_id = by_name.get(pref.b)
        if not a_id or not b_id:
            terms["adjacency_missing"] += 1.0
            continue
        if not room_adj.has_edge(a_id, b_id):
            terms["adjacency_missing"] += 1.0

    # privacy: bedrooms adjacent to living/kitchen
    if soft.enforce_privacy:
        noisy = {n for n in by_name if any(k in n.lower() for k in ("living", "kitchen"))}
        beds = {n for n in by_name if "bed" in n.lower()}
        for bn in beds:
            b_id = by_name[bn]
            for nn in noisy:
                n_id = by_name[nn]
                if room_adj.has_edge(b_id, n_id):
                    terms["bedroom_privacy"] += 1.0

    # aspect ratio deviation
    target = soft.aspect_ratio_target
    tol = soft.aspect_ratio_tolerance
    for sp in spaces:
        w, h = sp.rect.w, sp.rect.h
        if min(w, h) <= 0:
            continue
        ratio = max(w, h) / min(w, h)
        excess = max(0.0, abs(ratio - target) - tol)
        terms["aspect_ratio_deviation"] += excess

    # hub distance to corridor/living (center-to-center normalized)
    # select hub: corridor else living
    if building.floors:
        spaces = building.floors[0].spaces
        hub = None
        for sp in spaces:
            if sp.name.lower().startswith("corridor"):
                hub = sp; break
        if hub is None:
            for sp in spaces:
                if sp.name.lower().startswith("living"):
                    hub = sp; break
        if hub is None and spaces:
            hub = spaces[0]
        if hub is not None:
            hx, hy = hub.rect.x + hub.rect.w/2, hub.rect.y + hub.rect.h/2
            norm = max(1.0, building.width + building.height)
            for sp in spaces:
                if sp is hub:
                    continue
                cx, cy = sp.rect.x + sp.rect.w/2, sp.rect.y + sp.rect.h/2
                terms["hub_distance"] += (abs(cx - hx) + abs(cy - hy)) / norm

    # area target deviation (normalize by target to be scale-free)
    spec_targets = {s.name: s.target_area for s in brief.rooms if s.target_area}
    for sp in spaces:
        tgt = spec_targets.get(sp.name)
        if tgt:
            dev = abs((sp.rect.w * sp.rect.h) - tgt) / float(tgt)
            terms["area_target_deviation"] += dev

    # apply weights for reporting (we keep unweighted terms, aggregator will weight)
    return terms


def aggregate_cost(terms: Dict[str, float], brief: Brief) -> Tuple[float, Dict[str, float]]:
    W = _weights(brief)
    weighted = {
        "adjacency_missing": terms.get("adjacency_missing", 0.0) * W.adjacency_missing,
        "bedroom_privacy": terms.get("bedroom_privacy", 0.0) * W.bedroom_privacy,
        "aspect_ratio_deviation": terms.get("aspect_ratio_deviation", 0.0) * W.aspect_ratio_deviation,
        "area_target_deviation": terms.get("area_target_deviation", 0.0) * W.area_target_deviation,
        "hub_distance": terms.get("hub_distance", 0.0) * (getattr(W, 'hub_distance', 0.3)),
    }
    total = sum(weighted.values())
    return total, weighted
