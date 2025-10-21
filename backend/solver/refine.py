from __future__ import annotations

from typing import Dict

from backend.models.schema import Brief, LayoutResult


def refine_layout(layout: LayoutResult | dict, brief: Brief | dict, iterations: int = 2) -> LayoutResult:
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    # Nudge room sizes toward target area and aspect ratio target
    target_ratio = (brief.soft.aspect_ratio_target if brief.soft else 1.5)
    tol = (brief.soft.aspect_ratio_tolerance if brief.soft else 0.5)

    for _ in range(iterations):
        for r in layout.rooms:
            # Nudge toward target area
            spec = next((s for s in brief.rooms if s.name == r.name and s.target_area), None)
            if spec and spec.target_area:
                current = r.w * r.h
                if current < spec.target_area:
                    r.w = min(r.w + 10, brief.building_w)
                    r.h = min(r.h + 10, brief.building_h)
                elif current > spec.target_area:
                    r.w = max(r.w - 10, 1)
                    r.h = max(r.h - 10, 1)
            # Nudge aspect ratio towards target by adjusting the longer side
            w, h = r.w, r.h
            if min(w, h) <= 0:
                continue
            ratio = max(w, h) / min(w, h)
            if ratio > target_ratio + tol:
                # too skinny: reduce long side if possible
                if w > h and r.w > 1:
                    r.w = max(r.w - 10, 1)
                elif h > w and r.h > 1:
                    r.h = max(r.h - 10, 1)
            elif ratio < max(1.0, target_ratio - tol):
                # too fat: increase long side up to envelope
                if w >= h:
                    r.w = min(r.w + 10, brief.building_w)
                else:
                    r.h = min(r.h + 10, brief.building_h)
        # Keep within envelope (simple clamp)
        for r in layout.rooms:
            if r.x + r.w > brief.building_w:
                r.w = max(1, brief.building_w - r.x)
            if r.y + r.h > brief.building_h:
                r.h = max(1, brief.building_h - r.y)
    return layout


def add_corridor(layout: LayoutResult | dict, brief: Brief | dict) -> LayoutResult:
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    min_cw = (brief.hard.min_corridor_width if (brief.hard and brief.hard.min_corridor_width) else None)
    if not min_cw or not layout.rooms:
        return layout

    # Insert a horizontal corridor at top and push rooms down if space allows
    if min_cw < brief.building_h:
        for r in layout.rooms:
            r.y = r.y + min_cw
            if r.y + r.h > brief.building_h:
                # cannot fit after corridor; mark drop
                layout.dropped.append(r.name)
        # Remove dropped rooms
        layout.rooms = [r for r in layout.rooms if r.name not in set(layout.dropped)]
        # Add corridor room across full width
        layout.rooms.insert(0, type(layout.rooms[0])(name="corridor", x=0, y=0, w=brief.building_w, h=min_cw))
    return layout
