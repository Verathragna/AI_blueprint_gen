from __future__ import annotations

from typing import List

from backend.models.scene import Building, Floor, Space, Opening, OpeningType, Point


def apply_openings(building: Building) -> Building:
    if not building.floors:
        return building
    bw, bh = building.width, building.height
    for floor in building.floors:
        # Add a door from each space to corridor if overlap on horizontal edge
        corridor = next((s for s in floor.spaces if s.name.lower() == "corridor"), None)
        for sp in floor.spaces:
            # Windows on exterior walls
            x0, y0, w, h = sp.rect.x, sp.rect.y, sp.rect.w, sp.rect.h
            # top
            if y0 == 0:
                sp.openings.append(Opening(opening_type=OpeningType.WINDOW, at=Point(x=x0 + w/2, y=y0), w=min(900, w//2), h=1200))
            # bottom
            if y0 + h == bh:
                sp.openings.append(Opening(opening_type=OpeningType.WINDOW, at=Point(x=x0 + w/2, y=y0+h), w=min(900, w//2), h=1200))
            # left
            if x0 == 0:
                sp.openings.append(Opening(opening_type=OpeningType.WINDOW, at=Point(x=x0, y=y0 + h/2), w=900, h=1200))
            # right
            if x0 + w == bw:
                sp.openings.append(Opening(opening_type=OpeningType.WINDOW, at=Point(x=x0+w, y=y0 + h/2), w=900, h=1200))

            if corridor and sp is not corridor:
                # If corridor directly above/below and horizontal overlap, add door on shared edge
                cx0, cy0, cw, ch = corridor.rect.x, corridor.rect.y, corridor.rect.w, corridor.rect.h
                # corridor above
                if cy0 + ch == y0 and max(cx0, x0) < min(cx0+cw, x0+w):
                    xmid = max(cx0, x0) + (min(cx0+cw, x0+w) - max(cx0, x0)) / 2
                    sp.openings.append(Opening(opening_type=OpeningType.DOOR, at=Point(x=xmid, y=y0), w=900, h=2100))
                # corridor below
                if y0 + h == cy0 and max(cx0, x0) < min(cx0+cw, x0+w):
                    xmid = max(cx0, x0) + (min(cx0+cw, x0+w) - max(cx0, x0)) / 2
                    sp.openings.append(Opening(opening_type=OpeningType.DOOR, at=Point(x=xmid, y=y0+h), w=900, h=2100))
    return building
