"""Persistent telemetry extracted from legacy TMInterface SimStateData."""
from __future__ import annotations
from dataclasses import dataclass, field
import math, threading
import numpy as np

@dataclass
class AgentTelemetry:
    agent_id: int
    position: np.ndarray = field(default_factory=lambda: np.zeros(3, np.float64))
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(3, np.float64))
    yaw_pitch_roll: np.ndarray = field(default_factory=lambda: np.zeros(3, np.float64))
    race_time_ms: int = 0
    distance: float = 0.0
    max_distance: float = 0.0
    speed_sum: float = 0.0
    samples: int = 0
    wall_penalty: float = 0.0
    alive: bool = True
    crashed: bool = False
    below_speed_since_ms: int = -1
    activations: np.ndarray = field(default_factory=lambda: np.zeros(24, np.float32))
    lidar: np.ndarray = field(default_factory=lambda: np.ones(3, np.float32))
    last_steer: float = 0.0

    @property
    def speed_mps(self) -> float:
        return float(np.linalg.norm(self.velocity))

    @property
    def speed_kmh(self) -> float:
        return self.speed_mps * 3.6

    @property
    def average_speed(self) -> float:
        return self.speed_sum / max(1, self.samples)

    def observation(self, speed_limit=300.0, position_scale=1000.0) -> np.ndarray:
        x, y, z = self.position
        yaw = float(self.yaw_pitch_roll[0])
        return np.asarray(
            [
                np.clip(self.speed_kmh / speed_limit, 0.0, 1.0),
                np.clip(x / position_scale, -1.0, 1.0),
                np.clip(y / position_scale, -1.0, 1.0),
                np.clip(z / position_scale, -1.0, 1.0),
                np.clip(yaw / math.pi, -1.0, 1.0),
                float(self.lidar[0]),
                float(self.lidar[1]),
                float(self.lidar[2]),
            ],
            dtype=np.float32,
        )

    def _update_proximity(self, state):
        lateral_contact = bool(getattr(getattr(state, "scene_mobil", None), "has_any_lateral_contact", False))
        sliding = bool(getattr(getattr(state, "scene_mobil", None), "is_sliding", False))
        contact = 0.04 if lateral_contact else 1.0

        # The official legacy Python API exposes vehicle dynamics and lateral contact,
        # but not a generic world-mesh raycast. These channels therefore behave as
        # collision-aware proximity signals until a map-specific raycast provider is used.
        if lateral_contact:
            if self.last_steer < -0.05:
                self.lidar[1] = contact
                self.lidar[2] = min(1.0, self.lidar[2] + 0.2)
            elif self.last_steer > 0.05:
                self.lidar[2] = contact
                self.lidar[1] = min(1.0, self.lidar[1] + 0.2)
            else:
                self.lidar[1] = contact
                self.lidar[2] = contact
            self.lidar[0] = min(self.lidar[0], 0.35)
            self.wall_penalty += 1.0
        elif sliding:
            self.lidar *= 0.95
            self.wall_penalty += 0.05
        else:
            self.lidar += (1.0 - self.lidar) * 0.08

    def update(self, state):
        p = np.asarray(state.position, dtype=np.float64)
        v = np.asarray(state.velocity, dtype=np.float64)
        if self.samples:
            self.distance += max(0.0, float(np.linalg.norm(p - self.position)))
        self.position = p
        self.velocity = v
        self.yaw_pitch_roll = np.asarray(state.yaw_pitch_roll, dtype=np.float64)
        self.race_time_ms = int(state.race_time)
        input_steer = int(getattr(state, "input_steer", 0))
        self.last_steer = float(np.clip(input_steer / 65536.0, -1.0, 1.0))
        self.max_distance = max(self.max_distance, self.distance)
        self.speed_sum += self.speed_kmh
        self.samples += 1
        self._update_proximity(state)

        if self.race_time_ms >= 1500 and self.speed_kmh < 1.0 and self.alive:
            if self.below_speed_since_ms < 0:
                self.below_speed_since_ms = self.race_time_ms
            elif self.race_time_ms - self.below_speed_since_ms >= 150:
                self.crashed = True
                self.alive = False
        else:
            self.below_speed_since_ms = -1

    def reset(self):
        self.position.fill(0.0)
        self.velocity.fill(0.0)
        self.yaw_pitch_roll.fill(0.0)
        self.race_time_ms = 0
        self.distance = 0.0
        self.max_distance = 0.0
        self.speed_sum = 0.0
        self.samples = 0
        self.wall_penalty = 0.0
        self.alive = True
        self.crashed = False
        self.below_speed_since_ms = -1
        self.activations.fill(0.0)
        self.lidar.fill(1.0)
        self.last_steer = 0.0

class TelemetryStore:
    def __init__(self, size=50):
        self.agents = [AgentTelemetry(i) for i in range(size)]
        self.lock = threading.RLock()

    def update(self, i, state):
        with self.lock:
            self.agents[i].update(state)

    def observation(self, i):
        with self.lock:
            return self.agents[i].observation()

    def observations(self):
        with self.lock:
            return np.stack([a.observation() for a in self.agents])

    def active_count(self):
        with self.lock:
            return sum(a.alive for a in self.agents)
