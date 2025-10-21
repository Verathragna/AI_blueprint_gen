from __future__ import annotations

from typing import Callable, Iterable, List
import math

from backend.datasets.schema import DatasetSample, DatasetFloor, DatasetRoom, PolyPoint, Polygon


def _transform_points(points: List[PolyPoint], f: Callable[[float, float], tuple[float, float]]) -> List[PolyPoint]:
    return [PolyPoint(x=nx, y=ny) for (nx, ny) in (f(p.x, p.y) for p in points)]


def mirror_horizontal(sample: DatasetSample) -> DatasetSample:
    W = sample.width
    def f(x, y):
        return (W - x, y)
    for fl in sample.floors:
        for r in fl.rooms:
            r.polygon.points = _transform_points(r.polygon.points, f)
            for op in r.openings:
                op.polygon.points = _transform_points(op.polygon.points, f)
            for fx in r.fixtures:
                fx.at = PolyPoint(x=W - fx.at.x, y=fx.at.y)
    return sample


def rotate_90(sample: DatasetSample) -> DatasetSample:
    W, H = sample.width, sample.height
    def f(x, y):
        # rotate about origin then translate to keep positive coords
        return (H - y, x)
    for fl in sample.floors:
        for r in fl.rooms:
            r.polygon.points = _transform_points(r.polygon.points, f)
            for op in r.openings:
                op.polygon.points = _transform_points(op.polygon.points, f)
            for fx in r.fixtures:
                fx.at = PolyPoint(x=H - fx.at.y, y=fx.at.x)
    sample.width, sample.height = H, W
    return sample


def scale_uniform(sample: DatasetSample, s: float, max_width: float | None = None, max_height: float | None = None) -> DatasetSample:
    def f(x, y):
        return (x * s, y * s)
    for fl in sample.floors:
        for r in fl.rooms:
            r.polygon.points = _transform_points(r.polygon.points, f)
            for op in r.openings:
                op.polygon.points = _transform_points(op.polygon.points, f)
            for fx in r.fixtures:
                fx.at = PolyPoint(x=fx.at.x * s, y=fx.at.y * s)
                fx.w *= s
                fx.h *= s
    sample.width *= s
    sample.height *= s
    if max_width and sample.width > max_width:
        k = max_width / sample.width
        return scale_uniform(sample, k, max_width, max_height)
    if max_height and sample.height > max_height:
        k = max_height / sample.height
        return scale_uniform(sample, k, max_width, max_height)
    return sample


def add_style_tag(sample: DatasetSample, tag: str) -> DatasetSample:
    sample.meta["style"] = tag
    return sample
