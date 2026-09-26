from bridge.python.models import (
    PLAYER_CAMERA_ID,
    PLAYER_VEHICLE_ID,
    ai_camera_id,
    ai_vehicle_id,
)


def test_player_identity():
    assert PLAYER_VEHICLE_ID == "player_car"
    assert PLAYER_CAMERA_ID == "player_camera"


def test_ai_id_sequence():
    assert ai_vehicle_id(0) == "ai_thread_1"
    assert ai_vehicle_id(49) == "ai_thread_50"
    assert ai_camera_id(0) == "ai_camera_1"
    assert ai_camera_id(49) == "ai_camera_50"
