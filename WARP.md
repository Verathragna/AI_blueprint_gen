# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Commands

- Install dependencies (from pyproject):
```bash path=null start=null
python -m pip install --upgrade pip
pip install fastapi uvicorn[standard] pydantic networkx shapely ortools black isort
```

- Run the dev API (auto-reload):
```bash path=null start=null
python -m uvicorn backend.api.main:app --reload
# health check
curl http://127.0.0.1:8000/health
```

- Format (write changes):
```bash path=null start=null
python -m black .
python -m isort .
```

- Lint-style (no changes, CI-friendly):
```bash path=null start=null
python -m black --check --diff .
python -m isort --check-only --diff .
```

- Tests:
```bash path=null start=null
# No test suite configured yet.
```

## Architecture and code structure

High-level pipeline (see also `docs/architecture.md` and `README.md`):
- Orchestrator (`backend/core/orchestrator.py`): entry point that coordinates parse → generate → validate → export. Methods: `parse_requirements(raw_text)`, `generate_layout(brief)`, `validate(layout)`, `export(layout)`.
- Design engine (`backend/solver/solver.py`): CP-SAT scaffold using OR-Tools. `LayoutSolver.solve(brief)` builds a model (stubbed if OR-Tools missing). Future: variables/constraints for rooms, adjacencies, egress, etc.
- Rules/validation (`backend/rules/engine.py`): placeholder `RulesEngine.check(layout)` to apply code-compliance checks (IRC/IBC/ADA) and geometry queries; returns `compliant` and `violations`.
- API (`backend/api/main.py`): FastAPI app exposing endpoints (currently `/health`). Intended to orchestrate end-to-end flow in future.
- Data/DSL: to be defined (scene graph, adjacency graphs, constraints). Exports (IFC/DXF/SVG/PDF) planned in `orchestrator.export`.

MVP scope (per README): single-story layout, core code checks, basic SVG/PDF/DXF export; later phases extend to multi-story, accessibility, energy/daylight, and more.

## Repository notes

- Python 3.10+ (per `pyproject.toml`).
- Code style tools configured via `pyproject.toml`: Black (line-length 100) and isort (profile "black").
- Frontend/`docs/` folders exist; frontend is currently empty; `docs/architecture.md` summarizes the big picture.
