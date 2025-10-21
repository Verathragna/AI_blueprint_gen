from __future__ import annotations

from typing import Dict, Any, List, Tuple

from backend.models.schema import Brief, LayoutResult, PlacedRoom, RoomSpec


def pack_next_fit(brief: Brief | Dict[str, Any]) -> LayoutResult:
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    def size_for(s: RoomSpec) -> Tuple[int, int]:
        import math

        if s.target_area:
            w0 = max(s.min_w, int(math.sqrt(s.target_area)))
            h0 = max(s.min_h, int(math.ceil(s.target_area / w0)))
            return min(w0, brief.building_w), min(h0, brief.building_h)
        return min(s.min_w, brief.building_w), min(s.min_h, brief.building_h)

    # Sort by descending height to reduce fragmentation
    specs = sorted(brief.rooms, key=lambda r: size_for(r)[1], reverse=True)

    x, y, row_h = 0, 0, 0
    rooms: List[PlacedRoom] = []
    dropped: List[str] = []

    for s in specs:
        w, h = size_for(s)
        if x + w > brief.building_w:
            x = 0
            y += row_h
            row_h = 0
        if y + h > brief.building_h:
            dropped.append(s.name)
            continue
        rooms.append(PlacedRoom(name=s.name, x=x, y=y, w=w, h=h))
        x += w
        row_h = max(row_h, h)

    # Try to pull adjacency prefs closer by swapping positions locally
    name_to_idx = {r.name: i for i, r in enumerate(rooms)}
    prefs = list(brief.adjacency_preferences)
    if brief.soft and brief.soft.adjacency:
        prefs += [(p.a, p.b) for p in brief.soft.adjacency]
    for (a, b) in prefs:
        ia = name_to_idx.get(a)
        ib = name_to_idx.get(b)
        if ia is None or ib is None:
            continue
        ra, rb = rooms[ia], rooms[ib]
        if abs((ra.x + ra.w // 2) - (rb.x + rb.w // 2)) + abs((ra.y + ra.h // 2) - (rb.y + rb.h // 2)) > (brief.building_w // 2):
            # swap to bring closer
            ra.x, rb.x = rb.x, ra.x
            ra.y, rb.y = rb.y, ra.y
    return LayoutResult(rooms=rooms, dropped=dropped)
