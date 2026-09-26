from __future__ import annotations

from .client import TmBridgeClient
from .models import (
    CameraState,
    VehicleHandle,
    VehicleInput,
    VehicleState,
    ai_camera_id,
    ai_vehicle_id,
)


class NativeBridgeBackend:
    """Bridge-backed vehicle manager used by the trainer when native mode is available."""

    def __init__(self, client: TmBridgeClient):
        self.client = client
        self.handles: dict[int, VehicleHandle] = {}
        self.camera_targets: dict[int, CameraState] = {}

    def connect(self) -> None:
        if not self.client.connected:
            self.client.connect()
        if not self.client.session_id:
            self.client.start_session()

    def disconnect(self) -> None:
        self.client.stop_session()
        self.handles.clear()
        self.camera_targets.clear()

    def spawn(self, agent_id: int, position, rotation, velocity=(0, 0, 0)) -> VehicleHandle:
        handle = self.client.create_vehicle(
            agent_id=agent_id,
            position=position,
            rotation=rotation,
            velocity=velocity,
        )
        self.handles[int(agent_id)] = handle
        return handle

    def destroy(self, agent_id: int) -> None:
        handle = self.handles.pop(int(agent_id), None)
        if handle is not None:
            self.client.destroy_vehicle(handle)
            self.camera_targets.pop(int(agent_id), None)

    def destroy_all(self) -> None:
        self.client.destroy_all()
        self.handles.clear()
        self.camera_targets.clear()

    def send_inputs(self, commands: list[VehicleInput]) -> None:
        if commands:
            self.client.set_input_batch(commands)

    def select_camera(self, agent_id: int) -> CameraState:
        handle = self.handles[int(agent_id)]
        state = self.client.set_camera_target(handle)
        self.camera_targets[int(agent_id)] = state
        return state

    def release_camera(self) -> None:
        self.client.release_camera_target()
        self.camera_targets.clear()

    def camera_id(self, agent_id: int) -> str:
        return ai_camera_id(agent_id)

    def vehicle_id(self, agent_id: int) -> str:
        return ai_vehicle_id(agent_id)
