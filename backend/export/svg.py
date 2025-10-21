from __future__ import annotations

from typing import List

from backend.models.scene import Building


def to_svg(building: Building, stroke_width: int = 2) -> str:
    W, H = building.width, building.height
    # SVG uses y down; our coords already y down
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<g fill="none" stroke="#222" stroke-width="2">',
    ]
    # Spaces
    for f in building.floors:
        for sp in f.spaces:
            x, y, w, h = sp.rect.x, sp.rect.y, sp.rect.w, sp.rect.h
            lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" stroke="#333" fill="none" />')
            # Label
            lines.append(
                f'<text x="{x + w/2}" y="{y + h/2}" font-size="24" text-anchor="middle" fill="#555">{sp.name}</text>'
            )
            # Openings
            for op in sp.openings:
                ox, oy, ow, oh = op.at.x - op.w/2, op.at.y - op.h/2, op.w, op.h
                color = "#0a7" if op.opening_type.name == "DOOR" else "#07a"
                lines.append(f'<rect x="{ox}" y="{oy}" width="{ow}" height="{oh}" stroke="{color}" />')
    lines.append("</g>")
    lines.append("</svg>")
    return "\n".join(lines)