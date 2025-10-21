from __future__ import annotations

from typing import Dict, List

from backend.models.schema import Brief, LayoutResult, ValidationReport, MetricsReport
from backend.models.scene import Building


def _program_satisfaction(brief: Brief, layout: LayoutResult) -> float:
    req = len(brief.rooms)
    if req == 0:
        return 1.0
    placed_names = {r.name for r in layout.rooms}
    placed = sum(1 for s in brief.rooms if s.name in placed_names)
    return placed / req


def _corridor_ratio(building: Building) -> float:
    total = 0.0
    corridor = 0.0
    if not building.floors:
        return 0.0
    for sp in building.floors[0].spaces:
        a = sp.rect.w * sp.rect.h
        total += a
        if sp.name.lower() == "corridor":
            corridor += a
    return (corridor / total) if total > 0 else 0.0


def _compliance_pass(validation: ValidationReport) -> float:
    # 1.0 if no [error] violations, else 0.0
    if validation.compliant:
        return 1.0
    # parse errors
    errs = [v for v in validation.violations if v.startswith("[error]")]
    return 0.0 if errs else 1.0


def _violations_per_100m2(validation: ValidationReport, building: Building) -> float:
    # area in mm^2; 100 m^2 = 1e8 mm^2
    area = building.width * building.height
    factor = (area / 1e8) if area > 0 else 1.0
    return len(validation.violations) / factor


def _struct_alignment_score(analysis: Dict[str, object]) -> float:
    return float(analysis.get("alignment_score", 0.0))


def _mep_alignment_score(analysis: Dict[str, object], building: Building) -> float:
    avg_d = float(analysis.get("avg_distance", 0.0))
    norm = building.width + building.height
    if norm <= 0:
        return 0.0
    s = 1.0 - min(1.0, avg_d / norm)
    return s


def compute_metrics(brief: Brief, layout: LayoutResult, validation: ValidationReport, building: Building, structure_info: Dict[str, object], mep_info: Dict[str, object]) -> MetricsReport:
    return MetricsReport(
        program_satisfaction_pct=_program_satisfaction(brief, layout) * 100.0,
        corridor_ratio=_corridor_ratio(building),
        compliance_pass=_compliance_pass(validation),
        violations_per_100m2=_violations_per_100m2(validation, building),
        struct_alignment_score=_struct_alignment_score(structure_info),
        mep_alignment_score=_mep_alignment_score(mep_info, building),
    )
