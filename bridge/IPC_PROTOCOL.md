# Bridge IPC Protocol

## Transport

Primary:

Windows named pipe

    \\.\pipe\TMRL.TMNF.Bridge.v1

Development fallback:

localhost TCP with a dynamically selected local port.

## Framing

Fixed header:

    magic       u32
    version     u16
    message     u16
    flags       u32
    sequence    u64
    payload_len u32

Magic:

    TMRB

Initial payload:

UTF-8 JSON

Later:

packed binary telemetry is allowed for performance.

## Message IDs

0x0001 HELLO
0x0002 HELLO_ACK
0x0003 PING
0x0004 PONG
0x0010 START_SESSION
0x0011 STOP_SESSION
0x0020 CAPABILITIES
0x0100 CREATE_AGENT
0x0101 CREATE_AGENT_ACK
0x0102 DESTROY_AGENT
0x0103 DESTROY_ALL
0x0104 RESET_AGENT
0x0200 INPUT
0x0201 INPUT_BATCH
0x0210 CONTROL_MODE
0x0300 TELEMETRY
0x0301 TELEMETRY_BATCH
0x0400 MAP_INFO
0x0401 RACE_STATE
0x0500 CAMERA_TARGET
0x0501 CAMERA_RELEASE
0x0600 COMMAND_RESULT
0x0700 HEARTBEAT
0x0800 DIAGNOSTIC
0x0801 SELF_TEST
0x0900 EMERGENCY_STOP

## INPUT example

Fields:

    handle
    sequence
    steer
    throttle
    brake
    flags

The native bridge rejects stale sequence numbers.

## TELEMETRY example

Fields:

    handle
    agent_id
    game_tick
    position
    rotation
    velocity
    speed
    grounded
    checkpoint
    race_time
    alive
    crashed
    finished
    applied_input

## Result codes

OK
NOT_CONNECTED
WRONG_BUILD
CAPABILITY_UNAVAILABLE
INVALID_HANDLE
INVALID_ARGUMENT
SESSION_MISMATCH
ENTITY_LIMIT
QUEUE_FULL
GAME_NOT_READY
NATIVE_CALL_FAILED
HUMAN_PLAYER_PROTECTED
STALE_SEQUENCE
INTERNAL_ERROR

## Heartbeat policy

500 ms: warning

1500 ms: AI fail-safe

5000 ms: session considered stale

The fail-safe applies only to bridge-owned AI.

## Versioning

Major protocol changes increment the protocol major version.

Unknown optional fields should be ignored.

Unknown message types are rejected with an explicit result.
