import pytest

from backend.models.schema import Brief, RoomSpec
from backend.solver.solver import LayoutSolver


def intervals_overlap(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0) > 0


def has_overlap(rooms):
    for i in range(len(rooms)):
        a = rooms[i]
        for j in range(i + 1, len(rooms)):
            b = rooms[j]
            if intervals_overlap(a.x, a.x + a.w, b.x, b.x + b.w) and intervals_overlap(a.y, a.y + a.h, b.y, b.y + b.h):
                return True
    return False


def test_no_overlaps_simple():
    brief = Brief(
        building_w=2000,
        building_h=1200,
        rooms=[
            RoomSpec(name="living", min_w=600, min_h=400),
            RoomSpec(name="kitchen", min_w=400, min_h=300),
            RoomSpec(name="bed1", min_w=300, min_h=300),
            RoomSpec(name="bed2", min_w=300, min_h=300),
            RoomSpec(name="bath", min_w=200, min_h=200),
        ],
    )
    solver = LayoutSolver()
    out = solver.solve(brief)
    rooms = out["rooms"] if isinstance(out, dict) else out.rooms
    assert not has_overlap(rooms)
