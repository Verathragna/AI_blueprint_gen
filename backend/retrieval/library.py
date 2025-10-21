from __future__ import annotations

from typing import Dict, List, Optional

from backend.models.schema import LayoutResult, PlacedRoom, RoomSpec, Brief

# Simple curated templates: name -> list[(name, w, h)] in mm
_TEMPLATES: Dict[str, List[PlacedRoom]] = {
    "2bed_1bath": [
        PlacedRoom(name="living", x=0, y=0, w=400, h=300),
        PlacedRoom(name="kitchen", x=400, y=0, w=300, h=300),
        PlacedRoom(name="bed1", x=0, y=300, w=300, h=300),
        PlacedRoom(name="bed2", x=300, y=300, w=300, h=300),
        PlacedRoom(name="bath", x=600, y=300, w=100, h=200),
    ],
    "1bed_studio": [
        PlacedRoom(name="living", x=0, y=0, w=500, h=300),
        PlacedRoom(name="kitchen", x=0, y=300, w=300, h=200),
        PlacedRoom(name="bed1", x=500, y=0, w=300, h=300),
        PlacedRoom(name="bath", x=300, y=300, w=100, h=200),
    ],
}


def _program_signature(rooms: List[RoomSpec]) -> Dict[str, int]:
    # count by normalized name prefix (e.g., 'bed', 'bath')
    sig: Dict[str, int] = {}
    for r in rooms:
        key = r.name.lower()
        for prefix in ("bed", "bath", "living", "kitchen"):  # simple normalization
            if key.startswith(prefix):
                key = prefix
                break
        sig[key] = sig.get(key, 0) + 1
    return sig


def _distance(sig_a: Dict[str, int], sig_b: Dict[str, int]) -> int:
    keys = set(sig_a) | set(sig_b)
    return sum(abs(sig_a.get(k, 0) - sig_b.get(k, 0)) for k in keys)


def retrieve_seed(brief: Brief | dict) -> Optional[LayoutResult]:
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    if not brief.rooms:
        return None

    target = _program_signature(brief.rooms)
    best_key = None
    best_d = 1_000_000
    for key, rooms in _TEMPLATES.items():
        sig = _program_signature([RoomSpec(name=r.name, min_w=r.w, min_h=r.h) for r in rooms])
        d = _distance(target, sig)
        if d < best_d:
            best_d = d
            best_key = key
    if best_key is None:
        return None

    # Scale seed to envelope if necessary
    rooms = list(_TEMPLATES[best_key])
    dropped: List[str] = []
    # simple clamp
    scaled = []
    for r in rooms:
        if r.x + r.w > brief.building_w or r.y + r.h > brief.building_h:
            # attempt to fit by clamping at origin
            w = min(r.w, brief.building_w)
            h = min(r.h, brief.building_h)
            scaled.append(PlacedRoom(name=r.name, x=min(r.x, brief.building_w - w), y=min(r.y, brief.building_h - h), w=w, h=h))
        else:
            scaled.append(r)
    return LayoutResult(rooms=scaled, dropped=dropped)
