from __future__ import annotations

from typing import Dict, Tuple
import networkx as nx

from backend.models.scene import Building, Floor, Space


def _rects_touch_or_overlap(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    # Overlap or touching edges (inclusive)
    return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)


def build_room_adjacency(floor: Floor) -> nx.Graph:
    g = nx.Graph()
    for sp in floor.spaces:
        g.add_node(sp.id, name=sp.name)
    for i, a in enumerate(floor.spaces):
        for j in range(i + 1, len(floor.spaces)):
            b = floor.spaces[j]
            if _rects_touch_or_overlap(a.rect.bbox(), b.rect.bbox()):
                g.add_edge(a.id, b.id, kind="adjacent")
    return g


def build_circulation_graph(floor: Floor) -> nx.Graph:
    # MVP: reuse adjacency as a proxy for circulation; openings can refine later
    g = build_room_adjacency(floor)
    nx.set_edge_attributes(g, {e: {"kind": "circulation", "weight": 1.0} for e in g.edges})
    return g


def build_mep_graph(floor: Floor) -> nx.Graph:
    g = nx.Graph()
    wet_keywords = ("bath", "toilet", "wc", "kitchen", "laundry")
    wet_nodes = []
    for sp in floor.spaces:
        if any(k in sp.name.lower() for k in wet_keywords):
            wet_nodes.append(sp)
            g.add_node(sp.id, name=sp.name)
    # Fully connect wet spaces (later: connect to vertical stacks)
    for i, a in enumerate(wet_nodes):
        for j in range(i + 1, len(wet_nodes)):
            b = wet_nodes[j]
            g.add_edge(a.id, b.id, kind="wet_adj")
    return g


def build_graphs(building: Building) -> Dict[str, nx.Graph]:
    out: Dict[str, nx.Graph] = {}
    if not building.floors:
        return out
    # For MVP, single floor
    f = building.floors[0]
    out["room_adjacency"] = build_room_adjacency(f)
    out["circulation"] = build_circulation_graph(f)
    out["mep"] = build_mep_graph(f)
    return out
