# House Blueprint AI

Generate code-compliant, dimensioned floor plans from user parameters. MVP focuses on single-story layouts with CP-SAT + heuristics, basic code checks, and SVG/PDF/DXF export.

## Quick start
- Backend (FastAPI): see `backend/` and `pyproject.toml`
- Run dev API: `uvicorn backend.api.main:app --reload`

## Roadmap (high-level)
- MVP: parser → CP-SAT layout → validation → export (SVG/PDF/DXF) → lightweight editor
- Phase 2: multi-story, windows/daylight, stairs, fixtures, schedules, retrieval, critic
- Phase 3: IFC, accessibility, energy/daylight, style conditioning, RLHF
- Phase 4: site planning, elevations/sections, structural sizing, HVAC paths
