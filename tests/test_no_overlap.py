import pytest

from backend.models.schema import Brief, RoomSpec
from backend.solver.solver import LayoutSolver
from backend.solver.grid import solve_on_grid


def get_attr(room, key):
    if isinstance(room, dict):
        return room[key]
    return getattr(room, key)


def intervals_overlap(a0, a1, b0, b1):
    return min(a1, b1) - max(a0, b0) > 0


def has_overlap(rooms):
    for i in range(len(rooms)):
        a = rooms[i]
        for j in range(i + 1, len(rooms)):
            b = rooms[j]
            ax, ay, aw, ah = (get_attr(a, "x"), get_attr(a, "y"), get_attr(a, "w"), get_attr(a, "h"))
            bx, by, bw, bh = (get_attr(b, "x"), get_attr(b, "y"), get_attr(b, "w"), get_attr(b, "h"))
            if intervals_overlap(ax, ax + aw, bx, bx + bw) and intervals_overlap(ay, ay + ah, by, by + bh):
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


def touches_edge(a, b):
    ax, ay, aw, ah = (get_attr(a, "x"), get_attr(a, "y"), get_attr(a, "w"), get_attr(a, "h"))
    bx, by, bw, bh = (get_attr(b, "x"), get_attr(b, "y"), get_attr(b, "w"), get_attr(b, "h"))
    overlap_x = min(ax + aw, bx + bw) - max(ax, bx)
    overlap_y = min(ay + ah, by + bh) - max(ay, by)
    horizontal_touch = overlap_x > 0 and (ay + ah == by or by + bh == ay)
    vertical_touch = overlap_y > 0 and (ax + aw == bx or bx + bw == ax)
    return horizontal_touch or vertical_touch


def test_kitchen_adjacent_to_living():
    brief = Brief(
        building_w=1200,
        building_h=900,
        rooms=[
            RoomSpec(name="living", min_w=320, min_h=300, target_area=120000),
            RoomSpec(name="kitchen", min_w=260, min_h=250, target_area=80000),
            RoomSpec(name="bed1", min_w=300, min_h=300, target_area=90000),
            RoomSpec(name="bed2", min_w=300, min_h=300, target_area=90000),
            RoomSpec(name="bath", min_w=150, min_h=200, target_area=30000),
        ],
        hard={"min_corridor_width": 150},
        soft={"adjacency": [{"a": "kitchen", "b": "living"}]},
    )
    solver = LayoutSolver()
    out = solver.solve(brief)
    rooms = out["rooms"] if isinstance(out, dict) else out.rooms
    mapping = {get_attr(r, "name"): r for r in rooms}
    assert "living" in mapping and "kitchen" in mapping
    assert touches_edge(mapping["living"], mapping["kitchen"])


def test_grid_solver_handles_two_bed_corridor():
    brief = Brief(
        building_w=1200,
        building_h=800,
        rooms=[
            RoomSpec(name="living", min_w=300, min_h=300, target_area=120000),
            RoomSpec(name="kitchen", min_w=250, min_h=250, target_area=75000),
            RoomSpec(name="bed1", min_w=300, min_h=300, target_area=90000),
            RoomSpec(name="bed2", min_w=300, min_h=300, target_area=90000),
            RoomSpec(name="bath", min_w=150, min_h=200, target_area=30000),
        ],
        hard={"min_corridor_width": 100},
        soft={"adjacency": [{"a": "kitchen", "b": "living"}]},
    )
    layout = solve_on_grid(brief)
    assert layout.dropped == []
    assert not has_overlap(layout.rooms)
