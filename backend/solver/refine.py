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


def ensure_connectivity(layout: LayoutResult | dict, brief: Brief | dict, max_passes: int = 3) -> LayoutResult:
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    def bbox(r):
        return (r.x, r.y, r.x + r.w, r.y + r.h)

    def y_overlap(a, b):
        ax0, ay0, ax1, ay1 = bbox(a)
        bx0, by0, bx1, by1 = bbox(b)
        return not (ay1 <= by0 or by1 <= ay0)

    def x_overlap(a, b):
        ax0, ay0, ax1, ay1 = bbox(a)
        bx0, by0, bx1, by1 = bbox(b)
        return not (ax1 <= bx0 or bx1 <= ax0)

    def center(r):
        return (r.x + r.w / 2, r.y + r.h / 2)

    for _ in range(max_passes):
        def touches(a, b):
            ax0, ay0, ax1, ay1 = bbox(a)
            bx0, by0, bx1, by1 = bbox(b)
            return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)
        isolated = []
        for r in layout.rooms:
            if not any(touches(r, o) for o in layout.rooms if o is not r):
                isolated.append(r)
        if not isolated:
            break
        for r in isolated:
            # find nearest neighbor by Manhattan distance between centers
            cx, cy = center(r)
            others = [o for o in layout.rooms if o is not r]
            if not others:
                continue
            nearest = min(others, key=lambda o: abs(center(o)[0] - cx) + abs(center(o)[1] - cy))
            # try to snap horizontally if y-overlap, else vertically
            if y_overlap(r, nearest):
                # try place to the right of nearest
                new_x = nearest.x + nearest.w
                if new_x + r.w <= brief.building_w:
                    r.x = new_x
                else:
                    # place to the left
                    r.x = max(0, nearest.x - r.w)
                # align vertically within bounds
                r.y = min(max(r.y, 0), max(0, brief.building_h - r.h))
            else:
                # vertical snap below or above
                new_y = nearest.y + nearest.h
                if new_y + r.h <= brief.building_h:
                    r.y = new_y
                else:
                    r.y = max(0, nearest.y - r.h)
                r.x = min(max(r.x, 0), max(0, brief.building_w - r.w))
    return layout


def attract_to_hub(layout: LayoutResult | dict, brief: Brief | dict, step: int = 20, iters: int = 20) -> LayoutResult:
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    # find hub in current layout (corridor else living*)
    def find_hub():
        for r in layout.rooms:
            if r.name.lower().startswith("corridor"):
                return r
        for r in layout.rooms:
            if r.name.lower().startswith("living"):
                return r
        return layout.rooms[0] if layout.rooms else None
    hub = find_hub()
    if not hub:
        return layout
    def touches(a, b):
        return not (a.x + a.w < b.x or b.x + b.w < a.x or a.y + a.h < b.y or b.y + b.h < a.y)
    def move_toward(a, b):
        # move rectangle a towards b by step along shortest axis until boundary
        if a.x + a.w <= b.x:  # a is left of b
            a.x = min(a.x + step, b.x - a.w)
        elif b.x + b.w <= a.x:  # a is right of b
            a.x = max(a.x - step, 0)
        if a.y + a.h <= b.y:  # a above b
            a.y = min(a.y + step, b.y - a.h)
        elif b.y + b.h <= a.y:  # a below b
            a.y = max(a.y - step, 0)
        # clamp in envelope
        a.x = min(max(a.x, 0), max(0, brief.building_w - a.w))
        a.y = min(max(a.y, 0), max(0, brief.building_h - a.h))
    for _ in range(iters):
        moved = False
        for r in layout.rooms:
            if r is hub:
                continue
            if not touches(r, hub):
                move_toward(r, hub)
                moved = True
        if not moved:
            break
    return layout


def attract_to_corridor(layout: LayoutResult | dict, brief: Brief | dict, step: int = 20, iters: int = 20) -> LayoutResult:
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    corridor = next((r for r in layout.rooms if r.name.lower().startswith("corridor")), None)
    if corridor is None:
        return layout
    def is_private(r):
        n = r.name.lower()
        return n.startswith("bed") or n.startswith("bath")
    def touches(a,b):
        return not (a.x + a.w < b.x or b.x + b.w < a.x or a.y + a.h < b.y or b.y + b.h < a.y)
    for _ in range(iters):
        moved=False
        for r in layout.rooms:
            if not is_private(r):
                continue
            if not touches(r, corridor):
                # move vertically toward corridor if above/below else horizontally
                if r.y + r.h <= corridor.y:
                    r.y = min(r.y + step, corridor.y - r.h)
                elif corridor.y + corridor.h <= r.y:
                    r.y = max(r.y - step, 0)
                else:
                    if r.x + r.w <= corridor.x:
                        r.x = min(r.x + step, corridor.x - r.w)
                    elif corridor.x + corridor.w <= r.x:
                        r.x = max(r.x - step, 0)
                moved=True
        if not moved:
            break
    return layout


def ensure_corridor_overlap(layout: LayoutResult | dict, brief: Brief | dict) -> LayoutResult:
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    corridor = next((r for r in layout.rooms if r.name.lower().startswith("corridor")), None)
    if corridor is None:
        return layout
    min_ov = (brief.connectivity.min_overlap if brief.connectivity and brief.connectivity.min_overlap else 50)
    def overlap_len(a0,a1,b0,b1):
        return max(0, min(a1,b1) - max(a0,b0))
    for r in layout.rooms:
        if r is corridor:
            continue
        # if sharing vertical edge
        if r.x + r.w == corridor.x or corridor.x + corridor.w == r.x:
            ov = overlap_len(r.y, r.y + r.h, corridor.y, corridor.y + corridor.h)
            if 0 < ov < min_ov:
                # slide to increase overlap
                want = min_ov - ov
                if r.y > corridor.y:
                    r.y = max(0, r.y - want)
                else:
                    r.y = min(r.y + want, max(0, brief.building_h - r.h))
        # if sharing horizontal edge
        if r.y + r.h == corridor.y or corridor.y + corridor.h == r.y:
            ov = overlap_len(r.x, r.x + r.w, corridor.x, corridor.x + corridor.w)
            if 0 < ov < min_ov:
                want = min_ov - ov
                if r.x > corridor.x:
                    r.x = max(0, r.x - want)
                else:
                    r.x = min(r.x + want, max(0, brief.building_w - r.w))
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
