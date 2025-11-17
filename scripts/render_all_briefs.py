from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.orchestrator import Orchestrator  # noqa: E402


def iter_briefs(briefs_dir: Path) -> Iterable[Path]:
    for path in sorted(briefs_dir.glob("*.json")):
        if path.name.startswith("_"):
            continue
        yield path


def render_brief(orch: Orchestrator, brief_path: Path, formats: List[str], out_root: Path) -> None:
    data = json.loads(brief_path.read_text())
    response = orch.run(data)
    exports = orch.export(data, response.layout, formats)

    brief_dir = out_root / brief_path.stem
    brief_dir.mkdir(parents=True, exist_ok=True)

    for name, payload in exports.items():
        target = brief_dir / name
        target.write_text(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate blueprint exports for all briefs.")
    parser.add_argument(
        "--briefs-dir",
        type=Path,
        default=Path("briefs"),
        help="Directory containing brief JSON files.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("exports"),
        help="Directory where outputs will be written.",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["svg"],
        help="Export formats to request (e.g. svg dxf scene_json).",
    )
    args = parser.parse_args()

    briefs_dir = args.briefs_dir.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    orch = Orchestrator()
    rendered = 0
    for brief_path in iter_briefs(briefs_dir):
        render_brief(orch, brief_path, args.formats, out_dir)
        rendered += 1
        print(f"[ok] {brief_path.name} -> {out_dir / brief_path.stem}")

    if rendered == 0:
        print(f"No briefs found in {briefs_dir}")
    else:
        print(f"Rendered {rendered} briefs into {out_dir}")


if __name__ == "__main__":
    main()
