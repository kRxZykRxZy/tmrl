# Bridge Safety and Isolation

## Fail closed

Native writes are enabled only when:

- executable hash is known;
- profile is valid;
- critical signatures resolve;
- sanity checks pass;
- game-thread hook is live.

## Human protection

No native API may accept a generic current-vehicle target.

Every AI operation requires an explicit bridge handle.

Reject:

- null handle
- stale handle
- foreign session
- human player handle

## Emergency command

    emergency_stop_all_ai()

This affects only bridge-owned AI.

It must not:

- respawn human
- rewind human
- change global speed
- alter keyboard/controller state
- change player camera permanently

## Watchdogs

IPC watchdog:

- 500 ms warning
- 1500 ms AI failsafe
- 5000 ms stale session

Game-thread watchdog:

- detects hook stalls
- stops AI updates
- never mutates human state

## Release policy

Every supported executable build has a separate profile.

A TMNF update invalidates the profile until revalidated.
