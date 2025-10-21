from typing import Dict, Any, List
from backend.models.schema import Brief, LayoutResult, PlacedRoom
from backend.models.scene import from_brief_and_layout
from backend.rules.dsl import evaluate_rules, RuleViolation
from backend.rules.loader import load_rules


class RulesEngine:
    """Validate hard constraints and declarative scene rules."""

    def early_prune(self, brief: Dict[str, Any] | Brief) -> Brief:
        """Adjust incoming brief to meet absolute minimums (e.g., corridor width, min dims)."""
        if not isinstance(brief, Brief):
            brief = Brief(**brief)
        # Ensure room min dims are at least 1 unit and sensible
        for r in brief.rooms:
            r.min_w = max(1, r.min_w)
            r.min_h = max(1, r.min_h)
        return brief

    def check(self, layout: Dict[str, Any], brief: Dict[str, Any] | Brief | None = None, rule_paths: List[str] | None = None) -> Dict[str, Any]:
        # Accept both dict and LayoutResult
        if isinstance(layout, LayoutResult):
            rooms = layout.rooms
            dropped = layout.dropped
            layout_obj = layout
        else:
            data = LayoutResult(**layout)
            rooms = data.rooms
            dropped = data.dropped
            layout_obj = data

        violations: List[str] = []

        for r in rooms:
            if r.w <= 0 or r.h <= 0:
                violations.append(f"{r.name}: non-positive dimensions {r.w}x{r.h}")

        for name in dropped:
            violations.append(f"{name}: could not be placed within envelope")

        if brief is not None:
            if not isinstance(brief, Brief):
                brief = Brief(**brief)
            area_bounds = {c.name: (c.min_area, c.max_area) for c in (brief.hard.room_areas if brief.hard else [])}
            for r in rooms:
                if r.name in area_bounds:
                    mn, mx = area_bounds[r.name]
                    area = r.w * r.h
                    if mn is not None and area < mn:
                        violations.append(f"{r.name}: area {area} below min {mn}")
                    if mx is not None and area > mx:
                        violations.append(f"{r.name}: area {area} above max {mx}")
            # Scene-level declarative rules
            building = from_brief_and_layout(brief, layout_obj)
            rules = load_rules(rule_paths)
            scene_violations: List[RuleViolation] = evaluate_rules(rules, building)
            for v in scene_violations:
                violations.append(f"[{v.severity}] {v.id}: {v.title} @ {v.where} — {v.suggestion}")

        return {"compliant": len(violations) == 0, "violations": violations}
