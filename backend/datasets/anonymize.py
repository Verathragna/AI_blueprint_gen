from __future__ import annotations

from typing import Dict
from uuid import uuid4

from backend.datasets.schema import DatasetSample


def anonymize_sample(sample: DatasetSample) -> DatasetSample:
    """Remove or obfuscate potentially identifying metadata; keep stable IDs for round-trip.
    - Clears meta except optional 'style' tag.
    - Normalizes room names to generic types with indices (bedroom_1, etc.).
    """
    # Clear metadata except style tag
    style = sample.meta.get("style") if sample.meta else None
    sample.meta = {}
    if style:
        sample.meta["style"] = style
    # Normalize room names
    type_counters: Dict[str, int] = {}
    for fl in sample.floors:
        for r in fl.rooms:
            base = r.name.lower().split("_")[0]
            mapping = {
                "bed": "bedroom",
                "bath": "bath",
                "kitchen": "kitchen",
                "living": "living",
            }
            t = mapping.get(base, base)
            type_counters[t] = type_counters.get(t, 0) + 1
            r.name = f"{t}_{type_counters[t]}"
    return sample
