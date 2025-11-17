from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

try:
    from ortools.sat.python import cp_model
except Exception:  # pragma: no cover - optional dependency
    cp_model = None

from backend.models.schema import Brief, LayoutResult, PlacedRoom, RoomSpec

# Default conversion: 1 grid cell approximates 1 square foot (~30 cm).
UNITS_PER_FOOT = 30


@dataclass
class GridRect:
    x: int
    y: int
    w: int
    h: int

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)

    def center(self) -> Tuple[float, float]:
        return (self.x + self.w / 2.0, self.y + self.h / 2.0)


class GridPlanner:
    def __init__(self, brief: Brief, cell_size: int = UNITS_PER_FOOT) -> None:
        self.brief = brief
        self.cell_size = max(1, cell_size)
        self.grid_w = max(1, math.ceil(brief.building_w / self.cell_size))
        self.grid_h = max(1, math.ceil(brief.building_h / self.cell_size))

        self.room_specs: List[RoomSpec] = list(brief.rooms)
        self.min_corridor_cells = (
            max(1, math.ceil(brief.hard.min_corridor_width / self.cell_size))
            if brief.hard and brief.hard.min_corridor_width
            else None
        )
        self.corridor_flex = 2 if self.min_corridor_cells else 0
        private_rooms = [
            spec
            for spec in self.room_specs
            if spec.name.lower().startswith(("bed", "bath"))
        ]
        min_private = (
            brief.connectivity.min_private_for_corridor
            if brief.connectivity and brief.connectivity.min_private_for_corridor
            else 3
        )
        corridor_possible = (
            self.min_corridor_cells is not None
            and (self.min_corridor_cells <= self.grid_w or self.min_corridor_cells <= self.grid_h)
        )
        self.require_corridor = corridor_possible and len(private_rooms) >= min_private

        self.adjacency: Dict[str, Set[str]] = {spec.name: set() for spec in self.room_specs}
        if brief.soft and brief.soft.adjacency:
            for pref in brief.soft.adjacency:
                self.adjacency.setdefault(pref.a, set()).add(pref.b)
                self.adjacency.setdefault(pref.b, set()).add(pref.a)
        for a, b in brief.adjacency_preferences:
            self.adjacency.setdefault(a, set()).add(b)
            self.adjacency.setdefault(b, set()).add(a)

        self.dropped: List[str] = []
        self._init_state()
        self.best_corridor_option: Tuple[GridRect, ...] = tuple()

    def _init_state(self) -> None:
        self.occupancy: List[List[Optional[str]]] = [
            [None for _ in range(self.grid_w)] for _ in range(self.grid_h)
        ]
        self.placed: Dict[str, GridRect] = {}
        self.best_arrangement: Dict[str, GridRect] = {}
        self.best_count: int = 0

    def build(self) -> LayoutResult:
        specs = list(self.room_specs)
        specs.sort(
            key=lambda spec: (
                -len(self.adjacency.get(spec.name, ())),
                -self._estimated_area_cells(spec),
                -max(self._min_dim_cells(spec.min_w), self._min_dim_cells(spec.min_h)),
            )
        )

        best_global: Dict[str, GridRect] = {}
        best_global_count = -1
        best_corridor: Tuple[GridRect, ...] = tuple()

        for corridor_option in self._corridor_candidates():
            self._init_state()
            corridor_names: List[str] = []
            for idx, rect in enumerate(corridor_option):
                name = "corridor" if idx == 0 else f"corridor_{idx}"
                corridor_names.append(name)
                self.placed[name] = rect
                self._stamp(name, rect)
            self.best_arrangement = {name: rect for name, rect in self.placed.items()}
            self.best_count = len(self.placed)

            self._search(specs, 0)

            arrangement = self.best_arrangement
            count_rooms = len([k for k in arrangement if not k.startswith("corridor")])
            if count_rooms > best_global_count:
                best_global_count = count_rooms
                best_global = {k: GridRect(v.x, v.y, v.w, v.h) for k, v in arrangement.items()}
                best_corridor = corridor_option

        arrangement = {k: GridRect(v.x, v.y, v.w, v.h) for k, v in best_global.items()}
        self.best_corridor_option = best_corridor
        self._apply_arrangement(arrangement)

        dropped = [
            spec.name for spec in specs if spec.name not in arrangement.keys()
        ]
        if dropped:
            arrangement, dropped = self._second_pass_for_dropped(arrangement, dropped)

        arrangement = self._grow_rooms(arrangement)

        if dropped:
            cpsat_solution = self._attempt_cpsat(best_corridor)
            if cpsat_solution:
                arrangement = cpsat_solution
                self._apply_arrangement(arrangement)
                dropped = [
                    spec.name for spec in specs if spec.name not in arrangement.keys()
                ]
                if dropped:
                    arrangement, dropped = self._second_pass_for_dropped(arrangement, dropped)
                arrangement = self._grow_rooms(arrangement)

        placed_rooms = [
            PlacedRoom(
                name=name,
                x=rect.x * self.cell_size,
                y=rect.y * self.cell_size,
                w=rect.w * self.cell_size,
                h=rect.h * self.cell_size,
            )
            for name, rect in self._ordered_rooms(arrangement).items()
        ]
        self.dropped = dropped
        return LayoutResult(rooms=placed_rooms, dropped=dropped)

    def _ordered_rooms(self, rooms: Dict[str, GridRect]) -> Dict[str, GridRect]:
        order = {spec.name: idx for idx, spec in enumerate(self.brief.rooms)}

        def sort_key(item: Tuple[str, GridRect]) -> Tuple[int, str]:
            name, _ = item
            if name == "corridor":
                return (-1, name)
            return (order.get(name, 1_000), name)

        return dict(sorted(rooms.items(), key=sort_key))

    def _estimated_area_cells(self, spec: RoomSpec) -> int:
        area_units = spec.target_area or spec.min_w * spec.min_h
        area_cells = max(1, int(round(area_units / (self.cell_size**2))))
        min_cells = self._min_dim_cells(spec.min_w) * self._min_dim_cells(spec.min_h)
        return max(area_cells, min_cells)

    def _min_dim_cells(self, value: int) -> int:
        return max(1, math.ceil(value / self.cell_size))

    def _candidate_dims(self, spec: RoomSpec) -> List[Tuple[int, int]]:
        if spec.name == "corridor":
            heights = range(
                self.min_corridor_cells,
                min(self.grid_h, (self.min_corridor_cells or 1) + self.corridor_flex) + 1,
            )
            return [(self.grid_w, h) for h in heights]

        area_cells = self._estimated_area_cells(spec)
        min_w = self._min_dim_cells(spec.min_w)
        min_h = self._min_dim_cells(spec.min_h)

        target_ratio = 1.5
        tol = 0.75
        if self.brief.soft:
            target_ratio = self.brief.soft.aspect_ratio_target
            tol = self.brief.soft.aspect_ratio_tolerance
        max_ratio = max(3.0, target_ratio + tol)

        min_area = min_w * min_h
        max_area = self.grid_w * self.grid_h

        offsets = [0, -1, -2, -3, -4, 1, 2, 3]
        area_candidates = set()
        for off in offsets:
            candidate = area_cells + off
            candidate = max(min_area, min(candidate, max_area))
            area_candidates.add(candidate)
        area_candidates.add(min_area)
        area_candidates.add(area_cells)

        candidates: Set[Tuple[int, int]] = set()

        def add_candidate(w: int, h: int) -> None:
            if w <= 0 or h <= 0:
                return
            if w > self.grid_w or h > self.grid_h:
                return
            ratio = max(w, h) / max(1, min(w, h))
            if ratio > max_ratio:
                return
            candidates.add((w, h))

        for area_candidate in sorted(area_candidates):
            width_cap = min(
                self.grid_w,
                max(min_w, int(math.ceil(math.sqrt(area_candidate))) + 4),
            )
            for w in range(min_w, width_cap + 1):
                h = max(min_h, math.ceil(area_candidate / w))
                if h > self.grid_h:
                    continue
                add_candidate(w, h)
                add_candidate(h, w)
            # ensure slender variants anchored at min dimensions
            h_slender = min(self.grid_h, max(min_h, math.ceil(area_candidate / max(1, min_w))))
            add_candidate(min_w, h_slender)
            w_slender = min(self.grid_w, max(min_w, math.ceil(area_candidate / max(1, min_h))))
            add_candidate(w_slender, min_h)

        if not candidates:
            candidates.add((min_w, min_h))

        def score(dim: Tuple[int, int]) -> Tuple[float, float, int]:
            w, h = dim
            area_penalty = abs((w * h) - area_cells)
            aspect = abs((w / max(1, h)) - target_ratio)
            return (aspect, area_penalty, -(w * h))

        return sorted(candidates, key=score)

    def _placements_for_spec(self, spec: RoomSpec, limit: Optional[int] = None) -> List[GridRect]:
        neighbors = self.adjacency.get(spec.name, set())
        results: List[Tuple[float, GridRect]] = []
        dims = self._candidate_dims(spec)
        for w, h in dims:
            x_range, y_range = self._search_window(spec.name, w, h, neighbors)
            for y in y_range:
                for x in x_range:
                    if not self._is_empty(x, y, w, h):
                        continue
                    score = self._score_position(spec.name, x, y, w, h, neighbors)
                    if score is None:
                        continue
                    results.append((score, GridRect(x, y, w, h)))
                    if limit and len(results) >= limit:
                        break
                if limit and len(results) >= limit:
                    break
        results.sort(key=lambda item: item[0])
        return [rect for _, rect in results]

    def _search(self, specs: List[RoomSpec], idx: int) -> bool:
        if idx >= len(specs):
            if len(self.placed) > self.best_count:
                self.best_count = len(self.placed)
                self.best_arrangement = {
                    k: GridRect(v.x, v.y, v.w, v.h) for k, v in self.placed.items()
                }
            return True

        spec = specs[idx]
        placements = self._placements_for_spec(spec)
        full_solution = False
        for rect in placements:
            self.placed[spec.name] = rect
            self._stamp(spec.name, rect)
            if len(self.placed) > self.best_count:
                self.best_count = len(self.placed)
                self.best_arrangement = {
                    k: GridRect(v.x, v.y, v.w, v.h) for k, v in self.placed.items()
                }
            if self._ensure_future_feasible(specs, idx + 1):
                if self._search(specs, idx + 1):
                    full_solution = True
                    break
            self._unstamp(spec.name, rect)
            self.placed.pop(spec.name, None)

        if not full_solution and len(self.placed) > self.best_count:
            self.best_count = len(self.placed)
            self.best_arrangement = {
                k: GridRect(v.x, v.y, v.w, v.h) for k, v in self.placed.items()
            }
        return full_solution

    def _ensure_future_feasible(self, specs: List[RoomSpec], start_idx: int) -> bool:
        for i in range(start_idx, len(specs)):
            spec = specs[i]
            if spec.name in self.placed:
                continue
            if not self._placements_for_spec(spec, limit=1):
                return False
        return True

    def _apply_arrangement(self, arrangement: Dict[str, GridRect]) -> None:
        self._init_state()
        for name in list(arrangement.keys()):
            rect = arrangement[name]
            rect_copy = GridRect(rect.x, rect.y, rect.w, rect.h)
            self.placed[name] = rect_copy
            arrangement[name] = rect_copy
            self._stamp(name, rect_copy)

    def _second_pass_for_dropped(
        self,
        arrangement: Dict[str, GridRect],
        dropped: List[str],
    ) -> Tuple[Dict[str, GridRect], List[str]]:
        remaining: List[str] = []
        specs_by_name = {spec.name: spec for spec in self.room_specs}
        for name in dropped:
            spec = specs_by_name.get(name)
            if not spec:
                continue
            candidates = self._placements_for_spec(spec)
            if not candidates:
                remaining.append(name)
                continue
            rect = candidates[0]
            arrangement[name] = rect
            self.placed[name] = rect
            self._stamp(name, rect)
        return arrangement, remaining

    def _grow_rooms(self, arrangement: Dict[str, GridRect]) -> Dict[str, GridRect]:
        specs_by_name = {spec.name: spec for spec in self.room_specs}
        for name, rect in list(arrangement.items()):
            if name.startswith("corridor"):
                continue
            spec = specs_by_name.get(name)
            if not spec or spec.target_area is None:
                continue
            target_cells = math.ceil(spec.target_area / (self.cell_size**2))
            if rect.w * rect.h >= target_cells:
                continue
            grown = self._grow_rect(name, rect, target_cells)
            arrangement[name] = grown
        return arrangement

    def _grow_rect(self, name: str, rect: GridRect, target_cells: int) -> GridRect:
        current = GridRect(rect.x, rect.y, rect.w, rect.h)
        while current.w * current.h < target_cells:
            options: List[Tuple[float, str]] = []
            if self._can_expand(name, current, dx=-1, dy=0):
                options.append((current.x, "left"))
            if self._can_expand(name, current, dx=1, dy=0):
                options.append((self.grid_w - (current.x + current.w), "right"))
            if self._can_expand(name, current, dx=0, dy=-1):
                options.append((current.y, "up"))
            if self._can_expand(name, current, dx=0, dy=1):
                options.append((self.grid_h - (current.y + current.h), "down"))
            if not options:
                break
            _, direction = min(options, key=lambda item: item[0])
            if direction == "left":
                current.x -= 1
                current.w += 1
                for yy in range(current.y, current.y + current.h):
                    self.occupancy[yy][current.x] = name
            elif direction == "right":
                col = current.x + current.w
                for yy in range(current.y, current.y + current.h):
                    self.occupancy[yy][col] = name
                current.w += 1
            elif direction == "up":
                current.y -= 1
                current.h += 1
                for xx in range(current.x, current.x + current.w):
                    self.occupancy[current.y][xx] = name
            elif direction == "down":
                row = current.y + current.h
                for xx in range(current.x, current.x + current.w):
                    self.occupancy[row][xx] = name
                current.h += 1
        self.placed[name] = current
        return current

    def _can_expand(self, name: str, rect: GridRect, dx: int, dy: int) -> bool:
        if dx == -1:
            if rect.x == 0:
                return False
            x = rect.x - 1
            for yy in range(rect.y, rect.y + rect.h):
                if self.occupancy[yy][x] not in (None, name):
                    return False
            return True
        if dx == 1:
            x = rect.x + rect.w
            if x >= self.grid_w:
                return False
            for yy in range(rect.y, rect.y + rect.h):
                if self.occupancy[yy][x] not in (None, name):
                    return False
            return True
        if dy == -1:
            if rect.y == 0:
                return False
            y = rect.y - 1
            for xx in range(rect.x, rect.x + rect.w):
                if self.occupancy[y][xx] not in (None, name):
                    return False
            return True
        if dy == 1:
            y = rect.y + rect.h
            if y >= self.grid_h:
                return False
            for xx in range(rect.x, rect.x + rect.w):
                if self.occupancy[y][xx] not in (None, name):
                    return False
            return True
        return False

    def _attempt_cpsat(self, corridor_option: Tuple[GridRect, ...]) -> Optional[Dict[str, GridRect]]:
        if cp_model is None:
            return None
        corridor_cells = self._cells_for_rects(corridor_option)
        placements: Dict[str, List[GridRect]] = {}
        specs_by_name = {spec.name: spec for spec in self.room_specs}
        for spec in self.room_specs:
            options = self._all_positions_for_spec(spec, corridor_cells, limit=None)
            if not options:
                return None
            placements[spec.name] = options

        model = cp_model.CpModel()
        selection: Dict[str, List[cp_model.IntVar]] = {}
        for spec_name, options in placements.items():
            vars_for_spec = []
            for idx, _ in enumerate(options):
                vars_for_spec.append(model.NewBoolVar(f"place_{spec_name}_{idx}"))
            selection[spec_name] = vars_for_spec
            model.Add(sum(vars_for_spec) == 1)

        cell_vars: Dict[Tuple[int, int], List[cp_model.IntVar]] = {}
        for spec_name, options in placements.items():
            vars_for_spec = selection[spec_name]
            for idx, rect in enumerate(options):
                var = vars_for_spec[idx]
                for xx in range(rect.x, rect.x + rect.w):
                    for yy in range(rect.y, rect.y + rect.h):
                        cell = (xx, yy)
                        if cell in corridor_cells:
                            model.Add(var == 0)
                        else:
                            cell_vars.setdefault(cell, []).append(var)

        for vars_at_cell in cell_vars.values():
            if not vars_at_cell:
                continue
            model.Add(sum(vars_at_cell) <= 1)

        objective_terms = []
        for spec_name, options in placements.items():
            spec = specs_by_name[spec_name]
            target_cells = self._estimated_area_cells(spec)
            for idx, rect in enumerate(options):
                diff = abs(rect.w * rect.h - target_cells)
                if diff:
                    objective_terms.append(diff * selection[spec_name][idx])
        if objective_terms:
            model.Minimize(sum(objective_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 2.0
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return None

        arrangement: Dict[str, GridRect] = {}
        for spec_name, options in placements.items():
            vars_for_spec = selection[spec_name]
            for idx, var in enumerate(vars_for_spec):
                if solver.BooleanValue(var):
                    arrangement[spec_name] = options[idx]
                    break
        for idx, rect in enumerate(corridor_option):
            name = "corridor" if idx == 0 else f"corridor_{idx}"
            arrangement[name] = rect
        return arrangement

    def _all_positions_for_spec(
        self,
        spec: RoomSpec,
        corridor_cells: Set[Tuple[int, int]],
        limit: Optional[int] = None,
    ) -> List[GridRect]:
        candidates: List[Tuple[float, GridRect]] = []
        for w, h in self._candidate_dims(spec):
            for y in range(0, self.grid_h - h + 1):
                for x in range(0, self.grid_w - w + 1):
                    intersects_corridor = False
                    for xx in range(x, x + w):
                        for yy in range(y, y + h):
                            if (xx, yy) in corridor_cells:
                                intersects_corridor = True
                                break
                        if intersects_corridor:
                            break
                    if intersects_corridor:
                        continue
                    cx = x + w / 2.0
                    cy = y + h / 2.0
                    score = abs(cx - self.grid_w / 2.0) + abs(cy - self.grid_h / 2.0)
                    candidates.append((score, GridRect(x, y, w, h)))
        candidates.sort(key=lambda item: item[0])
        if limit:
            candidates = candidates[:limit]
        return [rect for _, rect in candidates]

    def _cells_for_rects(self, rects: Iterable[GridRect]) -> Set[Tuple[int, int]]:
        cells: Set[Tuple[int, int]] = set()
        for rect in rects:
            for xx in range(rect.x, rect.x + rect.w):
                for yy in range(rect.y, rect.y + rect.h):
                    cells.add((xx, yy))
        return cells

    def _corridor_candidates(self) -> List[Tuple[GridRect, ...]]:
        allow_none = not self.require_corridor
        if not self.min_corridor_cells:
            return [tuple()]

        candidates: List[Tuple[GridRect, ...]] = []
        seen: Set[Tuple[Tuple[int, int, int, int], ...]] = set()

        def add_option(option: Tuple[GridRect, ...]) -> None:
            key = tuple(sorted((r.x, r.y, r.w, r.h) for r in option))
            if key in seen:
                return
            seen.add(key)
            candidates.append(option)

        if allow_none:
            add_option(tuple())

        h_min = min(self.min_corridor_cells, self.grid_h)
        w_min = min(self.min_corridor_cells, self.grid_w)
        if h_min <= 0 and w_min <= 0:
            return candidates or [tuple()]

        h_max = min(self.grid_h, h_min + self.corridor_flex)
        w_max = min(self.grid_w, w_min + self.corridor_flex)

        center_y = self.grid_h / 2.0
        center_x = self.grid_w / 2.0

        horizontal_rects: List[GridRect] = []
        for h in range(max(1, h_min), max(1, h_max) + 1):
            if h > self.grid_h:
                continue
            positions = list(range(0, self.grid_h - h + 1))
            positions.sort(key=lambda y: abs((y + h / 2.0) - center_y))
            for y in positions[:6]:
                horizontal_rects.append(GridRect(0, y, self.grid_w, h))
            if 2 * h < self.grid_h:
                horizontal_rects.append(GridRect(0, 0, self.grid_w, h))
                horizontal_rects.append(GridRect(0, self.grid_h - h, self.grid_w, h))

        vertical_rects: List[GridRect] = []
        for w in range(max(1, w_min), max(1, w_max) + 1):
            if w > self.grid_w:
                continue
            positions = list(range(0, self.grid_w - w + 1))
            positions.sort(key=lambda x: abs((x + w / 2.0) - center_x))
            for x in positions[:6]:
                vertical_rects.append(GridRect(x, 0, w, self.grid_h))
            if 2 * w < self.grid_w:
                vertical_rects.append(GridRect(0, 0, w, self.grid_h))
                vertical_rects.append(GridRect(self.grid_w - w, 0, w, self.grid_h))

        for rect in horizontal_rects[:10]:
            add_option((rect,))
        for rect in vertical_rects[:10]:
            add_option((rect,))

        for rect in horizontal_rects:
            h = rect.h
            if 2 * h >= self.grid_h:
                continue
            top = GridRect(0, 0, self.grid_w, h)
            bottom = GridRect(0, self.grid_h - h, self.grid_w, h)
            add_option((top, bottom))
        for rect in vertical_rects:
            w = rect.w
            if 2 * w >= self.grid_w:
                continue
            left = GridRect(0, 0, w, self.grid_h)
            right = GridRect(self.grid_w - w, 0, w, self.grid_h)
            add_option((left, right))

        for h_rect in horizontal_rects[:4]:
            for v_rect in vertical_rects[:4]:
                add_option((h_rect, v_rect))

        return candidates or [tuple()]

    def _is_empty(self, x: int, y: int, w: int, h: int) -> bool:
        if x < 0 or y < 0 or x + w > self.grid_w or y + h > self.grid_h:
            return False
        for yy in range(y, y + h):
            row = self.occupancy[yy]
            for xx in range(x, x + w):
                if row[xx] is not None:
                    return False
        return True

    def _score_position(
        self,
        name: str,
        x: int,
        y: int,
        w: int,
        h: int,
        neighbors: Iterable[str],
    ) -> Optional[float]:
        rect = (x, y, w, h)
        cx = x + w / 2.0
        cy = y + h / 2.0
        score = abs(cx - self.grid_w / 2.0) * 0.3 + abs(cy - self.grid_h / 2.0) * 0.3

        neighbor_set = set(neighbors)
        for other_name, other_rect in self.placed.items():
            if other_name == name:
                continue
            gap = self._edge_gap(rect, other_rect.as_tuple())
            if other_name.startswith("corridor"):
                score += gap * 1.5
                continue
            if other_name not in neighbor_set:
                score += gap * 0.5
            else:
                if gap > 0:
                    score += 200.0 + gap * 10.0
                else:
                    score -= 25.0
            ocx, ocy = other_rect.center()
            score += 0.05 * (abs(cx - ocx) + abs(cy - ocy))
        score += 0.01 * (x + y)
        return score

    def _edge_gap(self, a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> int:
        ax0, ay0, aw, ah = a
        bx0, by0, bw, bh = b
        ax1, ay1 = ax0 + aw, ay0 + ah
        bx1, by1 = bx0 + bw, by0 + bh

        def gap_1d(a0: int, a1: int, b0: int, b1: int) -> int:
            if a1 <= b0:
                return b0 - a1
            if b1 <= a0:
                return a0 - b1
            return 0

        dx = gap_1d(ax0, ax1, bx0, bx1)
        dy = gap_1d(ay0, ay1, by0, by1)
        if dx == 0 and dy == 0:
            return 0
        if dx == 0:
            return dy
        if dy == 0:
            return dx
        return min(dx, dy)

    def _stamp(self, name: str, rect: GridRect) -> None:
        for yy in range(rect.y, rect.y + rect.h):
            row = self.occupancy[yy]
            for xx in range(rect.x, rect.x + rect.w):
                row[xx] = name

    def _unstamp(self, name: str, rect: GridRect) -> None:
        for yy in range(rect.y, rect.y + rect.h):
            row = self.occupancy[yy]
            for xx in range(rect.x, rect.x + rect.w):
                if row[xx] == name:
                    row[xx] = None

    def _search_window(
        self,
        name: str,
        w: int,
        h: int,
        neighbors: Iterable[str],
    ) -> Tuple[range, range]:
        if name == "corridor":
            return range(0, 1), range(0, self.grid_h - h + 1)

        pads = 2
        placed_neighbors = [self.placed[n] for n in neighbors if n in self.placed]
        corridors = [rect for key, rect in self.placed.items() if key.startswith("corridor")]
        if not placed_neighbors and corridors and not name.startswith("corridor"):
            placed_neighbors = corridors

        if not placed_neighbors:
            return range(0, self.grid_w - w + 1), range(0, self.grid_h - h + 1)

        min_x = min(r.x for r in placed_neighbors)
        max_x = max(r.x + r.w for r in placed_neighbors)
        min_y = min(r.y for r in placed_neighbors)
        max_y = max(r.y + r.h for r in placed_neighbors)

        x_start = max(0, min_x - w - pads)
        x_end = min(self.grid_w - w, max_x + pads)
        y_start = max(0, min_y - h - pads)
        y_end = min(self.grid_h - h, max_y + pads)

        if x_start > x_end or y_start > y_end:
            return range(0, self.grid_w - w + 1), range(0, self.grid_h - h + 1)

        return range(x_start, x_end + 1), range(y_start, y_end + 1)


def solve_on_grid(brief: Brief, cell_size: int = UNITS_PER_FOOT) -> LayoutResult:
    planner = GridPlanner(brief, cell_size=cell_size)
    return planner.build()
