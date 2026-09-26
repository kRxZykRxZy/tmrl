from __future__ import annotations

import json
import os
import secrets
import struct
import time
from pathlib import Path
from typing import Any

from .exceptions import BridgeDisconnected, BridgeProtocolError, BridgeRejected
from .models import (
    BridgeCapabilities,
    CameraState,
    VehicleHandle,
    VehicleInput,
    VehicleState,
)

PIPE_NAME = r"\\.\pipe\TMRL.TMNF.Bridge.v1"
HEADER = struct.Struct("<4sHHIQI")
MAGIC = b"TMRB"
PROTOCOL_VERSION = 1


class TmBridgeClient:
    """Synchronous local client for the native TMNF bridge."""

    def __init__(self, pipe_name: str = PIPE_NAME, timeout: float = 2.0):
        self.pipe_name = pipe_name
        self.timeout = max(0.1, float(timeout))
        self._pipe = None
        self._sequence = 0
        self.session_id = ""

    @property
    def connected(self) -> bool:
        return self._pipe is not None

    def connect(self) -> dict[str, Any]:
        if os.name != "nt":
            raise BridgeDisconnected("TMNF native bridge requires Windows")
        try:
            # Named pipes can be opened through the normal Windows file API.
            self._pipe = open(self.pipe_name, "r+b", buffering=0)
            hello = self.request(
                0x0001,
                {
                    "protocol_version": PROTOCOL_VERSION,
                    "client": "tmrl",
                    "client_nonce": secrets.token_hex(16),
                },
            )
            self.session_id = str(hello.get("session_id", ""))
            return hello
        except OSError as exc:
            self.close()
            raise BridgeDisconnected(str(exc)) from exc

    def close(self) -> None:
        pipe, self._pipe = self._pipe, None
        self.session_id = ""
        if pipe is not None:
            try:
                pipe.close()
            except OSError:
                pass

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _write_frame(self, message: int, payload: dict[str, Any]) -> int:
        if self._pipe is None:
            raise BridgeDisconnected("bridge is not connected")
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        seq = self._next_sequence()
        header = HEADER.pack(
            MAGIC,
            PROTOCOL_VERSION,
            int(message),
            0,
            seq,
            len(body),
        )
        self._pipe.write(header)
        self._pipe.write(body)
        self._pipe.flush()
        return seq

    def _read_exact(self, size: int) -> bytes:
        if self._pipe is None:
            raise BridgeDisconnected("bridge is not connected")
        chunks = bytearray()
        deadline = time.monotonic() + self.timeout
        while len(chunks) < size:
            if time.monotonic() > deadline:
                raise BridgeDisconnected("bridge response timeout")
            data = self._pipe.read(size - len(chunks))
            if not data:
                raise BridgeDisconnected("bridge closed the pipe")
            chunks.extend(data)
        return bytes(chunks)

    def _read_frame(self) -> tuple[int, dict[str, Any]]:
        header = self._read_exact(HEADER.size)
        magic, version, message, _flags, _sequence, length = HEADER.unpack(header)
        if magic != MAGIC:
            raise BridgeProtocolError("invalid bridge frame magic")
        if version != PROTOCOL_VERSION:
            raise BridgeProtocolError(f"unsupported protocol version {version}")
        body = self._read_exact(length) if length else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BridgeProtocolError("invalid JSON payload") from exc
        return message, payload

    def request(self, message: int, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self._write_frame(message, payload or {})
        _response_type, response = self._read_frame()
        if response.get("ok") is False:
            raise BridgeRejected(
                str(response.get("code", "INTERNAL_ERROR")),
                str(response.get("message", "bridge request rejected")),
            )
        return response

    def ping(self) -> dict[str, Any]:
        return self.request(0x0003, {})

    def get_capabilities(self) -> BridgeCapabilities:
        raw = self.request(0x0002, {})
        return BridgeCapabilities(
            connected=True,
            supported_build=bool(raw.get("supported_build", False)),
            native_vehicle_spawn=bool(raw.get("native_vehicle_spawn", False)),
            native_vehicle_physics=bool(raw.get("native_vehicle_physics", False)),
            native_vehicle_input=bool(raw.get("native_vehicle_input", False)),
            native_vehicle_pose=bool(raw.get("native_vehicle_pose", False)),
            native_telemetry=bool(raw.get("native_telemetry", False)),
            native_camera=bool(raw.get("native_camera", False)),
            max_ai_slots=int(raw.get("max_ai_slots", 0)),
            bridge_version=str(raw.get("bridge_version", "")),
            protocol_version=int(raw.get("protocol_version", PROTOCOL_VERSION)),
            build_id=str(raw.get("build_id", "")),
            read_only_reason=str(raw.get("read_only_reason", "")),
        )

    def start_session(self) -> str:
        result = self.request(0x0010, {})
        self.session_id = str(result["session_id"])
        return self.session_id

    def stop_session(self) -> None:
        if self.connected and self.session_id:
            self.request(0x0011, {"session_id": self.session_id})
        self.close()

    @staticmethod
    def _handle_payload(handle: VehicleHandle) -> dict[str, Any]:
        return {
            "session_id": handle.session_id,
            "slot_id": handle.slot_id,
            "generation": handle.generation,
            "vehicle_id": handle.vehicle_id,
        }

    def create_vehicle(
        self,
        agent_id: int,
        position=(0.0, 0.0, 0.0),
        rotation=(0.0, 0.0, 0.0, 1.0),
        velocity=(0.0, 0.0, 0.0),
        control_mode="native_physics",
    ) -> VehicleHandle:
        result = self.request(
            0x0100,
            {
                "session_id": self.session_id,
                "agent_id": int(agent_id),
                "vehicle_id": f"ai_thread_{int(agent_id) + 1}",
                "position": list(position),
                "rotation": list(rotation),
                "velocity": list(velocity),
                "control_mode": control_mode,
            },
        )
        return VehicleHandle(
            session_id=self.session_id,
            slot_id=int(result["slot_id"]),
            generation=int(result["generation"]),
            vehicle_id=str(result["vehicle_id"]),
        )

    def destroy_vehicle(self, handle: VehicleHandle) -> None:
        self.request(0x0102, {"handle": self._handle_payload(handle)})

    def destroy_all(self) -> None:
        self.request(0x0103, {"session_id": self.session_id})

    def reset_vehicle(self, handle: VehicleHandle, position, rotation, velocity=(0, 0, 0)) -> None:
        self.request(
            0x0104,
            {
                "handle": self._handle_payload(handle),
                "position": list(position),
                "rotation": list(rotation),
                "velocity": list(velocity),
            },
        )

    def set_input(self, command: VehicleInput) -> None:
        self.request(
            0x0200,
            {
                "handle": self._handle_payload(command.handle),
                "sequence": int(command.sequence),
                "steer": float(max(-1.0, min(1.0, command.steer))),
                "throttle": float(max(0.0, min(1.0, command.throttle))),
                "brake": float(max(0.0, min(1.0, command.brake))),
                "flags": int(command.flags),
            },
        )

    def set_input_batch(self, commands: list[VehicleInput]) -> None:
        self.request(
            0x0201,
            {
                "commands": [
                    {
                        "handle": self._handle_payload(c.handle),
                        "sequence": int(c.sequence),
                        "steer": float(max(-1.0, min(1.0, c.steer))),
                        "throttle": float(max(0.0, min(1.0, c.throttle))),
                        "brake": float(max(0.0, min(1.0, c.brake))),
                        "flags": int(c.flags),
                    }
                    for c in commands
                ]
            },
        )

    def set_camera_target(self, handle: VehicleHandle) -> CameraState:
        result = self.request(
            0x0500,
            {"handle": self._handle_payload(handle)},
        )
        return self._camera_from_payload(result)

    def release_camera_target(self) -> None:
        self.request(0x0501, {"session_id": self.session_id})

    def get_camera_state(self, handle: VehicleHandle) -> CameraState:
        result = self.request(
            0x0502,
            {"handle": self._handle_payload(handle)},
        )
        return self._camera_from_payload(result)

    @staticmethod
    def _camera_from_payload(raw: dict[str, Any]) -> CameraState:
        return CameraState(
            camera_id=str(raw["camera_id"]),
            vehicle_id=str(raw["vehicle_id"]),
            mode=str(raw.get("mode", "chase")),
            position=tuple(raw.get("position", (0, 0, 0))),
            look_at=tuple(raw.get("look_at", (0, 0, 0))),
            yaw=float(raw.get("yaw", 0.0)),
            pitch=float(raw.get("pitch", 0.0)),
            roll=float(raw.get("roll", 0.0)),
            fov_deg=float(raw.get("fov_deg", 90.0)),
            distance=float(raw.get("distance", 6.0)),
            height=float(raw.get("height", 2.0)),
            active=bool(raw.get("active", False)),
            native_supported=bool(raw.get("native_supported", False)),
        )
