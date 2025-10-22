from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from typing import Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.models.units import Rounding, UnitSystem


class Layer(str, Enum):
    ARCH = "arch"
    STRUCT = "struct"
    MEP = "mep"
    ANNO = "anno"  # annotations/dimensions


IFC_LAYER_MAP: Dict[Layer, str] = {
    Layer.ARCH: "IfcWall/IfcSpace/IfcDoor/IfcWindow",
    Layer.STRUCT: "IfcBeam/IfcColumn/IfcSlab",
    Layer.MEP: "IfcFlowSegment/IfcFlowTerminal",
    Layer.ANNO: "IfcAnnotation",
}

DWG_LAYER_MAP: Dict[Layer, str] = {
    Layer.ARCH: "A-*",
    Layer.STRUCT: "S-*",
    Layer.MEP: "M-*",
    Layer.ANNO: "G-ANNO",
}


class Point(BaseModel):
    x: float
    y: float


class Rect(BaseModel):
    x: float
    y: float
    w: float
    h: float

    def bbox(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.w, self.y + self.h)


class Node(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    typ: str
    layer: Layer = Layer.ARCH
    meta: Dict[str, str] = Field(default_factory=dict)


class OpeningType(str, Enum):
    DOOR = "door"
    WINDOW = "window"


class FixtureType(str, Enum):
    TOILET = "toilet"
    SINK = "sink"
    SHOWER = "shower"
    TUB = "tub"
    RANGE = "range"
    FRIDGE = "fridge"
    STAIRS = "stairs"
    RAMP = "ramp"


class Boundary(Node):
    typ: Literal["boundary"] = "boundary"
    a: Point
    b: Point
    thickness: float = 100.0


class Opening(Node):
    typ: Literal["opening"] = "opening"
    opening_type: OpeningType
    at: Point  # position along boundary or wall centerline
    w: float
    h: float


class Fixture(Node):
    typ: Literal["fixture"] = "fixture"
    fixture_type: FixtureType
    at: Point
    w: float = 0.0
    h: float = 0.0
    meta: Dict[str, str] = Field(default_factory=dict)


class Space(Node):
    typ: Literal["space"] = "space"
    name: str
    rect: Rect  # MVP: axis-aligned rectangle; can extend to polygons later
    boundaries: List[Boundary] = Field(default_factory=list)
    openings: List[Opening] = Field(default_factory=list)
    fixtures: List[Fixture] = Field(default_factory=list)


class Floor(Node):
    typ: Literal["floor"] = "floor"
    elevation: float = 0.0
    spaces: List[Space] = Field(default_factory=list)


class Building(Node):
    typ: Literal["building"] = "building"
    unit_system: UnitSystem = UnitSystem.METRIC_MM
    rounding: Rounding = Rounding.NEAREST_MM
    width: float
    height: float
    floors: List[Floor] = Field(default_factory=list)

    def ifc_layer_hint(self, layer: Layer) -> str:
        return IFC_LAYER_MAP.get(layer, "")

    def dwg_layer_hint(self, layer: Layer) -> str:
        return DWG_LAYER_MAP.get(layer, "")


# Adapters
from backend.models.schema import Brief, LayoutResult


def from_brief_and_layout(brief: Brief, layout: LayoutResult) -> Building:
    bldg = Building(unit_system=UnitSystem.METRIC_MM, width=brief.building_w, height=brief.building_h)
    def build_floor() -> Floor:
        floor = Floor(elevation=0.0)
        # First pass: create spaces and walls
        for r in layout.rooms:
            space = Space(name=r.name, rect=Rect(x=r.x, y=r.y, w=r.w, h=r.h))
            x0, y0, w, h = r.x, r.y, r.w, r.h
            pts = [Point(x=x0, y=y0), Point(x=x0 + w, y=y0), Point(x=x0 + w, y=y0 + h), Point(x=x0, y=y0 + h)]
            segs = [(pts[i], pts[(i + 1) % 4]) for i in range(4)]
            for a, b in segs:
                space.boundaries.append(Boundary(a=a, b=b))
            floor.spaces.append(space)
        # Second pass: add doors between meaningful adjacencies and windows on perimeter
        def bbox(sp):
            x, y, w, h = sp.rect.x, sp.rect.y, sp.rect.w, sp.rect.h
            return (x, y, x + w, y + h)
        def overlap_len(a0, a1, b0, b1):
            return max(0.0, min(a1, b1) - max(a0, b0))
        def is_private(name: str) -> bool:
            n = name.lower(); return n.startswith('bed') or n.startswith('bath')
        door_w = 90.0; door_h = 2000.0; min_ov = 60.0
        spaces = floor.spaces
        # adjacency doors
        for i in range(len(spaces)):
            for j in range(i + 1, len(spaces)):
                a = spaces[i]; b = spaces[j]
                ax0, ay0, ax1, ay1 = bbox(a); bx0, by0, bx1, by1 = bbox(b)
                # vertical shared edge
                if abs(ax1 - bx0) < 1e-6 or abs(bx1 - ax0) < 1e-6:
                    ov = overlap_len(ay0, ay1, by0, by1)
                    if ov >= min_ov:
                        # corridor-private or corridor-living
                        corridor_pair = (a.name.lower().startswith('corridor') or b.name.lower().startswith('corridor'))
                        if corridor_pair and (is_private(a.name) or is_private(b.name) or a.name.lower().startswith('living') or b.name.lower().startswith('living')):
                            y_mid = max(ay0, by0) + ov / 2.0
                            x_edge = ax1 if abs(ax1 - bx0) < 1e-6 else bx1
                            sp = a if a.name.lower().startswith('corridor') else b
                            sp.openings.append(Opening(opening_type=OpeningType.DOOR, at=Point(x=x_edge, y=y_mid), w=door_w, h=door_h))
                # horizontal shared edge
                if abs(ay1 - by0) < 1e-6 or abs(by1 - ay0) < 1e-6:
                    ov = overlap_len(ax0, ax1, bx0, bx1)
                    if ov >= min_ov:
                        # living–kitchen doorway if they meet
                        names = {a.name.lower(), b.name.lower()}
                        if 'living' in names and 'kitchen' in names:
                            x_mid = max(ax0, bx0) + ov / 2.0
                            y_edge = ay1 if abs(ay1 - by0) < 1e-6 else by1
                            a.openings.append(Opening(opening_type=OpeningType.DOOR, at=Point(x=x_mid, y=y_edge), w=door_w, h=door_h))
        # perimeter windows
        for sp in spaces:
            n = sp.name.lower()
            if n.startswith('bath'):
                continue
            x, y, w, h = sp.rect.x, sp.rect.y, sp.rect.w, sp.rect.h
            # top
            if abs(y - 0.0) < 1e-6:
                sp.openings.append(Opening(opening_type=OpeningType.WINDOW, at=Point(x=x + w/2, y=y), w=120.0, h=1200.0))
            # bottom
            if abs(y + h - bldg.height) < 1e-6:
                sp.openings.append(Opening(opening_type=OpeningType.WINDOW, at=Point(x=x + w/2, y=y + h), w=120.0, h=1200.0))
            # left
            if abs(x - 0.0) < 1e-6:
                sp.openings.append(Opening(opening_type=OpeningType.WINDOW, at=Point(x=x, y=y + h/2), w=120.0, h=1200.0))
            # right
            if abs(x + w - bldg.width) < 1e-6:
                sp.openings.append(Opening(opening_type=OpeningType.WINDOW, at=Point(x=x + w, y=y + h/2), w=120.0, h=1200.0))
        return floor
    floors = brief.building_floors if hasattr(brief, 'building_floors') else 1
    for i in range(floors):
        f = build_floor()
        f.elevation = i * 3000.0  # 3m floor-to-floor as placeholder
        bldg.floors.append(f)
    return bldg
