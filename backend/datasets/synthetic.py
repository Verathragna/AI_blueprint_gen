from __future__ import annotations

import json
from typing import Iterable, List, Optional
import random

from backend.core.orchestrator import Orchestrator
from backend.models.schema import Brief, RoomSpec
from backend.models.scene import from_brief_and_layout
from backend.datasets.schema import DatasetSample, sample_from_building
from backend.datasets.augment import mirror_horizontal, rotate_90, scale_uniform, add_style_tag


def _random_brief() -> Brief:
    # Simple random sampler within reasonable bounds
    W = random.choice([1000, 1200, 1400])
    H = random.choice([800, 900, 1000])
    n_bed = random.choice([1, 2, 3])
    rooms = [RoomSpec(name="living", min_w=300, min_h=300, target_area=120000),
             RoomSpec(name="kitchen", min_w=250, min_h=250, target_area=75000)]
    for i in range(n_bed):
        rooms.append(RoomSpec(name=f"bed{i+1}", min_w=300, min_h=300, target_area=90000))
    rooms.append(RoomSpec(name="bath", min_w=150, min_h=200, target_area=30000))
    return Brief(building_w=W, building_h=H, building_floors=1, rooms=rooms)


def generate_synthetic(n: int = 10, seed: Optional[int] = None, style_tag: Optional[str] = None) -> List[DatasetSample]:
    if seed is not None:
        random.seed(seed)
    orch = Orchestrator()
    out: List[DatasetSample] = []
    for _ in range(n):
        brief = _random_brief()
        res = orch.run(brief.model_dump())
        scene = from_brief_and_layout(brief, res.layout)
        sample = sample_from_building(scene)
        # augmentations
        if random.random() < 0.5:
            sample = mirror_horizontal(sample)
        if random.random() < 0.5:
            sample = rotate_90(sample)
        s = random.choice([0.9, 1.0, 1.1])
        sample = scale_uniform(sample, s)
        if style_tag:
            sample = add_style_tag(sample, style_tag)
        out.append(sample)
    return out


def write_jsonl(samples: Iterable[DatasetSample], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s.model_dump()) + "\n")
