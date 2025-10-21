from __future__ import annotations

from typing import Iterable

from backend.models.scene import Building


# Minimal ASCII DXF (R12-like) generator for rectangles as LWPOLYLINE

def _dxf_header() -> str:
    return "\n".join([
        "0", "SECTION",
        "2", "ENTITIES",
    ])


def _dxf_footer() -> str:
    return "\n".join([
        "0", "ENDSEC",
        "0", "EOF",
    ])


def _lwpoly(points, closed=True, layer="0") -> str:
    parts = ["0", "LWPOLYLINE", "8", str(layer), "90", str(len(points) + (1 if closed else 0))]
    for (x, y) in points:
        parts += ["10", f"{x}", "20", f"{y}"]
    if closed:
        parts += ["70", "1"]
    return "\n".join(parts)


def to_dxf(building: Building) -> str:
    out = [_dxf_header()]
    W, H = building.width, building.height
    # Spaces as rectangles on A-AREA layer
    for fi, floor in enumerate(building.floors):
        for sp in floor.spaces:
            x, y, w, h = sp.rect.x, sp.rect.y, sp.rect.w, sp.rect.h
            pts = [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
            out.append(_lwpoly(pts, closed=True, layer="A-AREA"))
    out.append(_dxf_footer())
    return "\n".join(out)