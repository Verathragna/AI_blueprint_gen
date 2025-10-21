from __future__ import annotations

from typing import Dict, List
import csv
import io

from backend.models.scene import Building


def build_schedules(building: Building) -> Dict[str, List[Dict[str, object]]]:
    rooms: List[Dict[str, object]] = []
    doors: List[Dict[str, object]] = []
    windows: List[Dict[str, object]] = []
    for fi, floor in enumerate(building.floors):
        for sp in floor.spaces:
            rooms.append({
                "id": sp.id,
                "name": sp.name,
                "floor_elev": floor.elevation,
                "x": sp.rect.x,
                "y": sp.rect.y,
                "w": sp.rect.w,
                "h": sp.rect.h,
                "area": sp.rect.w * sp.rect.h,
            })
            for op in sp.openings:
                row = {
                    "id": op.id,
                    "room_id": sp.id,
                    "room": sp.name,
                    "x": op.at.x,
                    "y": op.at.y,
                    "w": op.w,
                    "h": op.h,
                }
                if op.opening_type.name == "DOOR":
                    doors.append(row)
                else:
                    windows.append(row)
    return {"rooms": rooms, "doors": doors, "windows": windows}


def schedules_to_csvs(sched: Dict[str, List[Dict[str, object]]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, rows in sched.items():
        buf = io.StringIO()
        if not rows:
            out[key + ".csv"] = ""
            continue
        writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
        out[key + ".csv"] = buf.getvalue()
    return out