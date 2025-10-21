from __future__ import annotations

from typing import Dict, List

from backend.models.scene import Building


def compute_dimensions(building: Building) -> Dict[str, List[str]]:
    """Return simple dimension strings for spaces and openings (MVP)."""
    out: Dict[str, List[str]] = {"spaces": [], "openings": []}
    for fi, floor in enumerate(building.floors):
        for sp in floor.spaces:
            out["spaces"].append(
                f"floor{fi}:{sp.name} {sp.rect.w}x{sp.rect.h} at ({sp.rect.x},{sp.rect.y})"
            )
            for op in sp.openings:
                out["openings"].append(
                    f"floor{fi}:{sp.name}:{op.opening_type} at ({op.at.x},{op.at.y}) {op.w}x{op.h}"
                )
    return out
