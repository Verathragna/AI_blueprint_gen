from __future__ import annotations

from typing import Any, Dict, List

# Declarative base rules (IRC/IBC-inspired, simplified). Projects can extend/override.
DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        "id": "corridor.min.width",
        "title": "Corridor width must meet minimum",
        "severity": "error",
        "kind": "min_corridor_width",
        "min": 900,
    },
    {
        "id": "bedroom.window.egress",
        "title": "Bedrooms must have at least one egress-capable window",
        "severity": "error",
        "kind": "bedroom_egress_window",
    },
    {
        "id": "habitable.daylight.window",
        "title": "Habitable rooms require daylight/ventilation window",
        "severity": "warn",
        "kind": "habitable_daylight_window",
    },
    {
        "id": "bedroom.min.area",
        "title": "Bedroom minimum area",
        "severity": "error",
        "kind": "min_room_area",
        "selector": "bedroom",
        "min": 70000,
    },
]
