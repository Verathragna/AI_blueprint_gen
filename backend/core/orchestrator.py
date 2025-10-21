from typing import Any, Dict
import random
from uuid import uuid4

from backend.models.schema import Brief, LayoutResponse, LayoutResult, CostBreakdown, AnalysisReport, GovernanceReport
from backend.rules.engine import RulesEngine
from backend.solver.solver import LayoutSolver
from backend.models.scene import from_brief_and_layout
from backend.solver.costs import evaluate_cost, aggregate_cost
from backend.retrieval.library import retrieve_seed
from backend.solver.refine import refine_layout
from backend.learned.proposal import propose_variants
from backend.learned.critic import Critic
from backend.learned.topology import propose_topologies
from backend.learned.parser import parse_requirements_text
from backend.learned.placement import apply_learned_placements
from backend.geometry.openings import apply_openings
from backend.geometry.stairs import ensure_stairs
from backend.analysis.structure import analyze_structure
from backend.analysis.mep import analyze_mep
from backend.analysis.facade import analyze_facade
from backend.qa.metrics import compute_metrics
from backend.models.schema import ValidationReport
from backend.rules.loader import load_rules


class Orchestrator:
    """
    Coordinates parsing requirements, generation (solver + heuristics), validation, and export.
    """

    def __init__(self) -> None:
        self.solver = LayoutSolver()
        self.rules = RulesEngine()

    def parse_requirements(self, raw_text: str) -> Dict[str, Any]:
        # LLM-ready stub: parse text into a Brief
        brief = parse_requirements_text(raw_text)
        return brief.model_dump()

    def generate_layout(self, brief: Dict[str, Any]) -> LayoutResult:
        layout_dict = self.solver.solve(brief)
        return LayoutResult(**layout_dict)

    def validate(self, layout: LayoutResult, brief: Dict[str, Any] | Brief | None = None) -> Dict[str, Any]:
        return self.rules.check(layout, brief)

    def run(self, brief: Dict[str, Any]) -> LayoutResponse:
        # Early pruning of brief against absolute minimums
        brief = self.rules.early_prune(brief)
        # Seed and run id for reproducibility
        brief_obj = Brief(**brief) if not isinstance(brief, Brief) else brief
        if brief_obj.seed is not None:
            random.seed(brief_obj.seed)
        run_id = str(uuid4())
        # Stage 0: learned topology proposals
        topo_candidates = propose_topologies(brief, k=2)
        # Stage 1: retrieval seed
        seed = retrieve_seed(brief)
        # Stage 2: base layout (constraint-based placeholder + heuristic)
        base_layout = self.solver.solve(brief, seed.model_dump() if seed else None)
        base_layout = LayoutResult(**base_layout)
        # Stage 3: heuristic refinement
        if len(base_layout.rooms) > 0:
            base_layout = refine_layout(base_layout, brief, iterations=2)
        # Stage 4: learned proposal/critic loop: combine candidates (topology + refined + jitters)
        candidates = topo_candidates + [base_layout] + propose_variants(base_layout, brief, k=3)
        # Mid-pipeline rule filtering: discard candidates with fatal errors
        filtered = []
        for cand in candidates:
            rep = self.rules.check(cand, brief)
            fatals = [v for v in rep["violations"] if v.startswith("[error]")]
            if not fatals:
                filtered.append(cand)
        if filtered:
            candidates = filtered
        # brief_obj already defined above
        critic = Critic()
        best = max(candidates, key=lambda L: critic.score(brief_obj, L))
        layout = LayoutResult(**best.model_dump())

        validation = self.validate(layout, brief)
        # Final compliance report already includes scene-level declarative rules
        # Build scene and evaluate soft cost
        scene = from_brief_and_layout(brief_obj, layout)
        # Learned placement -> rules finalize, then stairs
        scene = apply_learned_placements(scene)
        scene = apply_openings(scene)
        scene = ensure_stairs(scene)
        terms = evaluate_cost(scene, brief_obj)
        total, weighted = aggregate_cost(terms, brief_obj)
        cost = CostBreakdown(total=total, terms=weighted)
        # Structural/MEP/Facade heuristics
        structure_info = analyze_structure(scene)
        mep_info = analyze_mep(scene)
        facade_info = analyze_facade(scene)
        analysis = AnalysisReport(structure=structure_info, mep=mep_info, facade=facade_info)
        metrics = compute_metrics(brief_obj, layout, ValidationReport(**validation) if isinstance(validation, dict) else validation, scene, structure_info, mep_info)
        applied_rules = [r.get('id','') for r in load_rules(None)]
        governance = GovernanceReport(run_id=run_id, seed=brief_obj.seed, tenant_id=brief_obj.tenant_id, consent_external=brief_obj.consent_external, rule_ids=applied_rules)
        return LayoutResponse(layout=layout, validation=validation, cost=cost, analysis=analysis, metrics=metrics, governance=governance)

    def export(self, brief: Dict[str, Any] | Brief, layout: Dict[str, Any] | LayoutResult, formats: list[str] | None = None) -> Dict[str, str]:
        if not isinstance(brief, Brief):
            brief = Brief(**brief)
        if not isinstance(layout, LayoutResult):
            layout = LayoutResult(**layout)
        scene = from_brief_and_layout(brief, layout)
        from backend.export.service import export_payloads
        meta = {"tenant_id": brief.tenant_id or "", "seed": str(brief.seed) if brief.seed is not None else ""}
        return export_payloads(scene, formats or ["svg", "dxf", "ifcjson", "schedules_csv", "scene_json"], meta=meta)
