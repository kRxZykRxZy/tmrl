# TMRL Native Bridge API Contract

## Connection

connect()
disconnect()
ping()
get_capabilities()
get_build_info()

## Session

start_session()
stop_session()
heartbeat()

## Vehicle lifecycle

create_vehicle(
    agent_id,
    position,
    rotation,
    velocity,
    control_mode,
    visible,
    collision,
    camera_capable
)

destroy_vehicle(handle)
destroy_all()
reset_vehicle(handle, reset_state)

## Control

set_input(
    handle,
    steer,
    throttle,
    brake,
    flags
)

set_input_batch(commands)
set_control_mode(handle, mode)

## State

get_vehicle_state(handle)
get_vehicle_states()
subscribe_telemetry(rate_hz)

## Race

get_map_info()
get_race_state()
reset_race_agents()

## Camera

set_camera_target(handle)
get_camera_state(handle)
release_camera_target()

## Diagnostics

run_self_test()
assert_isolated()
get_native_object_info(handle)
get_bridge_stats()

## Emergency

emergency_stop_all_ai()

## Core data types

VehicleHandle

    session_id
    slot_id
    generation

Vector3

    x
    y
    z

Rotation

    x
    y
    z
    w

VehicleInput

    sequence
    steer
    throttle
    brake
    flags

VehicleState

    handle
    agent_id
    game_tick
    position
    rotation
    velocity
    angular_velocity
    speed
    grounded
    checkpoint
    race_time
    alive
    crashed
    finished
    applied_input

Capabilities

    native_vehicle_spawn
    native_vehicle_physics
    native_vehicle_input
    native_vehicle_pose
    native_telemetry
    native_camera
    max_ai_slots

BuildInfo

    build_id
    exe_version
    exe_sha256
    bridge_version
    profile_version

## Ownership

Every AI belongs to exactly one bridge session.

Commands are rejected when:

    handle does not exist
    handle belongs to another session
    handle is stale
    handle refers to the human player

## Input safety

steer is clamped to [-1, +1].

throttle is clamped to [0, 1].

brake is clamped to [0, 1].

The bridge does not expose a "current car" mutation API.

## Backend integration

NativeTmnfBackend should implement the same high-level lifecycle used by DetachedGhostBackend.

Training code therefore consumes an abstract vehicle backend instead of knowing whether a vehicle is native or detached.


## Vehicle and camera identity

The bridge uses stable IDs:

    player_car
    player_camera

AI agents are:

    ai_thread_1
    ai_thread_2
    ai_thread_3
    ...
    ai_thread_N

Every AI has its own camera:

    ai_camera_1
    ai_camera_2
    ai_camera_3
    ...
    ai_camera_N

The vehicle ID and camera ID are immutable for the lifetime of the logical
agent slot. Native handles may be recycled, but the logical IDs remain stable.

## Per-car camera

Each AI owns a camera state containing:

    camera_id
    vehicle_id
    mode
    position
    look_at
    yaw
    pitch
    roll
    fov_deg
    distance
    height
    active
    native_supported

Supported modes are planned as:

    chase
    cockpit
    hood
    wheel
    orbit

The selected AI's camera is independent from every other AI camera.

Selecting:

    ai_thread_7

targets:

    ai_camera_7

The player camera remains:

    player_camera

and is restored with:

    release_camera_target()

The native bridge must never replace the player's camera permanently just to
observe an AI. Camera ownership is a view-state operation; AI control remains
owned by the AI handle.
