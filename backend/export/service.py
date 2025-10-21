from __future__ import annotations

from typing import Dict, List
import json

from backend.models.scene import Building
from backend.export.svg import to_svg
from backend.export.dxf import to_dxf
from backend.export.ifc import to_ifc_interchange
from backend.export.schedules import build_schedules, schedules_to_csvs


import hashlib

def _hash_payloads(d: Dict[str, str]) -> Dict[str, str]:
    h = {}
    for k, v in d.items():
        h[k] = hashlib.sha256(v.encode('utf-8')).hexdigest()
    return h


def export_payloads(building: Building, formats: List[str], meta: Dict[str, str] | None = None) -> Dict[str, str]:
    """Return a dict mapping filename to textual payload for requested formats.
    Supported formats: svg, dxf, ifcjson, schedules_csv, scene_json.
    Includes a manifest.json with hashes and metadata for reproducibility.
    """
    out: Dict[str, str] = {}
    if "svg" in formats:
        out["plan.svg"] = to_svg(building)
    if "dxf" in formats:
        out["plan.dxf"] = to_dxf(building)
    if "ifcjson" in formats:
        out["model.ifc.json"] = json.dumps(to_ifc_interchange(building), indent=2)
    if "schedules_csv" in formats:
        sched = build_schedules(building)
        out.update(schedules_to_csvs(sched))
    if "scene_json" in formats:
        # Raw scene dump for downstream custom tools
        out["scene.json"] = building.model_dump_json(indent=2)
    # Manifest
    manifest = {
        "hashes": _hash_payloads(out),
        "meta": meta or {},
    }
    out["manifest.json"] = json.dumps(manifest, indent=2)
    return out
