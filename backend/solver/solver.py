from typing import Dict, Any, List
from math import ceil, sqrt

try:
    from ortools.sat.python import cp_model
except Exception:  # pragma: no cover - allow working without OR-Tools installed yet
    cp_model = None

from backend.models.schema import Brief, LayoutResult, PlacedRoom, RoomSpec
from backend.solver.refine import add_corridor, ensure_connectivity
from backend.solver.cpsat import solve_rect_pack
from backend.solver.packing import pack_next_fit, pack_with_hub


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
            # improved heuristic packer with hub-first placement
            layout = pack_with_hub(brief)
            if not layout.rooms:
                layout = pack_next_fit(brief)

        # Corridor policy
        private_count = len([s for s in (brief.rooms if isinstance(brief, Brief) else Brief(**brief).rooms) if s.name.lower().startswith('bed') or s.name.lower().startswith('bath')])
        min_priv = (brief.connectivity.min_private_for_corridor if isinstance(brief, Brief) and brief.connectivity else 3)
        use_corr = private_count >= min_priv

        if use_corr:
            # Heuristic initial corridor placement
            from backend.solver.packing import pack_with_corridor
            init = pack_with_corridor(brief)
            # Extract corridor rect
            cor = next((r for r in init.rooms if r.name.lower().startswith('corridor')), None)
            if cor is not None:
                from backend.solver.cpsat import solve_with_corridor
                cp_layout = solve_with_corridor(
                    brief,
                    {"x": cor.x, "y": cor.y, "w": cor.w, "h": cor.h},
                    seed=init,
                    time_limit_s=1.0,
                    y_band=(max(0, cor.y-200), min((brief.building_h - cor.h), cor.y+200))
                )
                if cp_layout is None:
                    # try full-height band as fallback attempt (still CP-SAT), do not revert to heuristic silently
                    cp_layout = solve_with_corridor(
                        brief,
                        {"x": cor.x, "y": cor.y, "w": cor.w, "h": cor.h},
                        seed=init,
                        time_limit_s=1.5,
                        y_band=(0, max(0, brief.building_h - cor.h))
                    )
                layout = cp_layout if cp_layout is not None else init
            else:
                layout = init
            from backend.solver.refine import resolve_overlaps
            # After CP-SAT, avoid heuristic moves that can overlap; just run a safety resolver
            layout = resolve_overlaps(layout, brief)
        else:
            # Optionally add corridor if requested
            layout = add_corridor(layout, brief)
            # Ensure connectivity (snap isolated rooms)
            layout = ensure_connectivity(layout, brief)
            # Attraction to hub
            from backend.solver.refine import attract_to_hub, resolve_overlaps
            layout = attract_to_hub(layout, brief)
            layout = resolve_overlaps(layout, brief)

        # Try CP-SAT if available; fall back to heuristic result
        cp_layout = None if use_corr else solve_rect_pack(brief, layout)
        if cp_layout is not None:
            layout = cp_layout
            # post-process connectivity again just in case and attract
            layout = ensure_connectivity(layout, brief)
            from backend.solver.refine import attract_to_hub
            layout = attract_to_hub(layout, brief)

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
