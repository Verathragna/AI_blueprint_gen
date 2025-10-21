from typing import Dict, Any, List
from math import ceil, sqrt

try:
    from ortools.sat.python import cp_model
except Exception:  # pragma: no cover - allow working without OR-Tools installed yet
    cp_model = None

from backend.models.schema import Brief, LayoutResult, PlacedRoom, RoomSpec
from backend.solver.refine import add_corridor, ensure_connectivity
from backend.solver.cpsat import solve_rect_pack
from backend.solver.packing import pack_next_fit


class LayoutSolver:
    """
    Hybrid layout solver:
    - If OR-Tools is unavailable or inputs are underspecified, use a fast heuristic packer.
    - Otherwise, CP-SAT model can be added in future iterations.
    Units are arbitrary integer grid units (e.g., centimeters).
    """

    def solve(self, brief: Dict[str, Any], seed: Dict[str, Any] | None = None) -> Dict[str, Any]:
        # Accept dict or pydantic Brief
        if not isinstance(brief, Brief):
            brief = Brief(**brief)

        # If seed provided, start from it (clamped to envelope)
        if seed:
            layout = LayoutResult(**seed)
        else:
            # improved heuristic packer
            layout = pack_next_fit(brief)

        # Optionally add corridor if requested
        layout = add_corridor(layout, brief)
        # Ensure connectivity (snap isolated rooms)
        layout = ensure_connectivity(layout, brief)

        # Try CP-SAT if available; fall back to heuristic result
        cp_layout = solve_rect_pack(brief, layout)
        if cp_layout is not None:
            layout = cp_layout
            # post-process connectivity again just in case
            layout = ensure_connectivity(layout, brief)

        return layout.model_dump()

    def _heuristic_pack(self, brief: Brief) -> Dict[str, Any]:
        # Simple row-wise packer with line breaks when exceeding building width
        x_cursor, y_cursor = 0, 0
        row_height = 0
        placed: List[PlacedRoom] = []
        dropped: List[str] = []

        # Size each room from target_area when provided; otherwise use min dims
        def choose_size(spec: RoomSpec) -> tuple[int, int]:
            if spec.target_area:
                w0 = max(spec.min_w, int(sqrt(spec.target_area)))
                h0 = ceil(spec.target_area / w0)
                w = max(w0, spec.min_w)
                h = max(h0, spec.min_h)
            else:
                w, h = spec.min_w, spec.min_h
            # clamp overly large rooms to building bounds
            w = min(w, brief.building_w)
            h = min(h, brief.building_h)
            return w, h

        for spec in brief.rooms:
            w, h = choose_size(spec)
            # new row if necessary
            if x_cursor + w > brief.building_w:
                x_cursor = 0
                y_cursor += row_height
                row_height = 0
            # check fit vertically
            if y_cursor + h > brief.building_h:
                dropped.append(spec.name)
                continue
            placed.append(PlacedRoom(name=spec.name, x=x_cursor, y=y_cursor, w=w, h=h))
            x_cursor += w
            row_height = max(row_height, h)

        return LayoutResult(rooms=placed, dropped=dropped).model_dump()
