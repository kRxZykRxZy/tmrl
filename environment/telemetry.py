"""Strict wire-format telemetry parsing and normalization."""
from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np

@dataclass
class Telemetry:
    agent_id: int
    position: tuple[float, float, float]
    velocity: tuple[float, float, float]
    pitch: float
    roll: float
    yaw: float
    checkpoint_time: float
    lidar_left: float
    lidar_right: float
    lidar_front: float
    alive: bool = True
    elapsed: float = 0.0
    distance: float = 0.0
    wall_penalty: float = 0.0

    @property
    def speed(self) -> float:
        return math.sqrt(sum(v*v for v in self.velocity))

    def observation(self, speed_limit=100.0, position_scale=100.0):
        x, y, z = self.position
        return np.asarray([
            np.clip(self.speed / speed_limit, 0.0, 1.0),
            np.clip(x / position_scale, -1.0, 1.0),
            np.clip(y / position_scale, -1.0, 1.0),
            np.clip(z / position_scale, -1.0, 1.0),
            np.clip(self.yaw / math.pi, -1.0, 1.0),
            np.clip(self.lidar_left, 0.0, 1.0),
            np.clip(self.lidar_right, 0.0, 1.0),
            np.clip(self.lidar_front, 0.0, 1.0)
        ], dtype=np.float32)

def parse_agent(obj: dict) -> Telemetry:
    def vec3(key):
        v = obj.get(key, [0.0, 0.0, 0.0])
        if not isinstance(v, (list, tuple)) or len(v) != 3:
            raise ValueError(f"{key} must be a 3-vector")
        return tuple(float(i) for i in v)
    return Telemetry(
        agent_id=int(obj["id"]),
        position=vec3("position"),
        velocity=vec3("velocity"),
        pitch=float(obj.get("pitch", 0.0)),
        roll=float(obj.get("roll", 0.0)),
        yaw=float(obj.get("yaw", 0.0)),
        checkpoint_time=float(obj.get("checkpoint_time", 0.0)),
        lidar_left=float(obj.get("lidar_left", 1.0)),
        lidar_right=float(obj.get("lidar_right", 1.0)),
        lidar_front=float(obj.get("lidar_front", 1.0)),
        alive=bool(obj.get("alive", True)),
        elapsed=float(obj.get("elapsed", 0.0)),
        distance=float(obj.get("distance", 0.0)),
        wall_penalty=float(obj.get("wall_penalty", 0.0)),
    )

def parse_frame(packet: dict, population_size=50) -> list[Telemetry]:
    agents = packet.get("agents")
    if not isinstance(agents, list) or len(agents) != population_size:
        raise ValueError(f"frame must contain exactly {population_size} agents")
    parsed = [parse_agent(a) for a in agents]
    parsed.sort(key=lambda x: x.agent_id)
    if [a.agent_id for a in parsed] != list(range(population_size)):
        raise ValueError("agent ids must be exactly 0..population_size-1")
    return parsed
