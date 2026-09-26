# Bridge Milestones

## M0 — Contract

- protocol
- Python client model
- native DLL project
- build profile format

Result:

TMRL can connect to a fake bridge without touching TMNF.

## M1 — Native presence

- DLL loads
- game build detected
- game tick hook works
- heartbeat works

Result:

bridge READY with human player untouched.

## M2 — Read-only game access

- human identity
- map
- race state
- game tick
- transform

Result:

stable native telemetry.

## M3 — One visible AI

- one independently owned vehicle object
- visible in TMNF
- independent transform
- clean destroy

Result:

AI car physically exists in the game world as an in-engine object.

## M4 — One physical AI

- independent controller
- steering
- throttle
- brake
- native physics
- telemetry

Result:

TMRL can drive the AI inside TMNF.

## M5 — Python backend

- NativeTmnfBackend
- bridge client
- telemetry adapter
- evolution integration

Result:

neural network controls the real TMNF AI car.

## M6 — Two agents

Result:

two simultaneous AI vehicles with independent control.

## M7 — Pool

Scale:

2 -> 4 -> 8 -> 12 -> 20

Measure:

FPS, CPU, memory, IPC, physics.

## M8 — Camera

- AI camera target
- AI camera state
- player camera restoration
- Control Center integration

## M9 — 30 to 50 agents

Scale:

20 -> 30 -> 40 -> 50

Use the existing resource governor.

## M10 — Production

- installer
- profile manifest
- diagnostics
- recovery mode
- exact-build documentation
- clean shutdown
- default 2 live agents
- configurable maximum

## Definition of done

The user's car remains completely independent while at least two AI vehicles can be physically rendered, controlled, simulated, telemetered, and destroyed inside TMNF.
