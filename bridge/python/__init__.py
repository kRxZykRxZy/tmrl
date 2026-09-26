"""Python client/backend for the native TMRL ↔ TMNF bridge."""
from .models import (
    PLAYER_VEHICLE_ID,
    PLAYER_CAMERA_ID,
    ai_vehicle_id,
    ai_camera_id,
    BridgeCapabilities,
    CameraState,
    VehicleHandle,
    VehicleInput,
    VehicleState,
)
from .client import TmBridgeClient
from .backend import NativeBridgeBackend

__all__ = [
    "PLAYER_VEHICLE_ID",
    "PLAYER_CAMERA_ID",
    "ai_vehicle_id",
    "ai_camera_id",
    "BridgeCapabilities",
    "CameraState",
    "VehicleHandle",
    "VehicleInput",
    "VehicleState",
    "TmBridgeClient",
    "NativeBridgeBackend",
]
