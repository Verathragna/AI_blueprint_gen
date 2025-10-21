from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from backend.rules.catalog import DEFAULT_RULES


def load_rules(paths: List[str] | None = None) -> List[Dict[str, Any]]:
    """Load rules from JSON files if provided; otherwise return DEFAULT_RULES.
    JSON format: array of objects compatible with DEFAULT_RULES entries.
    """
    if not paths:
        return list(DEFAULT_RULES)
    out: List[Dict[str, Any]] = []
    for p in paths:
        path = Path(p)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
                if isinstance(data, list):
                    out.extend([x for x in data if isinstance(x, dict)])
            except Exception:
                continue
    return out or list(DEFAULT_RULES)
