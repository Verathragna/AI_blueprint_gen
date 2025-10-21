from __future__ import annotations

from typing import List

from backend.models.scene import Building, Opening, OpeningType, Point, Space, Fixture, FixtureType


def apply_learned_placements(building: Building) -> Building:
    """Learned placement stub: propose likely windows/doors/furniture; rules will finalize later.
    Adds suggestions with meta['source']='learned'.
    """
    if not building.floors:
        return building
    bw, bh = building.width, building.height
    for floor in building.floors:
        corridor = next((s for s in floor.spaces if s.name.lower() == "corridor"), None)
        for sp in floor.spaces:
            x0, y0, w, h = sp.rect.x, sp.rect.y, sp.rect.w, sp.rect.h
            # suggest a window near room center on exterior side
            if x0 == 0:
                sp.openings.append(Opening(opening_type=OpeningType.WINDOW, at=Point(x=x0+50, y=y0 + h/2), w=800, h=1200, meta={"source":"learned"}))
            if x0 + w == bw:
                sp.openings.append(Opening(opening_type=OpeningType.WINDOW, at=Point(x=x0+w-50, y=y0 + h/2), w=800, h=1200, meta={"source":"learned"}))
            # suggest door to corridor if adjacent
            if corridor and sp is not corridor:
                cx0, cy0, cw, ch = corridor.rect.x, corridor.rect.y, corridor.rect.w, corridor.rect.h
                if cy0 + ch == y0 and max(cx0, x0) < min(cx0+cw, x0+w):
                    xmid = max(cx0, x0) + (min(cx0+cw, x0+w) - max(cx0, x0)) / 2
                    sp.openings.append(Opening(opening_type=OpeningType.DOOR, at=Point(x=xmid, y=y0), w=900, h=2100, meta={"source":"learned"}))
            # suggest a bed fixture for bedrooms
            if "bed" in sp.name.lower():
                sp.fixtures.append(Fixture(fixture_type=FixtureType.RANGE, at=Point(x=x0 + w/2, y=y0 + h/2), w=2000, h=1500, meta={"source":"learned","hint":"bed_placeholder"}))
    return building
