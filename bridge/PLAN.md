# TMRL Native TMNF Bridge — Full Design Plan

## 1. Mission

Replace the current detached ghost renderer with a true in-process TrackMania Nations Forever bridge.

The target is not a screenshot overlay and not a second copy of the Python simulator.

The target is:

- TMRL remains the AI trainer.
- TMNF remains the actual rendered/physics world.
- A native bridge DLL runs inside TmForever.exe.
- The bridge creates independent AI-controlled vehicle entities inside the game.
- The user's normal car remains a separate human-controlled entity.
- AI control, telemetry, spawning, reset, destruction, and camera selection all use explicit AI handles.
- Multiple AI vehicles can exist simultaneously.

The first production milestone is one real in-game AI vehicle. Scaling to 50 comes only after the one-agent path is proven stable.

## 2. Why this is a separate bridge

TMInterface is useful for reading simulation state and controlling the currently controlled vehicle, but its public Python interface does not provide the entity-management API required for creating arbitrary independent live vehicles.

This bridge therefore does not try to make TMInterface pretend to be a multi-vehicle entity manager.

The architecture becomes:

    TMRL Python
        |
        | local bridge protocol
        v
    Native bridge DLL
        |
        | game-thread command queue
        v
    TMNF internal vehicle/world systems
        |
        +---- human player
        +---- AI vehicle 0
        +---- AI vehicle 1
        +---- ...
        +---- AI vehicle N

The Python trainer owns genomes and learning.

TMNF owns the actual in-game vehicle state.

## 3. External research that motivates the design

Public TMNF projects show that native runtime modification is practical:

- Delorean12DMC/tmnf-plugins demonstrates a TMNF ASI/DLL plugin approach and describes using Ghidra plus TmForever.map for internal exploration.
- pixeltris/ModTMNF demonstrates runtime loading, hooking, and accessing game state.
- TMUnlimiter is a deeper TMNF/TMUF modification project with extensive internal documentation.
- TMRL documentation/discussions explicitly mention that deeper TMNF tooling can perform capabilities such as spawning a car at selected state, even though modern TMRL did not retain that old architecture.

These are research references, not proof that a ready-made public spawn API exists. The exact vehicle construction path must still be discovered and validated against the exact TmForever.exe build.

## 4. Bridge directory

The planned repository layout is:

    bridge/
        PLAN.md
        API.md
        IPC_PROTOCOL.md
        NATIVE_IMPLEMENTATION.md
        REVERSE_ENGINEERING.md
        MILESTONES.md
        TEST_PLAN.md
        SAFETY.md

        python/
            __init__.py
            client.py
            models.py
            discovery.py
            exceptions.py
            backend.py

        native/
            CMakeLists.txt
            include/
                bridge_api.h
                bridge_protocol.h
                bridge_types.h
            src/
                dllmain.cpp
                bridge_server.cpp
                bridge_protocol.cpp
                command_queue.cpp
                telemetry_queue.cpp
                build_detector.cpp
                profile_loader.cpp
                hook_manager.cpp
                game_tick.cpp
                diagnostics.cpp
                game/
                    tmnf_adapter.cpp
                    tmnf_adapter.h
                    object_registry.cpp
                    vehicle_factory.cpp
                    vehicle_controller.cpp
                    vehicle_telemetry.cpp
                    race_adapter.cpp
                    camera_adapter.cpp

                memory/
                    module_map.cpp
                    signature_scan.cpp
                    safe_memory.cpp

        profiles/
            README.md
            profile_schema.json

        research/
            build_hashes.md
            function_catalog.md
            object_layouts.md
            signatures.md
            hook_points.md

        evidence/
            README.md
            BUILD_*.md
            SINGLE_AGENT_*.md

## 5. Core architecture

### TMRL side

Add a NativeTmnfBackend beside the existing detached backend.

Common backend contract:

    connect
    disconnect
    start_session
    stop_session
    create_vehicle
    destroy_vehicle
    destroy_all
    set_input
    set_input_batch
    get_state
    get_states
    reset_vehicle
    get_race_state
    set_camera_target
    release_camera_target
    capabilities

The existing evolution system should not care whether an agent is simulated or native.

### Native side

The native DLL is divided into:

1. bootstrap
2. build verification
3. hooks
4. IPC
5. command queue
6. entity manager
7. TMNF adapter
8. telemetry
9. safety/ownership
10. diagnostics

The game adapter is the only layer allowed to know raw internal TMNF addresses or object layouts.

## 6. Native game-thread rule

The IPC thread must never directly mutate live TMNF objects.

All mutations become game-thread commands.

Pipeline:

    Python
      |
      v
    named pipe
      |
      v
    IPC parser
      |
      v
    validated command queue
      |
      v
    game tick hook
      |
      +-- create
      +-- destroy
      +-- input
      +-- reset
      +-- camera
      |
      v
    telemetry sampling
      |
      v
    telemetry queue
      |
      v
    named pipe
      |
      v
    Python

This is essential for object lifetime and thread safety.

## 7. The actual AI entity

The bridge must distinguish between three concepts:

### Human player

The normal player-owned live vehicle.

### Replay/ghost data

A replay/ghost representation such as CGameCtnGhost or Ghost.Gbx data.

### Live AI vehicle

An actual scene object with the required render, control, and physics state.

The bridge must not assume that replay/ghost data automatically equals a live physical vehicle.

The acceptance definition of a live AI vehicle is:

- rendered by TMNF;
- independently positioned;
- independently controlled;
- independently simulated;
- has its own velocity;
- participates in the appropriate world/physics path;
- can be deleted without deleting the human car.

## 8. Vehicle creation strategy

Use a discovery ladder.

### Strategy A — internal vehicle factory

Find the internal construction path used when TMNF creates the player's live vehicle.

Best case:

- allocate object;
- initialize object through native constructor;
- attach physics/controller/render state;
- register with world/scene.

Clone or call the same lifecycle with a different owner/control state.

### Strategy B — clone existing vehicle object

If there is no callable generic factory, duplicate an existing vehicle object through the engine's own clone/initialization path, then replace:

- owner;
- input/controller;
- transform;
- race identity.

Avoid a raw memcpy clone unless the class layout and pointer ownership are fully understood.

### Strategy C — replay object promotion

Investigate whether a replay/ghost object can be converted into a live render/physics entity.

This is a fallback research path only.

A Ghost.Gbx file can be serialized/deserialized as CGameCtnGhost data, but serialization support alone does not establish live physics.

## 9. Human-player protection

The bridge must capture the human identity before AI creation.

Each AI operation takes an explicit AI handle.

Forbidden design:

    set_current_car_input(...)

Required design:

    set_input(ai_handle, ...)

Before every mutation:

    target exists
    target belongs to bridge session
    target is an AI slot
    target != human player
    target build/profile is valid

Any failed check rejects the command.

Add an explicit diagnostic:

    ASSERT_NO_ALIAS

It must prove that no AI handle points at the human player object.

## 10. AI input pipeline

Target control values:

    steer    [-1, +1]
    throttle [0, 1]
    brake    [0, 1]

Optional:

    handbrake
    respawn
    reset
    action flags

The Python neural network already produces steering and drive-like values. The native backend converts them to the normalized bridge contract.

The bridge then translates the normalized command to the internal TMNF control structure or function expected by the AI vehicle's controller.

The bridge must not write the human controller structure.

## 11. AI telemetry

Each AI should report:

    handle
    agent_id
    generation
    game_tick
    position x y z
    rotation
    linear velocity
    angular velocity where available
    speed
    ground/contact state
    checkpoint index
    race time
    finished
    crashed
    alive
    current input
    spawn state
    vehicle health/status if applicable

This is mapped into the existing AgentTelemetry model.

## 12. Race/reset semantics

The bridge must implement AI-only reset.

AI reset must not:

- respawn the human;
- rewind the human;
- change global game speed;
- alter the user's input;
- move the human vehicle.

Race lifecycle should be:

    MAP_READY
      |
      v
    CREATE AI POOL
      |
      v
    COUNTDOWN
      |
      v
    LIVE
      |
      +---- checkpoint
      +---- crash
      +---- finish
      +---- reset
      |
      v
    CLEANUP

## 13. Camera architecture

The current Camera Wall should eventually stop cloning the user's TMNF frame.

Native mode should expose:

    set_camera_target(ai_handle)
    get_camera_state(ai_handle)
    release_camera_target()

The camera system should temporarily target the selected AI if TMNF's internal camera path allows it.

The user must be able to restore the human camera.

Camera switching must not change AI control ownership.

## 14. IPC design

Use a local Windows named pipe first.

Suggested pipe:

    \\.\pipe\TMRL.TMNF.Bridge.v1

Fallback development transport:

    localhost TCP

Protocol is transport-independent.

Frame header:

    magic       4 bytes
    version     u16
    message     u16
    flags       u32
    sequence    u64
    payload_len u32

Initial payload encoding:

    UTF-8 JSON

Later high-rate telemetry can switch to packed binary records without changing the public API.

## 15. Full API surface

### Connection

    connect()
    disconnect()
    ping()
    get_capabilities()
    get_build_info()

### Session

    start_session()
    stop_session()
    heartbeat()

### Vehicle lifecycle

    create_vehicle(...)
    destroy_vehicle(handle)
    destroy_all()
    reset_vehicle(handle, state)

### Controls

    set_input(handle, steer, throttle, brake, flags)
    set_input_batch(commands)
    set_control_mode(handle, mode)

### Telemetry

    get_vehicle_state(handle)
    get_vehicle_states()
    subscribe_telemetry(rate_hz)

### Race

    get_map_info()
    get_race_state()
    reset_race_agents()

### Camera

    set_camera_target(handle)
    release_camera_target()
    get_camera_state(handle)

### Diagnostics

    run_self_test()
    assert_isolated()
    get_native_object_info(handle)
    get_bridge_stats()

### Emergency

    emergency_stop_all_ai()

The API never exposes a public operation that means "mutate whatever vehicle is currently active".

## 16. Create vehicle request

Fields:

    agent_id
    position
    rotation
    velocity
    control_mode
    visible
    collision
    camera_capable

Response:

    success
    bridge_handle
    native_object_id
    actual_position
    actual_rotation
    capabilities
    diagnostic_code

## 17. Command sequencing

Each AI has a monotonically increasing command sequence.

Rule:

    sequence <= last_sequence
        reject as stale

    sequence > last_sequence
        accept

This prevents delayed IPC packets from applying old controls.

## 18. Heartbeat

Recommended:

    warning: 500 ms
    AI fail-safe: 1500 ms
    session stale: 5000 ms

If Python disappears:

- AI commands stop;
- AI goes to a safe configured state;
- bridge preserves the human player;
- session cleanup eventually runs.

If the native bridge fails:

- Python marks native ghosts unavailable;
- does not fall back to writing TMInterface input to the player car.

## 19. Build profiles

Do not ship one global set of hard-coded offsets.

Each supported TmForever.exe build gets:

    build_id
    exe_version
    exe_sha256
    image_size
    signatures
    offsets
    vtables
    calling_conventions
    sanity_checks
    feature_flags

If the hash is unknown:

    native write mode = disabled

If a critical signature resolves incorrectly:

    native write mode = disabled

## 20. Reverse-engineering sequence

1. Hash the user's exact TmForever.exe.
2. Record version and PE metadata.
3. Load compatible map/symbol material into Ghidra/IDA.
4. Identify main game tick.
5. Identify human player object.
6. Identify vehicle constructor/factory.
7. Identify render/scene registration.
8. Identify physics/controller construction.
9. Identify input application/update function.
10. Identify world registration/removal.
11. Identify destruction path.
12. Validate every discovered function with a harmless read-only probe.
13. Implement a single AI render object.
14. Implement a single AI physics object.
15. Implement independent AI controls.
16. Add telemetry.
17. Add cleanup.
18. Scale to two.
19. Scale gradually.

## 21. Required native probes

Before vehicle spawning works, create diagnostic probes:

    game_tick_probe
    player_identity_probe
    world_object_probe
    vehicle_factory_probe
    vehicle_controller_probe
    vehicle_destroy_probe
    camera_probe

Each probe must produce an evidence record.

Evidence should contain:

- executable hash;
- profile;
- function/signature;
- test;
- result;
- crash status;
- cleanup status;
- confidence.

## 22. Scaling plan

Do not start with 50 native vehicles.

Use:

    1
    2
    4
    8
    12
    20
    30
    40
    50

At each step record:

- FPS;
- frame time;
- CPU;
- memory;
- physics stability;
- render stability;
- IPC latency;
- telemetry latency;
- command drop count;
- crashes;
- leaks.

The trainer keeps the existing CPU governor so a machine can dynamically reduce native AI count.

## 23. Integration with current TMRL

The existing detached simulator should become a backend.

Proposed abstraction:

    GhostBackend
        |
        +-- DetachedGhostBackend
        |
        +-- NativeTmnfBackend

Training code uses the backend contract.

This avoids rewriting:

- evolution;
- neural network;
- checkpoints;
- telemetry;
- fitness;
- UI state model.

The only major new dependency is native bridge connectivity.

## 24. Rollout plan

### Phase A

Bridge process and protocol with no game mutation.

### Phase B

Bridge loads inside TMNF and reports build/game status.

### Phase C

Read-only native telemetry.

### Phase D

One visible AI entity.

### Phase E

One physically simulated AI.

### Phase F

Python neural network controls native AI.

### Phase G

Two AI vehicles.

### Phase H

Camera integration.

### Phase I

5–10 vehicles.

### Phase J

10–50 stress testing.

### Phase K

Remove current screenshot-clone camera implementation from native mode.

## 25. Definition of done

The bridge is complete when:

1. the user can drive their own TMNF car normally;
2. at least one AI vehicle physically exists inside TMNF;
3. AI control is independent;
4. AI telemetry is returned to TMRL;
5. two or more AI vehicles can coexist;
6. each AI can be destroyed independently;
7. TMRL evolution directly drives the native AI;
8. the selected AI can be observed through the native camera path where supported;
9. unsupported TMNF builds reject native writes;
10. cleanup is reliable;
11. no AI pointer aliases the human;
12. bridge failure cannot take over the human vehicle.

## 26. What is deliberately not claimed yet

This plan does not claim that the exact constructor addresses, vtable indices, object layouts, or hook points are already known.

Those are reverse-engineering deliverables.

That distinction is important: the architectural bridge is fully specified, while the TMNF-specific internals still have to be measured and validated against the user's exact executable.
