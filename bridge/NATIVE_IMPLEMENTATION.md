# Native TMNF Implementation Plan

## Target

32-bit Windows native bridge DLL loaded into TmForever.exe.

## Native modules

    dllmain
    bridge_server
    bridge_protocol
    command_queue
    telemetry_queue
    build_detector
    profile_loader
    hook_manager
    game_tick
    diagnostics

## Game modules

    tmnf_adapter
    object_registry
    vehicle_factory
    vehicle_controller
    vehicle_telemetry
    race_adapter
    camera_adapter

## Memory modules

    module_map
    signature_scan
    safe_memory

## Loader

Use a tested ASI/DLL injection route.

Do not patch the executable permanently unless a loader limitation makes it necessary.

The loader path must be documented separately from the actual bridge logic.

## Build detection

At startup:

1. locate TmForever.exe module;
2. calculate SHA-256;
3. resolve profile;
4. validate module ranges;
5. resolve critical signatures;
6. run sanity checks;
7. enable only verified capabilities.

Unknown build:

    read-only diagnostics only

## Hook design

At least one stable game-thread execution point is required.

The hook must:

1. preserve original behavior;
2. execute bridge commands;
3. update AI objects;
4. sample telemetry;
5. publish events;
6. return to original code.

No blocking IPC inside the game hook.

## Vehicle construction

Preferred order:

1. identify engine vehicle factory;
2. call the game's own initialization path;
3. attach the correct render/physics/controller components;
4. register the entity in the same world structure used by real vehicles;
5. place the vehicle.

If that is impossible, investigate controlled cloning of an existing live vehicle object.

Do not use blind memory memcpy cloning.

## Independent controller

The critical discovery is an input/controller path that can be bound to the AI vehicle.

The AI controller must be separate from:

- keyboard;
- gamepad;
- human controller;
- global current-player input state.

## Physical mode

The preferred result is native physics.

TMRL sends normalized input.

TMNF computes:

- acceleration;
- steering response;
- collisions;
- gravity;
- suspension;
- contact;
- track interaction.

Pose injection remains available as a debug/recovery mode.

## Telemetry

Sample the native AI after its physics/update path has executed.

This prevents reporting input commands as though they were actual vehicle state.

## Cleanup

Every allocation path must have a matching destruction path.

On session stop:

1. stop accepting AI input;
2. queue destroy operations;
3. destroy on the game thread;
4. verify pointers/handles are gone;
5. return cleanup status.

## Human-player guard

The native bridge records the human vehicle identity before any AI spawn.

Every mutator accepts an AI handle.

If a resolved target equals the recorded human object:

    return HUMAN_PLAYER_PROTECTED

## Diagnostics

Provide:

    get_build_info
    get_bridge_stats
    get_native_object_info
    run_self_test
    assert_isolated

## Important implementation constraint

Exact internal function addresses and layouts are build-specific research results.

They must live in build profiles and signature catalogs, not in generic business logic.
