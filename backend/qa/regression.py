from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from backend.models.schema import Brief, LayoutResult

GOLDEN_PATH = Path(__file__).parent / "golden.json"
SNAPSHOTS_DIR = Path(__file__).parent / "snapshots"
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def load_golden() -> List[Dict]:
    if GOLDEN_PATH.exists():
        return json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    # default small set
    return [
        {"brief": {"building_w": 1200, "building_h": 800, "rooms": [
            {"name": "living", "min_w": 300, "min_h": 300, "target_area": 120000},
            {"name": "kitchen", "min_w": 250, "min_h": 250, "target_area": 75000},
            {"name": "bed1", "min_w": 300, "min_h": 300, "target_area": 90000},
            {"name": "bed2", "min_w": 300, "min_h": 300, "target_area": 90000},
            {"name": "bath", "min_w": 150, "min_h": 200, "target_area": 30000}
        ]}},
    ]


def layout_similarity(a: LayoutResult, b: LayoutResult) -> float:
    # Average IoU over rooms matched by name; returns 0..1
    import math
    by_name_a = {r.name: r for r in a.rooms}
    by_name_b = {r.name: r for r in b.rooms}
    names = set(by_name_a) & set(by_name_b)
    if not names:
        return 0.0
    def iou(r1, r2):
        ax0, ay0, ax1, ay1 = r1.x, r1.y, r1.x + r1.w, r1.y + r1.h
        bx0, by0, bx1, by1 = r2.x, r2.y, r2.x + r2.w, r2.y + r2.h
        ix0, iy0 = max(ax0, bx0), max(ay0, by0)
        ix1, iy1 = min(ax1, bx1), min(ay1, by1)
        iw, ih = max(0, ix1 - ix0), max(0, iy1 - iy0)
        inter = iw * ih
        area = (r1.w * r1.h) + (r2.w * r2.h) - inter
        return inter / area if area > 0 else 0.0
    return sum(iou(by_name_a[n], by_name_b[n]) for n in names) / len(names)


def snapshot_layout(name: str, layout: LayoutResult) -> Path:
    p = SNAPSHOTS_DIR / f"{name}.layout.json"
    p.write_text(layout.model_dump_json(indent=2), encoding="utf-8")
    return p
