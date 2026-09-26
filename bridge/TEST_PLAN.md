# Bridge Test Plan

## Unit

Python:

- frame encoding
- frame decoding
- sequence handling
- capability parsing
- handle ownership
- telemetry decoding

Native:

- frame parser
- queue
- handle allocator
- build profile
- signature validation

## Native integration

### Test 1

Load bridge.

Expected:

- bridge initializes;
- unsupported build cannot enter write mode.

### Test 2

Human identity.

Expected:

- human captured;
- no AI alias.

### Test 3

One AI render.

Expected:

- visible;
- separate pose;
- player controls unchanged.

### Test 4

One AI physics.

Expected:

- steering, throttle, brake move only AI.

### Test 5

Telemetry.

Expected:

- native state matches in-game observations.

### Test 6

Destroy.

Expected:

- AI gone;
- player unchanged;
- no leaked references.

### Test 7

Two AI.

Expected:

- different handles;
- independent controls;
- independent positions.

### Test 8

Dropped packets.

Expected:

- stale inputs rejected;
- AI failsafe;
- human unaffected.

### Test 9

Python crash.

Expected:

- heartbeat timeout;
- AI cleanup/failsafe;
- player survives.

### Test 10

Bridge crash.

Expected:

- Python detects disconnect;
- no fallback control of human car.

### Test 11

Camera.

Expected:

- selected AI can be observed;
- player camera can be restored.

### Test 12

Long run.

Run at least 30 minutes.

Record:

- CPU
- FPS
- memory
- game tick stability
- IPC latency
- handle count
- allocations
- crashes

## Scale

1 -> 2 -> 4 -> 8 -> 12 -> 20 -> 30 -> 40 -> 50
