from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field, PositiveInt


# ----- Program / Room specs -----
class RoomSpec(BaseModel):
    name: str = Field(..., description="Programmatic room name, e.g., 'bedroom', 'kitchen'")
    min_w: PositiveInt = Field(..., description="Minimum room width in units (e.g., mm)")
    min_h: PositiveInt = Field(..., description="Minimum room height in units (e.g., mm)")
    target_area: Optional[PositiveInt] = Field(
        None, description="Desired room area in square units; heuristic uses when provided"
    )


# ----- Constraints (hard) -----
class RoomAreaConstraint(BaseModel):
    name: str
    min_area: Optional[PositiveInt] = None
    max_area: Optional[PositiveInt] = None


class HardConstraints(BaseModel):
    room_areas: List[RoomAreaConstraint] = Field(
        default_factory=list, description="Per-room hard area bounds"
    )
    # Placeholders for future hard constraints (not enforced yet in MVP)
    min_corridor_width: Optional[PositiveInt] = None
    setbacks: Optional[Dict[str, PositiveInt]] = None  # {north,south,east,west}
    lot_coverage_max_pct: Optional[float] = None


# ----- Objectives (soft) -----
class AdjacencyPreference(BaseModel):
    a: str
    b: str


class SoftObjectives(BaseModel):
    adjacency: List[AdjacencyPreference] = Field(default_factory=list)
    # Privacy: bedrooms not adjacent to noisy spaces (living/kitchen)
    enforce_privacy: bool = True
    # Aspect ratio target (penalize tall/skinny)
    aspect_ratio_target: float = 1.5
    aspect_ratio_tolerance: float = 0.5  # acceptable +/- range


class SoftWeights(BaseModel):
    adjacency_missing: float = 1.0
    bedroom_privacy: float = 1.0
    aspect_ratio_deviation: float = 0.5
    area_target_deviation: float = 0.2
    hub_distance: float = 0.3


class Brief(BaseModel):
    building_w: PositiveInt = Field(..., description="Envelope width in units")
    building_h: PositiveInt = Field(..., description="Envelope height in units")
    building_floors: PositiveInt = Field(1, description="Number of floors (MVP: replicated)")
    rooms: List[RoomSpec] = Field(default_factory=list)
    # Back-compat simple tuple list; prefer soft.adjacency
    adjacency_preferences: List[Tuple[str, str]] = Field(default_factory=list)
    hard: Optional[HardConstraints] = None
    soft: Optional[SoftObjectives] = None
    weights: Optional[SoftWeights] = None
    # Security/governance
    tenant_id: Optional[str] = None
    consent_external: bool = False
    seed: Optional[int] = None


# ----- Layout and responses -----
class PlacedRoom(BaseModel):
    name: str
    x: int
    y: int
    w: int
    h: int

    @property
    def area(self) -> int:
        return self.w * self.h


class LayoutResult(BaseModel):
    rooms: List[PlacedRoom]
    dropped: List[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    compliant: bool
    violations: List[str] = Field(default_factory=list)


class CostBreakdown(BaseModel):
    total: float
    terms: Dict[str, float] = Field(default_factory=dict)


# ----- Interaction -----
class PinRoom(BaseModel):
    name: str
    lock_position: bool = True
    lock_size: bool = True
    x: Optional[int] = None
    y: Optional[int] = None
    w: Optional[int] = None
    h: Optional[int] = None


class Pins(BaseModel):
    rooms: List[PinRoom] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    structure: Dict[str, Any] = Field(default_factory=dict)
    mep: Dict[str, Any] = Field(default_factory=dict)
    facade: Dict[str, Any] = Field(default_factory=dict)


class GovernanceReport(BaseModel):
    run_id: str
    seed: Optional[int] = None
    tenant_id: Optional[str] = None
    consent_external: bool = False
    rule_ids: List[str] = Field(default_factory=list)


class MetricsReport(BaseModel):
    program_satisfaction_pct: float
    corridor_ratio: float
    compliance_pass: float
    violations_per_100m2: float
    struct_alignment_score: float
    mep_alignment_score: float


class LayoutResponse(BaseModel):
    layout: LayoutResult
    validation: ValidationReport
    cost: Optional[CostBreakdown] = None
    analysis: Optional[AnalysisReport] = None
    metrics: Optional[MetricsReport] = None
    governance: Optional[GovernanceReport] = None
