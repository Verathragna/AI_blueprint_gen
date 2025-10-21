from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from backend.models.schema import SoftWeights

PREFS_PATH = Path(__file__).parent / "user_prefs.json"


def load_weights() -> SoftWeights:
    if PREFS_PATH.exists():
        try:
            data = json.loads(PREFS_PATH.read_text(encoding="utf-8"))
            return SoftWeights(**data)
        except Exception:
            pass
    return SoftWeights()


def save_weights(w: SoftWeights) -> None:
    PREFS_PATH.write_text(json.dumps(w.model_dump(), indent=2), encoding="utf-8")


def update_from_choice(chosen_terms: Dict[str, float], others_terms: List[Dict[str, float]]) -> SoftWeights:
    """Very simple online update: if chosen has lower penalty for a term than average of others, increase its weight slightly."""
    w = load_weights()
    avg = {}
    if others_terms:
        keys = set().union(*[t.keys() for t in others_terms])
        for k in keys:
            avg[k] = sum(t.get(k, 0.0) for t in others_terms) / len(others_terms)
    for k, v in chosen_terms.items():
        if avg.get(k, v + 1) > v:
            # chosen is better -> increase weight
            cur = getattr(w, k, None)
            if isinstance(cur, (int, float)):
                setattr(w, k, float(cur) + 0.1)
    save_weights(w)
    return w
