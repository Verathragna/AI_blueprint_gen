from __future__ import annotations

from backend.models.scene import Building, Floor, Space, Fixture, FixtureType, Point


def ensure_stairs(building: Building) -> Building:
    if len(building.floors) <= 1:
        return building
    # Place a single stair core roughly at building center on each floor
    cx = building.width / 2
    cy = building.height / 2
    for i, floor in enumerate(building.floors):
        stair = Fixture(fixture_type=FixtureType.STAIRS, at=Point(x=cx, y=cy), w=1500, h=3000, meta={"rise": "175", "run": "280"})
        # Put in the first space that contains center, else attach to first space
        placed = False
        for sp in floor.spaces:
            if sp.rect.x <= cx <= sp.rect.x + sp.rect.w and sp.rect.y <= cy <= sp.rect.y + sp.rect.h:
                sp.fixtures.append(stair)
                placed = True
                break
        if not placed and floor.spaces:
            floor.spaces[0].fixtures.append(stair)
    return building
