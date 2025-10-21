from __future__ import annotations

import json
from pathlib import Path
from typing import Dict
from datetime import datetime

from backend.models.schema import Brief, LayoutResult

EVAL_LOG = Path(__file__).parent / "human_eval.jsonl"
EVAL_LOG.parent.mkdir(parents=True, exist_ok=True)


def record_rating(brief: Brief | dict, layout: LayoutResult | dict, ratings: Dict[str, float]) -> None:
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    rec = {
        "ts": datetime.utcnow().isoformat(),
        "brief": brief.model_dump(),
        "layout": layout.model_dump(),
        "ratings": ratings,
    }
    with open(EVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


def record_pairwise(brief: Brief | dict, layouts: list[LayoutResult | dict], chosen_index: int, criteria: str = "overall") -> None:
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    ls = [l.model_dump() if isinstance(l, LayoutResult) else LayoutResult(**l).model_dump() for l in layouts]
    rec = {
        "ts": datetime.utcnow().isoformat(),
        "brief": brief.model_dump(),
        "layouts": ls,
        "chosen": chosen_index,
        "criteria": criteria,
    }
    with open(EVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
