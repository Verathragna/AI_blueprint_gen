from __future__ import annotations

from typing import Dict, Any, List, Tuple

from backend.models.schema import Brief, LayoutResult, PlacedRoom, RoomSpec


def _find_hub_name(brief: Brief) -> str | None:
    # corridor if will exist, else first living*
    for s in brief.rooms:
        if s.name.lower().startswith("corridor"):
            return s.name
    for s in brief.rooms:
        if s.name.lower().startswith("living"):
            return s.name
    return brief.rooms[0].name if brief.rooms else None


def pack_with_hub(brief: Brief | Dict[str, Any]) -> LayoutResult:
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    def size_for(s: RoomSpec) -> Tuple[int, int]:
        import math
        if s.target_area:
            w0 = max(s.min_w, int(math.sqrt(s.target_area)))
            h0 = max(s.min_h, int(math.ceil(s.target_area / w0)))
            return min(w0, brief.building_w), min(h0, brief.building_h)
        return min(s.min_w, brief.building_w), min(s.min_h, brief.building_h)

    hub_name = _find_hub_name(brief)
    specs_by_name = {s.name: s for s in brief.rooms}
    rooms: List[PlacedRoom] = []
    dropped: List[str] = []

    if not hub_name:
        return LayoutResult(rooms=[], dropped=[])

    # Place hub at top-left
    hw, hh = size_for(specs_by_name[hub_name])
    rooms.append(PlacedRoom(name=hub_name, x=0, y=0, w=hw, h=hh))

    # Pack others touching the hub: first along the right edge, then along bottom
    y_cursor = 0
    for s in brief.rooms:
        if s.name == hub_name:
            continue
        w, h = size_for(s)
        # try right edge stack
        if y_cursor + h <= hh and hw + w <= brief.building_w:
            rooms.append(PlacedRoom(name=s.name, x=hw, y=y_cursor, w=w, h=h))
            y_cursor += h
        else:
            # place along bottom edge, stacking in x
            # compute current max x on bottom row
            bottoms = [r for r in rooms if r.y == hh]
            x_next = sum(r.w for r in bottoms) if bottoms else 0
            if x_next + w <= brief.building_w:
                rooms.append(PlacedRoom(name=s.name, x=x_next, y=hh, w=w, h=h))
            else:
                dropped.append(s.name)
    return LayoutResult(rooms=rooms, dropped=dropped)


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
