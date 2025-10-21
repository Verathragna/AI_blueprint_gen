from __future__ import annotations

from typing import Dict, Any, List

from backend.models.scene import Building

try:
    import ifcopenshell  # type: ignore
except Exception:  # pragma: no cover
    ifcopenshell = None


def to_ifc_interchange(building: Building) -> Dict[str, Any]:
    """IFC-like JSON interchange preserving IDs for round-trip."""
    data: Dict[str, Any] = {
        "schema": "IFC4-lite",
        "building": {
            "id": building.id,
            "width": building.width,
            "height": building.height,
            "floors": [],
        },
    }
    for f in building.floors:
        fl = {"id": f.id, "elevation": f.elevation, "spaces": []}
        for sp in f.spaces:
            room = {
                "id": sp.id,
                "name": sp.name,
                "rect": {"x": sp.rect.x, "y": sp.rect.y, "w": sp.rect.w, "h": sp.rect.h},
                "openings": [
                    {
                        "id": op.id,
                        "type": op.opening_type.value,
                        "at": {"x": op.at.x, "y": op.at.y},
                        "w": op.w,
                        "h": op.h,
                    }
                    for op in sp.openings
                ],
            }
            fl["spaces"].append(room)
        data["building"]["floors"].append(fl)
    return data


def to_ifc_file(building: Building, path: str) -> None:
    """If IfcOpenShell is available, write a basic IFC; otherwise write JSON interchange to .ifc.json."""
    if ifcopenshell is None:
        import json
        with open(path if path.endswith(".json") else path + ".json", "w", encoding="utf-8") as f:
            json.dump(to_ifc_interchange(building), f, indent=2)
        return
    # TODO: Implement real IFC population using IfcOpenShell API (spaces/walls/doors/windows)
    # Placeholder: write interchange JSON even if IfcOpenShell present for now
    import json
    with open(path if path.endswith(".json") else path + ".json", "w", encoding="utf-8") as f:
        json.dump(to_ifc_interchange(building), f, indent=2)