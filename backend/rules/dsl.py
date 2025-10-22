from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.models.scene import Building, Space


@dataclass
class RuleViolation:
    id: str
    title: str
    severity: str  # info|warn|error
    where: str
    suggestion: str


def _is_bedroom(sp: Space) -> bool:
    return sp.name.lower().startswith("bed")


def _is_habitable(sp: Space) -> bool:
    n = sp.name.lower()
    return n.startswith("bed") or n.startswith("living") or n.startswith("kitchen")


def evaluate_rule(rule: Dict[str, Any], building: Building) -> List[RuleViolation]:
    out: List[RuleViolation] = []
    r_id = rule.get("id", "rule")
    title = rule.get("title", r_id)
    severity = rule.get("severity", "warn")
    kind = rule.get("kind")

    # Corridor width check
    if kind == "min_corridor_width":
        min_w = float(rule.get("min", 900))
        for f in building.floors:
            for sp in f.spaces:
                if sp.name.lower() == "corridor":
                    cw = min(sp.rect.w, sp.rect.h)
                    if cw < min_w:
                        out.append(
                            RuleViolation(
                                id=r_id,
                                title=title,
                                severity=severity,
                                where=f"floor@{f.elevation}:corridor",
                                suggestion=f"Increase corridor width to at least {int(min_w)} mm (current {int(cw)}).",
                            )
                        )
    # Bedroom egress window (at least one window opening)
    elif kind == "bedroom_egress_window":
        for f in building.floors:
            for sp in f.spaces:
                if _is_bedroom(sp):
                    wins = [op for op in sp.openings if op.opening_type.name == "WINDOW"]
                    if len(wins) == 0:
                        out.append(
                            RuleViolation(
                                id=r_id,
                                title=title,
                                severity=severity,
                                where=f"room:{sp.name}",
                                suggestion="Add at least one operable window meeting egress dimensions.",
                            )
                        )
    # Habitable daylight (at least one window)
    elif kind == "habitable_daylight_window":
        for f in building.floors:
            for sp in f.spaces:
                if _is_habitable(sp):
                    wins = [op for op in sp.openings if op.opening_type.name == "WINDOW"]
                    if len(wins) == 0:
                        out.append(
                            RuleViolation(
                                id=r_id,
                                title=title,
                                severity=severity,
                                where=f"room:{sp.name}",
                                suggestion="Provide at least one window for daylight/ventilation in habitable room.",
                            )
                        )
    # Min room area
    elif kind == "min_room_area":
        min_area = float(rule.get("min", 70000))
        selector = rule.get("selector", "bedroom")
        for f in building.floors:
            for sp in f.spaces:
                cond = _is_bedroom(sp) if selector == "bedroom" else True
                if cond:
                    area = sp.rect.w * sp.rect.h
                    if area < min_area:
                        out.append(
                            RuleViolation(
                                id=r_id,
                                title=title,
                                severity=severity,
                                where=f"room:{sp.name}",
                                suggestion=f"Increase area to at least {int(min_area)} mm^2 (current {int(area)}).",
                            )
                        )
    return out


def evaluate_rules(rules: List[Dict[str, Any]], building: Building) -> List[RuleViolation]:
    violations: List[RuleViolation] = []
    for r in rules:
        violations.extend(evaluate_rule(r, building))
    # Connectivity rule (implicit): if specified via kind
    if any(r.get("kind") == "connected_rooms" for r in rules):
        # Build adjacency by shared edges/overlap
        from backend.models.graphs import build_room_adjacency
        for f in building.floors:
            g = build_room_adjacency(f)
            for sp in f.spaces:
                if g.degree(sp.id) == 0:
                    violations.append(
                        RuleViolation(
                            id="graph.connected",
                            title="Room is isolated (no adjacency)",
                            severity="warn",
                            where=f"room:{sp.name}",
                            suggestion="Snap or move room to share an edge with another room or corridor.",
                        )
                    )
    # Corridor-private rules
    if any(r.get("kind") == "private_rooms_to_corridor" for r in rules) or any(r.get("kind") == "corridor_touches_living" for r in rules):
        corridor = None
        for f in building.floors:
            for sp in f.spaces:
                if sp.name.lower().startswith("corridor"):
                    corridor = sp
                    break
            if corridor:
                break
        if corridor:
            min_ov = 50
            for r in rules:
                if r.get("kind") in ("private_rooms_to_corridor", "corridor_touches_living") and r.get("min_overlap"):
                    try:
                        min_ov = int(r.get("min_overlap"))
                    except Exception:
                        pass
            def overlap_len(a0,a1,b0,b1):
                return max(0, min(a1,b1) - max(a0,b0))
            # private rooms must share corridor edge with overlap
            for f in building.floors:
                for sp in f.spaces:
                    n = sp.name.lower()
                    if n.startswith("bed") or n.startswith("bath"):
                        v1 = (sp.rect.x + sp.rect.w == corridor.rect.x and overlap_len(sp.rect.y, sp.rect.y+sp.rect.h, corridor.rect.y, corridor.rect.y+corridor.rect.h) >= min_ov)
                        v2 = (corridor.rect.x + corridor.rect.w == sp.rect.x and overlap_len(sp.rect.y, sp.rect.y+sp.rect.h, corridor.rect.y, corridor.rect.y+corridor.rect.h) >= min_ov)
                        v3 = (sp.rect.y + sp.rect.h == corridor.rect.y and overlap_len(sp.rect.x, sp.rect.x+sp.rect.w, corridor.rect.x, corridor.rect.x+corridor.rect.w) >= min_ov)
                        v4 = (corridor.rect.y + corridor.rect.h == sp.rect.y and overlap_len(sp.rect.x, sp.rect.x+sp.rect.w, corridor.rect.x, corridor.rect.x+corridor.rect.w) >= min_ov)
                        if not (v1 or v2 or v3 or v4):
                            violations.append(RuleViolation(
                                id="corridor.private.touch",
                                title="Private room not connected to corridor",
                                severity="error",
                                where=f"room:{sp.name}",
                                suggestion="Move room to share an edge with the corridor.",
                            ))
            # living should touch an end of corridor
            for f in building.floors:
                for sp in f.spaces:
                    if sp.name.lower().startswith("living"):
                        left_end = (sp.rect.x + sp.rect.w == corridor.rect.x and overlap_len(sp.rect.y, sp.rect.y+sp.rect.h, corridor.rect.y, corridor.rect.y+corridor.rect.h) >= min_ov and sp.rect.x==0)
                        right_end = (corridor.rect.x + corridor.rect.w == sp.rect.x and overlap_len(sp.rect.y, sp.rect.y+sp.rect.h, corridor.rect.y, corridor.rect.y+corridor.rect.h) >= min_ov and corridor.rect.x+corridor.rect.w==building.width)
                        top_end = (sp.rect.y + sp.rect.h == corridor.rect.y and overlap_len(sp.rect.x, sp.rect.x+sp.rect.w, corridor.rect.x, corridor.rect.x+corridor.rect.w) >= min_ov and sp.rect.y==0)
                        bottom_end = (corridor.rect.y + corridor.rect.h == sp.rect.y and overlap_len(sp.rect.x, sp.rect.x+sp.rect.w, corridor.rect.x, corridor.rect.x+corridor.rect.w) >= min_ov and corridor.rect.y+corridor.rect.h==building.height)
                        if not (left_end or right_end or top_end or bottom_end):
                            violations.append(RuleViolation(
                                id="corridor.living.end",
                                title="Living should connect to corridor at an end",
                                severity="warn",
                                where=f"room:{sp.name}",
                                suggestion="Align living to one corridor end.",
                            ))
    return violations
