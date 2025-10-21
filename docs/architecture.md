# Architecture overview

This project implements a modular, hybrid pipeline to convert requirements into code-compliant floor plans.

- Orchestrator: coordinates parsing → generation → validation → export
- Design engine: CP-SAT layout + heuristics (see `backend/solver/`)
- Validators: rules engine and geometric checks (see `backend/rules/`)
- API: FastAPI endpoints for orchestration (see `backend/api/`)
- Data/DSL: to be defined (scene graph, adjacency graphs, constraints)
- Exports: IFC/DXF/SVG/PDF (future)

MVP focus: single-story layout, core code checks, and simple exports.
