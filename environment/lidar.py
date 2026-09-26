"""Track-boundary raycasting primitives independent of Trackmania."""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np

@dataclass(frozen=True)
class Segment:
    ax: float; ay: float; bx: float; by: float

@dataclass(frozen=True)
class RayHit:
    distance: float
    x: float
    y: float
    hit: bool

def ray_segment_intersection(origin, direction, segment: Segment, max_distance: float) -> RayHit:
    ox, oy = float(origin[0]), float(origin[1])
    dx, dy = float(direction[0]), float(direction[1])
    sx, sy = segment.bx - segment.ax, segment.by - segment.ay
    denom = dx * sy - dy * sx
    if abs(denom) < 1e-9:
        return RayHit(max_distance, ox + dx * max_distance, oy + dy * max_distance, False)
    qx, qy = segment.ax - ox, segment.ay - oy
    t = (qx * sy - qy * sx) / denom
    u = (qx * dy - qy * dx) / denom
    if t >= 0.0 and 0.0 <= u <= 1.0 and t <= max_distance:
        return RayHit(t, ox + dx * t, oy + dy * t, True)
    return RayHit(max_distance, ox + dx * max_distance, oy + dy * max_distance, False)

def cast_ray(origin, angle_radians, boundaries, max_distance=100.0) -> RayHit:
    d = (math.cos(angle_radians), math.sin(angle_radians))
    best = RayHit(max_distance, origin[0] + d[0]*max_distance, origin[1] + d[1]*max_distance, False)
    for seg in boundaries:
        hit = ray_segment_intersection(origin, d, seg, max_distance)
        if hit.distance < best.distance:
            best = hit
    return best

def three_rays(position, yaw, boundaries, max_distance=100.0):
    angles = (yaw + math.pi/2, yaw - math.pi/2, yaw)
    return tuple(cast_ray(position, a, boundaries, max_distance) for a in angles)

def normalized_three_rays(position, yaw, boundaries, max_distance=100.0):
    return np.asarray([h.distance / max_distance for h in three_rays(position, yaw, boundaries, max_distance)], dtype=np.float32)
