from __future__ import annotations

from typing import Dict, Any, List, Tuple

try:
    from ortools.sat.python import cp_model
except Exception:  # pragma: no cover
    cp_model = None

from backend.models.schema import Brief, LayoutResult, PlacedRoom, RoomSpec


def _choose_size(spec: RoomSpec) -> Tuple[int, int]:
    # Fixed size from target or min dims
    if spec.target_area:
        import math

        w0 = max(spec.min_w, int(math.sqrt(spec.target_area)))
        h0 = max(spec.min_h, int(math.ceil(spec.target_area / w0)))
        return w0, h0
    return spec.min_w, spec.min_h


def solve_rect_pack(brief: Brief | Dict[str, Any], seed: LayoutResult | Dict[str, Any] | None = None, time_limit_s: float = 0.5) -> LayoutResult | None:
    if cp_model is None:
        return None
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    model = cp_model.CpModel()

    n = len(brief.rooms)
    if n == 0:
        return LayoutResult(rooms=[], dropped=[])

    # fixed sizes
    sizes = [_choose_size(s) for s in brief.rooms]

    X = [model.NewIntVar(0, brief.building_w, f"x_{i}") for i in range(n)]
    Y = [model.NewIntVar(0, brief.building_h, f"y_{i}") for i in range(n)]
    X2 = []
    Y2 = []
    Xiv = []
    Yiv = []

    for i, (w, h) in enumerate(sizes):
        x2 = model.NewIntVar(0, brief.building_w, f"x2_{i}")
        y2 = model.NewIntVar(0, brief.building_h, f"y2_{i}")
        model.Add(x2 == X[i] + w)
        model.Add(y2 == Y[i] + h)
        model.Add(x2 <= brief.building_w)
        model.Add(y2 <= brief.building_h)
        X2.append(x2)
        Y2.append(y2)
        sx = model.NewIntVar(w, w, f"sx_{i}")
        sy = model.NewIntVar(h, h, f"sy_{i}")
        Xiv.append(model.NewIntervalVar(X[i], sx, x2, f"xint_{i}"))
        Yiv.append(model.NewIntervalVar(Y[i], sy, y2, f"yint_{i}"))

    # Non-overlap
    model.AddNoOverlap2D(Xiv, Yiv)

    # Seed hint
    if seed is not None:
        if not isinstance(seed, LayoutResult):
            seed = LayoutResult(**seed)
        name_to_index = {s.name: i for i, s in enumerate(brief.rooms)}
        for pr in seed.rooms:
            i = name_to_index.get(pr.name)
            if i is not None:
                model.AddHint(X[i], pr.x)
                model.AddHint(Y[i], pr.y)

    # Objective: minimize adjacency distances for preferred pairs
    # Build list of preferred pairs
    prefs: List[Tuple[int, int]] = []
    if brief.soft and brief.soft.adjacency:
        name_to_index = {s.name: i for i, s in enumerate(brief.rooms)}
        for pref in brief.soft.adjacency:
            a = name_to_index.get(pref.a)
            b = name_to_index.get(pref.b)
            if a is not None and b is not None:
                prefs.append((a, b))
    # legacy tuple support
    for (a_name, b_name) in brief.adjacency_preferences:
        name_to_index = {s.name: i for i, s in enumerate(brief.rooms)}
        a = name_to_index.get(a_name)
        b = name_to_index.get(b_name)
        if a is not None and b is not None:
            prefs.append((a, b))

    dist_terms = []
    for (i, j) in prefs:
        # centers (using fixed sizes)
        cx_i = model.NewIntVar(0, brief.building_w, f"cx_{i}")
        cy_i = model.NewIntVar(0, brief.building_h, f"cy_{i}")
        cx_j = model.NewIntVar(0, brief.building_w, f"cx_{j}")
        cy_j = model.NewIntVar(0, brief.building_h, f"cy_{j}")
        wi, hi = sizes[i]
        wj, hj = sizes[j]
        model.Add(cx_i == X[i] + wi // 2)
        model.Add(cy_i == Y[i] + hi // 2)
        model.Add(cx_j == X[j] + wj // 2)
        model.Add(cy_j == Y[j] + hj // 2)
        dx = model.NewIntVar(0, brief.building_w, f"dx_{i}_{j}")
        dy = model.NewIntVar(0, brief.building_h, f"dy_{i}_{j}")
        model.AddAbsEquality(dx, cx_i - cx_j)
        model.AddAbsEquality(dy, cy_i - cy_j)
        dist = model.NewIntVar(0, brief.building_w + brief.building_h, f"d_{i}_{j}")
        model.Add(dist == dx + dy)
        dist_terms.append(dist)

    if dist_terms:
        model.Minimize(sum(dist_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_search_workers = 8
    res = solver.Solve(model)
    if res not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    rooms = []
    for i, spec in enumerate(brief.rooms):
        wi, hi = sizes[i]
        x = int(solver.Value(X[i]))
        y = int(solver.Value(Y[i]))
        rooms.append(PlacedRoom(name=spec.name, x=x, y=y, w=wi, h=hi))
    return LayoutResult(rooms=rooms, dropped=[])
