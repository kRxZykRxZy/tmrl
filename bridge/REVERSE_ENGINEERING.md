# TMNF Reverse-Engineering Workplan

## Phase 1 — Identify exact build

Record:

- TmForever.exe SHA-256
- version information
- PE timestamp
- image size
- relevant loaded modules

The bridge will be profile-driven.

## Phase 2 — Build function catalog

Research:

- game tick
- player object
- vehicle constructor/factory
- vehicle destructor
- render registration
- physics registration
- controller/input
- transform
- velocity
- race checkpoint
- respawn
- camera target

## Phase 3 — Object ownership

For every candidate object determine:

- allocation owner
- destructor
- vtable if present
- parent/child links
- scene registration
- physics registration
- pointer lifetime
- respawn behavior

## Phase 4 — Human isolation

Find the exact human-player object and prove that an independently created object has different identity and control state.

Required evidence:

    human_pointer != ai_pointer

and:

    ai_input_path != human_input_path

## Phase 5 — Vehicle creation

Test the smallest possible mutation.

Order:

1. locate factory;
2. call with no visible AI;
3. verify object exists;
4. register render state;
5. verify one visible object;
6. add physics;
7. add input;
8. read telemetry;
9. destroy.

## Phase 6 — Game-thread safety

All construction/destruction happens on the game thread.

Do not create or delete core TMNF objects from the IPC worker.

## Phase 7 — Evidence

Every discovery gets a file under bridge/evidence containing:

- executable hash
- profile
- discovery method
- function/signature
- calling convention
- test
- observed behavior
- cleanup behavior
- confidence
- unresolved questions

## Research references

Delorean12DMC/tmnf-plugins:

https://github.com/Delorean12DMC/tmnf-plugins

pixeltris/ModTMNF:

https://github.com/pixeltris/ModTMNF

TMUnlimiter:

https://github.com/tomek0055/TMUnlimiter

TMInterface documentation:

https://tminterface.readthedocs.io/

TMRL TMNF discussion:

https://github.com/trackmania-rl/tmrl/discussions/59

## No invented offsets

Do not put a guessed address into the bridge and call it an implementation.

A native address is accepted only after:

- exact executable hash is known;
- signature or symbol resolves;
- calling convention is verified;
- behavior is tested;
- cleanup is tested.
