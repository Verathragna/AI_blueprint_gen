from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from backend.models.schema import Brief, LayoutResult, CostBreakdown, AnalysisReport, Pins, PinRoom
from backend.core.orchestrator import Orchestrator
from backend.solver.costs import evaluate_cost, aggregate_cost
from backend.models.scene import from_brief_and_layout
from backend.learned.critic import Critic
from backend.learned.proposal import propose_variants
from backend.learned.topology import propose_topologies
from backend.retrieval.library import retrieve_seed
from backend.solver.refine import refine_layout


class Candidate(BaseModel):
    layout: LayoutResult
    cost: CostBreakdown
    analysis: AnalysisReport
    summary: str


def _explain(brief: Brief, layout: LayoutResult) -> tuple[CostBreakdown, AnalysisReport, str]:
    orch = Orchestrator()
    scene = from_brief_and_layout(brief, layout)
    # reuse orchestrator scene passes: openings/stairs
    from backend.geometry.openings import apply_openings
    from backend.geometry.stairs import ensure_stairs
    from backend.analysis.structure import analyze_structure
    from backend.analysis.mep import analyze_mep
    from backend.analysis.facade import analyze_facade

    scene = apply_openings(scene)
    scene = ensure_stairs(scene)
    terms = evaluate_cost(scene, brief)
    total, weighted = aggregate_cost(terms, brief)
    cost = CostBreakdown(total=total, terms=weighted)
    analysis = AnalysisReport(structure=analyze_structure(scene), mep=analyze_mep(scene), facade=analyze_facade(scene))
    # simple summary: top 2 weighted terms
    top = sorted(weighted.items(), key=lambda kv: kv[1], reverse=True)[:2]
    parts = [f"{k}={v:.2f}" for k, v in top]
    summary = ", ".join(parts) if parts else "balanced"
    return cost, analysis, summary


def generate_candidates(brief: Brief | dict, k: int = 4) -> List[Candidate]:
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    orch = Orchestrator()
    brief_d = orch.rules.early_prune(brief).model_dump()
    # seed paths
    topo = propose_topologies(brief_d, k=2)
    seed = retrieve_seed(brief_d)
    base = orch.solver.solve(brief_d, seed.model_dump() if seed else None)
    base = LayoutResult(**base)
    if len(base.rooms) > 0:
        base = refine_layout(base, brief_d, iterations=2)
    candidates = topo + [base] + propose_variants(base, brief_d, k=max(0, k - 3))
    critic = Critic()
    scored = sorted(candidates, key=lambda L: critic.score(brief, L), reverse=True)[:k]
    out: List[Candidate] = []
    for c in scored:
        cost, analysis, summary = _explain(brief, c)
        out.append(Candidate(layout=c, cost=cost, analysis=analysis, summary=summary))
    return out


def apply_pins_and_optimize(brief: Brief | dict, layout: LayoutResult | dict, pins: Pins | dict) -> LayoutResult:
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(pins, Pins):
        pins = Pins(**pins)
    # lock pinned rooms; nudge others with refine only
    pinned = {p.name: p for p in pins.rooms}
    for r in layout.rooms:
        p = pinned.get(r.name)
        if p:
            if p.lock_position and p.x is not None and p.y is not None:
                r.x, r.y = p.x, p.y
            if p.lock_size and p.w is not None and p.h is not None:
                r.w, r.h = p.w, p.h
    # refine others
    refine_layout(layout, brief, iterations=2)
    # clamp to envelope
    for r in layout.rooms:
        r.x = max(0, min(r.x, brief.building_w - r.w))
        r.y = max(0, min(r.y, brief.building_h - r.h))
    return layout


def local_edit_move(layout: LayoutResult | dict, name: str, dx: int, dy: int, brief: Brief | dict) -> LayoutResult:
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    for r in layout.rooms:
        if r.name == name:
            r.x = max(0, min(r.x + dx, brief.building_w - r.w))
            r.y = max(0, min(r.y + dy, brief.building_h - r.h))
            break
    return layout


def local_edit_resize(layout: LayoutResult | dict, name: str, dw: int, dh: int, brief: Brief | dict) -> LayoutResult:
    if not isinstance(layout, LayoutResult):
        layout = LayoutResult(**layout)
    if not isinstance(brief, Brief):
        brief = Brief(**brief)
    for r in layout.rooms:
        if r.name == name:
            r.w = max(1, min(r.w + dw, brief.building_w - r.x))
            r.h = max(1, min(r.h + dh, brief.building_h - r.y))
            break
    return layout
