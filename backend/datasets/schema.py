from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.models.scene import Building, Floor, Space, OpeningType
from backend.models.graphs import build_graphs


class PolyPoint(BaseModel):
    x: float
    y: float


class Polygon(BaseModel):
    points: List[PolyPoint]


class DatasetOpening(BaseModel):
    opening_type: str
    polygon: Polygon


class DatasetFixture(BaseModel):
    fixture_type: str
    at: PolyPoint
    w: float
    h: float


class DatasetRoom(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    polygon: Polygon
    openings: List[DatasetOpening] = Field(default_factory=list)
    fixtures: List[DatasetFixture] = Field(default_factory=list)


class DatasetFloor(BaseModel):
    elevation: float
    rooms: List[DatasetRoom] = Field(default_factory=list)


class GraphEdge(BaseModel):
    a: str
    b: str
    kind: str


class ComplianceAttributes(BaseModel):
    flags: Dict[str, bool] = Field(default_factory=dict)


class Ratings(BaseModel):
    aesthetics: Optional[float] = None
    usability: Optional[float] = None
    daylight: Optional[float] = None


class DatasetSample(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    width: float
    height: float
    unit: str = "mm"
    floors: List[DatasetFloor]
    program: Dict[str, int] = Field(default_factory=dict)
    graphs: List[GraphEdge] = Field(default_factory=list)
    compliance: ComplianceAttributes = Field(default_factory=ComplianceAttributes)
    ratings: Ratings = Field(default_factory=Ratings)
    meta: Dict[str, str] = Field(default_factory=dict)


def _rect_to_polygon(x: float, y: float, w: float, h: float) -> Polygon:
    pts = [
        PolyPoint(x=x, y=y),
        PolyPoint(x=x + w, y=y),
        PolyPoint(x=x + w, y=y + h),
        PolyPoint(x=x, y=y + h),
    ]
    return Polygon(points=pts)


def sample_from_building(building: Building) -> DatasetSample:
    floors: List[DatasetFloor] = []
    for f in building.floors:
        rooms: List[DatasetRoom] = []
        for sp in f.spaces:
            room = DatasetRoom(name=sp.name, polygon=_rect_to_polygon(sp.rect.x, sp.rect.y, sp.rect.w, sp.rect.h))
            for op in sp.openings:
                poly = _rect_to_polygon(op.at.x - op.w / 2, op.at.y - op.h / 2, op.w, op.h)
                room.openings.append(DatasetOpening(opening_type=op.opening_type.value, polygon=poly))
            for fx in sp.fixtures:
                room.fixtures.append(DatasetFixture(fixture_type=fx.fixture_type.value, at=PolyPoint(x=fx.at.x, y=fx.at.y), w=fx.w, h=fx.h))
            rooms.append(room)
        floors.append(DatasetFloor(elevation=f.elevation, rooms=rooms))

    # Graphs (use first floor adjacency)
    graphs = []
    gdict = build_graphs(building)
    for kind, G in gdict.items():
        for (a, b) in G.edges:
            graphs.append(GraphEdge(a=a, b=b, kind=kind))

    # Program counts
    prog: Dict[str, int] = {}
    if building.floors:
        for sp in building.floors[0].spaces:
            key = sp.name.lower().split("_")[0]
            prog[key] = prog.get(key, 0) + 1

    return DatasetSample(width=building.width, height=building.height, floors=floors, graphs=graphs, program=prog)
