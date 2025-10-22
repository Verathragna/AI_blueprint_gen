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


def _find_hub_index(brief: Brief) -> int:
    for i, s in enumerate(brief.rooms):
        if s.name.lower().startswith("corridor"):
            return i
    for i, s in enumerate(brief.rooms):
        if s.name.lower().startswith("living"):
            return i
    return 0


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

    # Hard connectivity to hub
    hub = _find_hub_index(brief)
    for i in range(n):
        if i == hub:
            continue
        touchL = model.NewBoolVar(f"touchL_{i}")
        touchR = model.NewBoolVar(f"touchR_{i}")
        touchT = model.NewBoolVar(f"touchT_{i}")
        touchB = model.NewBoolVar(f"touchB_{i}")
        # Enforce edge equalities when active
        model.Add(X[i] + sizes[i][0] == X[hub]).OnlyEnforceIf(touchL)
        model.Add(X[hub] + sizes[hub][0] == X[i]).OnlyEnforceIf(touchR)
        model.Add(Y[i] + sizes[i][1] == Y[hub]).OnlyEnforceIf(touchT)
        model.Add(Y[hub] + sizes[hub][1] == Y[i]).OnlyEnforceIf(touchB)
        # Require at least one touch
        model.AddBoolOr([touchL, touchR, touchT, touchB])

    # Objective: minimize adjacency distances for preferred pairs and hub distance
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

    # hub distance terms
    for i in range(n):
        if i == hub:
            continue
        hx = model.NewIntVar(0, brief.building_w, f"hcx")
        hy = model.NewIntVar(0, brief.building_h, f"hcy")
        wi, hi = sizes[hub]
        model.Add(hx == X[hub] + wi // 2)
        model.Add(hy == Y[hub] + hi // 2)
        cx = model.NewIntVar(0, brief.building_w, f"cxh_{i}")
        cy = model.NewIntVar(0, brief.building_h, f"cyh_{i}")
        wi2, hi2 = sizes[i]
        model.Add(cx == X[i] + wi2 // 2)
        model.Add(cy == Y[i] + hi2 // 2)
        dx = model.NewIntVar(0, brief.building_w, f"dxh_{i}")
        dy = model.NewIntVar(0, brief.building_h, f"dyh_{i}")
        model.AddAbsEquality(dx, cx - hx)
        model.AddAbsEquality(dy, cy - hy)
        dist_terms.append(dx)
        dist_terms.append(dy)

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


def solve_with_corridor(
    brief: Brief | Dict[str, Any],
    corridor_rect: Dict[str, int],
    seed: LayoutResult | Dict[str, Any] | None = None,
    time_limit_s: float = 1.0,
) -> LayoutResult | None:
    if cp_model is None:
        return None
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    model = cp_model.CpModel()
    n = len(brief.rooms)
    if n == 0:
        return LayoutResult(rooms=[], dropped=[])

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

    # Corridor fixed intervals
    cx = corridor_rect.get("x", 0)
    cy = corridor_rect.get("y", 0)
    cw = corridor_rect.get("w", max(1, brief.building_w))
    ch = corridor_rect.get("h", 120)
    XC = model.NewIntVar(cx, cx, "xc")
    YC = model.NewIntVar(cy, cy, "yc")
    X2C = model.NewIntVar(cx + cw, cx + cw, "x2c")
    Y2C = model.NewIntVar(cy + ch, cy + ch, "y2c")
    SXc = model.NewIntVar(cw, cw, "sxc")
    SYc = model.NewIntVar(ch, ch, "syc")
    XivC = model.NewIntervalVar(XC, SXc, X2C, "xint_c")
    YivC = model.NewIntervalVar(YC, SYc, Y2C, "yint_c")

    # No overlaps among rooms and with corridor
    model.AddNoOverlap2D(Xiv + [XivC], Yiv + [YivC])

    # Seed hints
    if seed is not None:
        if not isinstance(seed, LayoutResult):
            seed = LayoutResult(**seed)
        name_to_index = {s.name: i for i, s in enumerate(brief.rooms)}
        for pr in seed.rooms:
            i = name_to_index.get(pr.name)
            if i is not None:
                model.AddHint(X[i], max(0, min(pr.x, brief.building_w)))
                model.AddHint(Y[i], max(0, min(pr.y, brief.building_h)))

    # Touch corridor (private rooms)
    private = []
    for i, s in enumerate(brief.rooms):
        n = s.name.lower()
        if n.startswith("bed") or n.startswith("bath"):
            private.append(i)
    for i in private:
        touchL = model.NewBoolVar(f"ctL_{i}")
        touchR = model.NewBoolVar(f"ctR_{i}")
        touchT = model.NewBoolVar(f"ctT_{i}")
        touchB = model.NewBoolVar(f"ctB_{i}")
        wi, hi = sizes[i]
        # edge equalities
        model.Add(X[i] + wi == XC).OnlyEnforceIf(touchL)
        model.Add(XC + cw == X[i]).OnlyEnforceIf(touchR)
        model.Add(Y[i] + hi == YC).OnlyEnforceIf(touchT)
        model.Add(YC + ch == Y[i]).OnlyEnforceIf(touchB)
        model.AddBoolOr([touchL, touchR, touchT, touchB])

    # Living at corridor end if requested
    living = None
    for i, s in enumerate(brief.rooms):
        if s.name.lower().startswith("living"):
            living = i
            break
    req_end = True
    # Hard enforce end contact only if corridor spans horizontally and request present
    if living is not None:
        wi, hi = sizes[living]
        endL = model.NewBoolVar("endL")
        endR = model.NewBoolVar("endR")
        model.Add(X[living] + wi == XC).OnlyEnforceIf(endL)
        model.Add(XC + cw == X[living]).OnlyEnforceIf(endR)
        # also clamp to envelope ends
        model.Add(X[living] == 0).OnlyEnforceIf(endL)
        model.Add(X[living] + wi == brief.building_w).OnlyEnforceIf(endR)
        model.AddBoolOr([endL, endR])

    # Objective: adjacency prefs + corridor distance for private
    dist_terms: List[Any] = []
    name_to_index = {s.name: i for i, s in enumerate(brief.rooms)}
    if brief.soft and brief.soft.adjacency:
        for pref in brief.soft.adjacency:
            a = name_to_index.get(pref.a); b = name_to_index.get(pref.b)
            if a is not None and b is not None:
                cx_i = model.NewIntVar(0, brief.building_w, f"cxa_{a}")
                cy_i = model.NewIntVar(0, brief.building_h, f"cya_{a}")
                cx_j = model.NewIntVar(0, brief.building_w, f"cxb_{b}")
                cy_j = model.NewIntVar(0, brief.building_h, f"cyb_{b}")
                wi, hi = sizes[a]; wj, hj = sizes[b]
                model.Add(cx_i == X[a] + wi // 2)
                model.Add(cy_i == Y[a] + hi // 2)
                model.Add(cx_j == X[b] + wj // 2)
                model.Add(cy_j == Y[b] + hj // 2)
                dx = model.NewIntVar(0, brief.building_w, f"dx_{a}_{b}")
                dy = model.NewIntVar(0, brief.building_h, f"dy_{a}_{b}")
                model.AddAbsEquality(dx, cx_i - cx_j)
                model.AddAbsEquality(dy, cy_i - cy_j)
                dist_terms.append(dx); dist_terms.append(dy)
    # corridor distance
    hx = model.NewIntVar(cx + cw // 2, cx + cw // 2, "hcx_fix")
    hy = model.NewIntVar(cy + ch // 2, cy + ch // 2, "hcy_fix")
    for i in private:
        wi, hi = sizes[i]
        cxi = model.NewIntVar(0, brief.building_w, f"cxi_{i}")
        cyi = model.NewIntVar(0, brief.building_h, f"cyi_{i}")
        model.Add(cxi == X[i] + wi // 2)
        model.Add(cyi == Y[i] + hi // 2)
        dx = model.NewIntVar(0, brief.building_w, f"dxh_{i}")
        dy = model.NewIntVar(0, brief.building_h, f"dyh_{i}")
        model.AddAbsEquality(dx, cxi - hx)
        model.AddAbsEquality(dy, cyi - hy)
        dist_terms.append(dx); dist_terms.append(dy)

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
        x = int(solver.Value(X[i])); y = int(solver.Value(Y[i]))
        rooms.append(PlacedRoom(name=spec.name, x=x, y=y, w=wi, h=hi))
    # append corridor as room for downstream
    rooms.append(PlacedRoom(name="corridor", x=cx, y=cy, w=cw, h=ch))
    return LayoutResult(rooms=rooms, dropped=[])
