from __future__ import annotations

from typing import List

from backend.datasets.schema import DatasetSample

# Stubs for public dataset importers. Implementations should map external schemas into DatasetSample.

def import_rplan(path: str) -> List[DatasetSample]:
    # TODO: parse RPLAN format and convert to DatasetSample
    return []


def import_cubiccasa5k(path: str) -> List[DatasetSample]:
    # TODO: parse CubiCasa5k and convert
    return []


def import_structured3d(path: str) -> List[DatasetSample]:
    # TODO: parse Structured3D and convert
    return []


def import_lifull(path: str) -> List[DatasetSample]:
    # TODO: parse LIFULL Home's dataset and convert
    return []
