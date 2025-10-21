from __future__ import annotations

from typing import List, Tuple, Optional
import heapq

Grid = List[List[int]]  # 0=free, 1=blocked


def astar(grid: Grid, start: Tuple[int, int], goal: Tuple[int, int]) -> Optional[List[Tuple[int, int]]]:
    w, h = len(grid[0]), len(grid)
    sx, sy = start
    gx, gy = goal
    def inb(x, y):
        return 0 <= x < w and 0 <= y < h
    def hcost(x, y):
        return abs(x - gx) + abs(y - gy)

    openh = [(hcost(sx, sy), 0, (sx, sy), None)]
    came = {}
    gscore = { (sx, sy): 0 }
    visited = set()
    while openh:
        f, g, (x, y), parent = heapq.heappop(openh)
        if (x, y) in visited:
            continue
        visited.add((x, y))
        came[(x, y)] = parent
        if (x, y) == (gx, gy):
            # reconstruct
            path = []
            cur = (x, y)
            while cur is not None:
                path.append(cur)
                cur = came[cur]
            return list(reversed(path))
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if not inb(nx, ny) or grid[ny][nx] == 1:
                continue
            ng = g + 1
            if ng < gscore.get((nx, ny), 1e9):
                gscore[(nx, ny)] = ng
                heapq.heappush(openh, (ng + hcost(nx, ny), ng, (nx, ny), (x, y)))
    return None
