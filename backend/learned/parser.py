from __future__ import annotations

import re
from typing import Dict, List, Optional

from backend.models.schema import Brief, RoomSpec, HardConstraints, SoftObjectives, AdjacencyPreference

_MM_PER_M = 1000
_MM_PER_FT = 304.8

_DEFAULTS = {
    "living": (3000, 3000, 120000),
    "kitchen": (2500, 2500, 75000),
    "bed": (3000, 3000, 90000),
    "bath": (1500, 2000, 30000),
}

_WORD_NUM = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
}


def _parse_dimensions(text: str) -> Optional[tuple[int, int]]:
    # e.g., 12x8 m, 40x26 ft, 1200x800
    m = re.search(r"(\d+(?:\.\d+)?)\s*[xX×]\s*(\d+(?:\.\d+)?)(?:\s*(m|meter|meters|ft|feet))?", text)
    if not m:
        return None
    a, b, unit = m.groups()
    a = float(a)
    b = float(b)
    if unit is None:
        # assume mm if large, else meters
        if a > 50 and b > 50:
            return int(a), int(b)
        return int(a * _MM_PER_M), int(b * _MM_PER_M)
    unit = unit.lower()
    if unit.startswith("m"):
        return int(a * _MM_PER_M), int(b * _MM_PER_M)
    else:
        return int(a * _MM_PER_FT), int(b * _MM_PER_FT)


def _parse_count(text: str, key: str) -> int:
    # matches "2 bed", "two bedrooms"
    patt = rf"(\b(\d+|one|two|three|four|five)\b)\s*{key}"
    m = re.search(patt, text, re.IGNORECASE)
    if not m:
        return 0
    tok = m.group(1).lower()
    if tok.isdigit():
        return int(tok)
    return _WORD_NUM.get(tok, 0)


def parse_requirements_text(text: str) -> Brief:
    t = text.strip()
    dims = _parse_dimensions(t) or (1200, 800)
    floors = 1
    mf = re.search(r"(\d+)\s*(floor|floors|story|stories)", t, re.IGNORECASE)
    if mf:
        floors = int(mf.group(1))

    rooms: List[RoomSpec] = []

    def add_room(name: str, count: int):
        if count <= 0:
            return
        min_w, min_h, tgt = _DEFAULTS[name if name in _DEFAULTS else "living"]
        for i in range(count):
            suffix = "" if count == 1 else str(i + 1)
            nm = name if suffix == "" else f"{name}{suffix}"
            rooms.append(RoomSpec(name=nm, min_w=min_w, min_h=min_h, target_area=tgt))

    # counts
    add_room("bed", max(_parse_count(t, "bed"), _parse_count(t, "bedroom")))
    add_room("bath", max(_parse_count(t, "bath"), _parse_count(t, "bathroom")))
    # ensure one of each living/kitchen if mentioned
    if re.search(r"\bkitchen\b", t, re.IGNORECASE):
        add_room("kitchen", 1)
    if re.search(r"\bliving\b|\blounge\b", t, re.IGNORECASE):
        add_room("living", 1)
    # defaults if empty
    if not rooms:
        add_room("living", 1)
        add_room("kitchen", 1)
        add_room("bed", 1)
        add_room("bath", 1)

    hard = HardConstraints()
    soft = SoftObjectives()
    # prefer kitchen adjacent to living
    soft.adjacency.append(AdjacencyPreference(a="kitchen", b="living"))

    return Brief(building_w=dims[0], building_h=dims[1], building_floors=floors, rooms=rooms, soft=soft)
