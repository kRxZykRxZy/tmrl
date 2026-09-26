from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


PLAYER_VEHICLE_ID = "player_car"
PLAYER_CAMERA_ID = "player_camera"


def ai_vehicle_id(agent_id: int) -> str:
    return f"ai_thread_{int(agent_id) + 1}"


def ai_camera_id(agent_id: int) -> str:
    return f"ai_camera_{int(agent_id) + 1}"


@dataclass(slots=True)
class BridgeCapabilities:
    connected: bool = False
    supported_build: bool = False
    native_vehicle_spawn: bool = False
    native_vehicle_physics: bool = False
    native_vehicle_input: bool = False
    native_vehicle_pose: bool = False
    native_telemetry: bool = False
    native_camera: bool = False
    max_ai_slots: int = 0
    bridge_version: str = ""
    protocol_version: int = 1
    build_id: str = ""
    read_only_reason: str = ""


@dataclass(slots=True, frozen=True)
class VehicleHandle:
    session_id: str
    slot_id: int
    generation: int
    vehicle_id: str


@dataclass(slots=True)
class VehicleInput:
    handle: VehicleHandle
    sequence: int
    steer: float
    throttle: float
    brake: float
    flags: int = 0


@dataclass(slots=True)
class CameraState:
    camera_id: str
    vehicle_id: str
    mode: str = "chase"
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    look_at: tuple[float, float, float] = (0.0, 0.0, 0.0)
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    fov_deg: float = 90.0
    distance: float = 6.0
    height: float = 2.0
    active: bool = False
    native_supported: bool = False


@dataclass(slots=True)
class VehicleState:
    handle: VehicleHandle
    agent_id: int
    position: tuple[float, float, float]
    rotation: tuple[float, float, float, float]
    velocity: tuple[float, float, float]
    speed: float
    grounded: bool
    checkpoint: int
    race_time_ms: int
    alive: bool
    crashed: bool
    finished: bool
    steer: float = 0.0
    throttle: float = 0.0
    brake: float = 0.0
    camera: CameraState | None = None
    raw: dict[str, Any] = field(default_factory=dict)
