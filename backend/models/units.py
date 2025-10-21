from __future__ import annotations

from enum import Enum
from typing import Literal

MM_PER_INCH = 25.4


class UnitSystem(str, Enum):
    METRIC_MM = "metric_mm"  # internal base unit
    IMPERIAL_INCH = "imperial_inch"


class Rounding(str, Enum):
    NONE = "none"
    NEAREST_MM = "nearest_mm"
    FIVE_MM = "5mm"
    QUARTER_INCH = "1/4in"
    HALF_INCH = "1/2in"


def to_mm(value: float, unit: UnitSystem) -> float:
    if unit == UnitSystem.METRIC_MM:
        return float(value)
    if unit == UnitSystem.IMPERIAL_INCH:
        return float(value) * MM_PER_INCH
    raise ValueError(f"Unknown unit {unit}")


def from_mm(mm: float, unit: UnitSystem) -> float:
    if unit == UnitSystem.METRIC_MM:
        return float(mm)
    if unit == UnitSystem.IMPERIAL_INCH:
        return float(mm) / MM_PER_INCH
    raise ValueError(f"Unknown unit {unit}")


def round_value(value: float, rounding: Rounding, unit: UnitSystem) -> float:
    if rounding == Rounding.NONE:
        return value

    if unit == UnitSystem.METRIC_MM:
        if rounding == Rounding.NEAREST_MM:
            step = 1.0
        elif rounding == Rounding.FIVE_MM:
            step = 5.0
        else:
            # imperial rounding applied after conversion
            value_in = from_mm(value, UnitSystem.IMPERIAL_INCH)
            return from_mm(round_value(value_in, rounding, UnitSystem.IMPERIAL_INCH), UnitSystem.IMPERIAL_INCH)
        return round(value / step) * step

    if unit == UnitSystem.IMPERIAL_INCH:
        if rounding == Rounding.QUARTER_INCH:
            step = 0.25
        elif rounding == Rounding.HALF_INCH:
            step = 0.5
        else:
            # metric rounding applied after conversion
            value_mm = to_mm(value, UnitSystem.IMPERIAL_INCH)
            return from_mm(round_value(value_mm, rounding, UnitSystem.METRIC_MM), UnitSystem.IMPERIAL_INCH)
        return round(value / step) * step

    return value
