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
        for r in layout.rooms:
            space = Space(name=r.name, rect=Rect(x=r.x, y=r.y, w=r.w, h=r.h))
            # Boundaries as four walls for rectangle rooms (MVP)
            x0, y0, w, h = r.x, r.y, r.w, r.h
            pts = [Point(x=x0, y=y0), Point(x=x0 + w, y=y0), Point(x=x0 + w, y=y0 + h), Point(x=x0, y=y0 + h)]
            segs = [(pts[i], pts[(i + 1) % 4]) for i in range(4)]
            for a, b in segs:
                space.boundaries.append(Boundary(a=a, b=b))
            floor.spaces.append(space)
        return floor
    floors = brief.building_floors if hasattr(brief, 'building_floors') else 1
    for i in range(floors):
        f = build_floor()
        f.elevation = i * 3000.0  # 3m floor-to-floor as placeholder
        bldg.floors.append(f)
    return bldg
