"""Telemetry and replay history for 50 virtual TMInterface agents."""
from __future__ import annotations
from dataclasses import dataclass, field
import math, threading
import numpy as np

HISTORY_LIMIT = 6000

@dataclass
class AgentTelemetry:
    agent_id: int
    position: np.ndarray = field(default_factory=lambda: np.zeros(3, np.float64))
    velocity: np.ndarray = field(default_factory=lambda: np.zeros(3, np.float64))
    yaw_pitch_roll: np.ndarray = field(default_factory=lambda: np.zeros(3, np.float64))
    lidar: np.ndarray = field(default_factory=lambda: np.ones(3, np.float32))
    activations: np.ndarray = field(default_factory=lambda: np.zeros(24, np.float32))
    state_blob: bytes = b""
    race_time_ms: int = 0
    distance: float = 0.0
    max_distance: float = 0.0
    speed_sum: float = 0.0
    samples: int = 0
    wall_penalty: float = 0.0
    alive: bool = True
    crashed: bool = False
    lap: int = 0
    lap_times: list[float] = field(default_factory=list)
    checkpoint_times: list[float] = field(default_factory=list)
    below_speed_since_ms: int = -1
    last_steer: float = 0.0
    last_gas: float = 0.0
    history_time: list[float] = field(default_factory=list)
    history_x: list[float] = field(default_factory=list)
    history_y: list[float] = field(default_factory=list)
    history_z: list[float] = field(default_factory=list)
    history_speed: list[float] = field(default_factory=list)
    history_steer: list[float] = field(default_factory=list)
    history_gas: list[float] = field(default_factory=list)

    @property
    def speed_mps(self): return float(np.linalg.norm(self.velocity))
    @property
    def speed_kmh(self): return self.speed_mps * 3.6
    @property
    def average_speed(self): return self.speed_sum / max(1, self.samples)
    @property
    def latest_lap_time(self): return self.lap_times[-1] if self.lap_times else 0.0

    def observation(self, speed_limit_kmh=300.0, position_scale=1000.0):
        x, y, z = self.position
        yaw = float(self.yaw_pitch_roll[0])
        return np.asarray([
            np.clip(self.speed_kmh / speed_limit_kmh, 0.0, 1.0),
            np.clip(x / position_scale, -1.0, 1.0),
            np.clip(y / position_scale, -1.0, 1.0),
            np.clip(z / position_scale, -1.0, 1.0),
            np.clip(yaw / math.pi, -1.0, 1.0),
            float(self.lidar[0]), float(self.lidar[1]), float(self.lidar[2])
        ], np.float32)

    def update_state(self, state, blob: bytes):
        p = np.asarray(state.position, np.float64)
        v = np.asarray(state.velocity, np.float64)
        if self.samples:
            self.distance += max(0.0, float(np.linalg.norm(p - self.position)))
        self.position[:] = p
        self.velocity[:] = v
        self.yaw_pitch_roll[:] = np.asarray(state.yaw_pitch_roll, np.float64)
        self.race_time_ms = int(state.race_time)
        self.state_blob = blob
        self.max_distance = max(self.max_distance, self.distance)
        self.speed_sum += self.speed_kmh
        self.samples += 1
        contact = bool(getattr(getattr(state, "scene_mobil", None), "has_any_lateral_contact", False))
        sliding = bool(getattr(getattr(state, "scene_mobil", None), "is_sliding", False))
        if contact:
            self.lidar[:] = np.minimum(self.lidar, np.asarray([0.20, 0.05, 0.05], np.float32))
            self.wall_penalty += 1.0
        elif sliding:
            self.lidar[:] = np.maximum(0.0, self.lidar * 0.98)
            self.wall_penalty += 0.05
        else:
            self.lidar += (1.0 - self.lidar) * 0.05
        if self.race_time_ms >= 1500 and self.speed_kmh < 1.0 and self.alive:
            if self.below_speed_since_ms < 0:
                self.below_speed_since_ms = self.race_time_ms
            elif self.race_time_ms - self.below_speed_since_ms >= 150:
                self.crashed = True
                self.alive = False
        else:
            self.below_speed_since_ms = -1

    def record_action(self, steer_norm: float, gas_norm: float):
        self.last_steer = float(steer_norm)
        self.last_gas = float(gas_norm)
        self.history_time.append(self.race_time_ms / 1000.0)
        self.history_x.append(float(self.position[0]))
        self.history_y.append(float(self.position[1]))
        self.history_z.append(float(self.position[2]))
        self.history_speed.append(float(self.speed_kmh))
        self.history_steer.append(self.last_steer)
        self.history_gas.append(self.last_gas)
        if len(self.history_time) > HISTORY_LIMIT:
            extra = len(self.history_time) - HISTORY_LIMIT
            for seq in (self.history_time, self.history_x, self.history_y, self.history_z,
                        self.history_speed, self.history_steer, self.history_gas):
                del seq[:extra]

    def lap_changed(self, lap: int, race_time_ms: int):
        if lap > self.lap:
            self.lap_times.append((race_time_ms / 1000.0) - sum(self.lap_times))
            self.lap = lap

    def checkpoint_changed(self, race_time_ms: int):
        self.checkpoint_times.append(race_time_ms / 1000.0)
        if len(self.checkpoint_times) > 512:
            del self.checkpoint_times[:-512]

    def reset(self, keep_history=False):
        self.position.fill(0); self.velocity.fill(0); self.yaw_pitch_roll.fill(0)
        self.lidar.fill(1); self.activations.fill(0)
        self.state_blob = b""
        self.race_time_ms = 0; self.distance = 0; self.max_distance = 0
        self.speed_sum = 0; self.samples = 0; self.wall_penalty = 0
        self.alive = True; self.crashed = False; self.lap = 0
        self.lap_times.clear(); self.checkpoint_times.clear()
        self.below_speed_since_ms = -1
        self.last_steer = self.last_gas = 0
        if not keep_history:
            self.history_time.clear(); self.history_x.clear(); self.history_y.clear()
            self.history_z.clear(); self.history_speed.clear()
            self.history_steer.clear(); self.history_gas.clear()

class TelemetryStore:
    def __init__(self, size=50):
        self.agents = [AgentTelemetry(i) for i in range(size)]
        self.lock = threading.RLock()

    def update(self, agent_id, state, blob):
        with self.lock:
            self.agents[agent_id].update_state(state, blob)

    def observation_matrix(self, speed_limit=300.0, position_scale=1000.0):
        with self.lock:
            return np.stack([a.observation(speed_limit, position_scale) for a in self.agents])

    def active_count(self):
        with self.lock:
            return sum(a.alive for a in self.agents)
