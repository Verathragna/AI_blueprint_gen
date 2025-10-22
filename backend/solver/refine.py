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


def resolve_overlaps(layout: LayoutResult | dict, brief: Brief | dict, passes: int = 20) -> LayoutResult:
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    def overlap(a, b):
        ox = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
        oy = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
        return ox, oy

    def is_corridor(r):
        return r.name.lower().startswith("corridor")

    def clear_pair(fixed, mover):
        # compute minimal moves to place mover left/right/above/below fixed (exactly tangent)
        candidates = []
        # push left of fixed (mover.x2 = fixed.x)
        new_x = fixed.x - mover.w
        if new_x >= 0:
            candidates.append((abs(mover.x - new_x), new_x, mover.y))
        # push right of fixed (mover.x = fixed.x2)
        new_x = fixed.x + fixed.w
        if new_x + mover.w <= brief.building_w:
            candidates.append((abs(new_x - mover.x), new_x, mover.y))
        # push above fixed (mover.y2 = fixed.y)
        new_y = fixed.y - mover.h
        if new_y >= 0:
            candidates.append((abs(mover.y - new_y), mover.x, new_y))
        # push below fixed (mover.y = fixed.y2)
        new_y = fixed.y + fixed.h
        if new_y + mover.h <= brief.building_h:
            candidates.append((abs(new_y - mover.y), mover.x, new_y))
        if candidates:
            # choose the smallest displacement first, then prefer axis with more penetration relief
            dist, nx, ny = min(candidates, key=lambda t: t[0])
            mover.x = min(max(nx, 0), max(0, brief.building_w - mover.w))
            mover.y = min(max(ny, 0), max(0, brief.building_h - mover.h))
            return True
        return False

    def contains(inner, outer):
        return (
            inner.x >= outer.x and inner.y >= outer.y and
            inner.x + inner.w <= outer.x + outer.w and
            inner.y + inner.h <= outer.y + outer.h
        )

    def push_out(inner, outer):
        # Move contained rect to nearest outside side of outer
        d_left = abs(inner.x - (outer.x - inner.w))
        d_right = abs((outer.x + outer.w) - inner.x)
        d_up = abs(inner.y - (outer.y - inner.h))
        d_down = abs((outer.y + outer.h) - inner.y)
        choices = [
            (d_left, outer.x - inner.w, inner.y),
            (d_right, outer.x + outer.w, inner.y),
            (d_up, inner.x, outer.y - inner.h),
            (d_down, inner.x, outer.y + outer.h),
        ]
        dist, nx, ny = min(choices, key=lambda t: t[0])
        inner.x = min(max(nx, 0), max(0, brief.building_w - inner.w))
        inner.y = min(max(ny, 0), max(0, brief.building_h - inner.h))
        return True

    for _ in range(passes):
        moved = False
        for i in range(len(layout.rooms)):
            for j in range(i + 1, len(layout.rooms)):
                a = layout.rooms[i]; b = layout.rooms[j]
                # Skip corridor pair
                if is_corridor(a) and is_corridor(b):
                    continue
                ox, oy = overlap(a, b)
                if ox > 0 and oy > 0:
                    # Handle strict containment first (move the contained one out)
                    if contains(a, b) and not is_corridor(a):
                        changed = push_out(a, b)
                    elif contains(b, a) and not is_corridor(b):
                        changed = push_out(b, a)
                    else:
                        # Prefer to move the non-corridor room; otherwise move b
                        move_b = not is_corridor(b)
                        fixed, mover = (a, b) if move_b else (b, a)
                        # Try to clear by minimal displacement while staying in envelope
                        changed = clear_pair(fixed, mover)
                        if not changed:
                            # If mover couldn't move (bounded), try moving the other
                            changed = clear_pair(mover, fixed)
                    moved = moved or changed
        if not moved:
            break
    return layout


def keep_corridor_clear(layout: LayoutResult | dict, brief: Brief | dict) -> LayoutResult:
    """Force all rooms out of the corridor band (no intersections).

    Deterministic cleanup used after heuristic moves; never moves the corridor, only others.
    """
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    corridor = next((r for r in layout.rooms if r.name.lower().startswith("corridor")), None)
    if corridor is None:
        return layout

    def intersects(a, b):
        return not (a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y)

    cy_mid = corridor.y + corridor.h // 2
    for r in layout.rooms:
        if r is corridor:
            continue
        if intersects(r, corridor):
            # choose above or below based on center
            rc_mid = r.y + r.h // 2
            if rc_mid <= cy_mid:
                # move above
                r.y = max(0, corridor.y - r.h)
            else:
                # move below
                r.y = min(corridor.y + corridor.h, max(0, brief.building_h - r.h))
            # clamp horizontally too (keep as-is)
            r.x = min(max(r.x, 0), max(0, brief.building_w - r.w))
    return layout


def has_overlap(layout: LayoutResult | dict) -> bool:
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    n = len(layout.rooms)
    for i in range(n):
        a = layout.rooms[i]
        for j in range(i + 1, n):
            b = layout.rooms[j]
            ox = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
            oy = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
            if ox > 0 and oy > 0:
                return True
    return False


def legalize_no_overlap(layout: LayoutResult | dict, brief: Brief | dict) -> LayoutResult:
    """Re-pack rooms (keeping sizes) into rows to guarantee no overlaps.
    Preserves corridor position if present; other rooms are packed above/below.
    """
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    rooms = [r for r in layout.rooms]
    corridor = next((r for r in rooms if r.name.lower().startswith("corridor")), None)

    def pack_rows(candidates, x0, y0, W, H):
        x = x0; y = y0; row_h = 0
        placed = []
        for r in candidates:
            if r.w > W or r.h > H:
                continue  # cannot fit region; skip, will try elsewhere
            if x + r.w > x0 + W:
                x = x0
                y += row_h
                row_h = 0
            if y + r.h > y0 + H:
                continue  # no more space in this region
            r.x, r.y = x, y
            x += r.w
            row_h = max(row_h, r.h)
            placed.append(r)
        return placed

    if corridor:
        others = [r for r in rooms if r is not corridor]
        # Try pack above then remaining below
        # sort largest first to reduce fragmentation
        others.sort(key=lambda r: r.w * r.h, reverse=True)
        top_space = pack_rows(others, 0, 0, brief.building_w, max(0, corridor.y))
        placed_ids = set(id(r) for r in top_space)
        rest = [r for r in others if id(r) not in placed_ids]
        bottom_space = pack_rows(rest, 0, corridor.y + corridor.h, brief.building_w, max(0, brief.building_h - (corridor.y + corridor.h)))
        # Update layout list order is irrelevant
        layout.rooms = [corridor] + top_space + bottom_space
    else:
        # Simple whole-envelope pack
        rs = [r for r in rooms]
        rs.sort(key=lambda r: r.w * r.h, reverse=True)
        packed = pack_rows(rs, 0, 0, brief.building_w, brief.building_h)
        layout.rooms = packed

    return layout


# Presentation / geometry polishing

def snap_and_align(layout: LayoutResult | dict, brief: Brief | dict, grid: int = 10, margin: int = 20) -> LayoutResult:
    """Snap all rectangles to grid, enforce outer margin, and align rows/columns.
    Does not change corridor size/position beyond snapping.
    """
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    def snap(v: int) -> int:
        r = int(round(v / grid) * grid)
        return max(0, r)

    # snap
    for r in layout.rooms:
        r.x = snap(r.x); r.y = snap(r.y); r.w = max(grid, snap(r.w)); r.h = max(grid, snap(r.h))
    # outer margin
    for r in layout.rooms:
        r.x = min(max(r.x, margin), max(0, brief.building_w - margin - r.w))
        r.y = min(max(r.y, margin), max(0, brief.building_h - margin - r.h))
    # align rows (by top y) and columns (by left x)
    ys = {}
    xs = {}
    for r in layout.rooms:
        ys.setdefault(r.y, []).append(r)
        xs.setdefault(r.x, []).append(r)
    # merge keys within grid tolerance
    def merge_keys(keys):
        keys = sorted(keys)
        bands = []
        for k in keys:
            if not bands or abs(k - bands[-1][-1]) > grid:
                bands.append([k])
            else:
                bands[-1].append(k)
        reps = [int(round(sum(b) / len(b))) for b in bands]
        return reps, bands
    # rows
    reps_y, bands_y = merge_keys(list(ys.keys()))
    for rep, band in zip(reps_y, bands_y):
        for k in band:
            for r in ys[k]:
                r.y = rep
    # columns
    reps_x, bands_x = merge_keys(list(xs.keys()))
    for rep, band in zip(reps_x, bands_x):
        for k in band:
            for r in xs[k]:
                r.x = rep

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
