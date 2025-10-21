from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

from backend.models.schema import Brief, LayoutResponse, LayoutResult, Pins
from backend.core.orchestrator import Orchestrator
from backend.interaction.service import generate_candidates, apply_pins_and_optimize, Candidate, local_edit_move, local_edit_resize
from backend.interaction.prefs import update_from_choice, load_weights
from backend.qa.human_eval import record_rating, record_pairwise

app = FastAPI(title="House Blueprint AI", version="0.1.0")
orch = Orchestrator()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/layout", response_model=LayoutResponse)
def generate_layout(brief: Brief):
    return orch.run(brief.model_dump())


class CandidatesRequest(BaseModel):
    brief: Brief
    k: int = 4


@app.post("/candidates", response_model=List[Candidate])
def list_candidates(req: CandidatesRequest):
    return generate_candidates(req.brief, k=req.k)


class OptimizeWithPinsRequest(BaseModel):
    brief: Brief
    layout: LayoutResult
    pins: Pins


@app.post("/optimize", response_model=LayoutResult)
def optimize_with_pins(req: OptimizeWithPinsRequest):
    return apply_pins_and_optimize(req.brief, req.layout, req.pins)


class MoveOp(BaseModel):
    name: str
    dx: int
    dy: int


class ResizeOp(BaseModel):
    name: str
    dw: int
    dh: int


class EditRequest(BaseModel):
    brief: Brief
    layout: LayoutResult
    move: Optional[MoveOp] = None
    resize: Optional[ResizeOp] = None


@app.post("/edit", response_model=LayoutResult)
def apply_edit(req: EditRequest):
    layout = req.layout
    if req.move:
        layout = local_edit_move(layout, req.move.name, req.move.dx, req.move.dy, req.brief)
    if req.resize:
        layout = local_edit_resize(layout, req.resize.name, req.resize.dw, req.resize.dh, req.brief)
    return layout


class ExportRequest(BaseModel):
    brief: Brief
    layout: LayoutResult
    formats: List[str] = ["svg", "dxf", "ifcjson", "schedules_csv", "scene_json"]


@app.post("/export")
def export_payload(req: ExportRequest):
    return orch.export(req.brief, req.layout, req.formats)


class RatingRequest(BaseModel):
    brief: Brief
    layout: LayoutResult
    ratings: dict


@app.post("/eval/rate")
def eval_rate(req: RatingRequest):
    record_rating(req.brief, req.layout, req.ratings)
    return {"status": "ok"}


class PairwiseRequest(BaseModel):
    brief: Brief
    layouts: List[LayoutResult]
    chosen_index: int
    criteria: str = "overall"


@app.post("/eval/compare")
def eval_compare(req: PairwiseRequest):
    record_pairwise(req.brief, req.layouts, req.chosen_index, req.criteria)
    return {"status": "ok"}


class PrefsUpdateRequest(BaseModel):
    chosen_terms: dict
    others_terms: List[dict]


@app.post("/preferences/update")
def prefs_update(req: PrefsUpdateRequest):
    w = update_from_choice(req.chosen_terms, req.others_terms)
    return w


@app.get("/preferences/weights")
def prefs_get():
    return load_weights()
