from __future__ import annotations

from typing import List

from backend.models.schema import Brief, LayoutResult, PlacedRoom


def propose_topologies(brief: Brief | dict, k: int = 2) -> List[LayoutResult]:
    if not isinstance(brief, Brief):
        brief = Brief(**brief)

    # Strategy: place living+kitchen adjacent on first row; bedrooms in second row; bath near bedrooms
    names = [r.name.lower() for r in brief.rooms]
    has_living = any(n.startswith("living") for n in names)
    has_kitchen = any(n.startswith("kitchen") for n in names)
    beds = [r for r in brief.rooms if r.name.lower().startswith("bed")]
    baths = [r for r in brief.rooms if r.name.lower().startswith("bath")]

    variants: List[LayoutResult] = []
    for i in range(k):
        x, y = 0, 0
        row_h = 0
        rooms: List[PlacedRoom] = []
        # first row: living + kitchen if present
        if has_living:
            rooms.append(PlacedRoom(name="living", x=x, y=y, w=min(brief.building_w//3, 500), h=300))
            x += rooms[-1].w
            row_h = max(row_h, rooms[-1].h)
        if has_kitchen:
            rooms.append(PlacedRoom(name="kitchen", x=x, y=y, w=min(brief.building_w//4, 300), h=300))
            x += rooms[-1].w
            row_h = max(row_h, rooms[-1].h)
        # second row: bedrooms
        x = 0
        y += row_h
        row_h = 0
        for b in beds:
            w = min(brief.building_w//3, 300)
            h = 300
            if x + w > brief.building_w:
                x = 0
                y += row_h
                row_h = 0
            rooms.append(PlacedRoom(name=b.name, x=x, y=y, w=w, h=h))
            x += w
            row_h = max(row_h, h)
        # bathrooms next to bedrooms area
        for idx, ba in enumerate(baths):
            w, h = 200, 200
            bx = min(brief.building_w - w, rooms[-1].x + (idx+1)*10)
            by = rooms[-1].y
            rooms.append(PlacedRoom(name=ba.name, x=bx, y=by, w=w, h=h))
        variants.append(LayoutResult(rooms=rooms, dropped=[]))
    return variants
