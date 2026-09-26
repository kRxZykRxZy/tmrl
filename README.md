# TMRL — TrackMania Nations Forever AI Ghost Trainer

TMRL is a **50-genome evolutionary AI trainer** for TrackMania Nations Forever. It launches **2 live ghost cars by default** and can be raised to 50 from Settings.

## Current runtime architecture

The trainer is deliberately **player-safe**:

- Your TMNF car remains under your keyboard/controller.
- TMRL never calls TMInterface `set_input_state()`.
- TMRL never calls `rewind_to_state()`.
- TMRL never calls `respawn()` for the player.
- TMInterface is used only to read the player's world position/orientation.
- Up to 50 AI agents are available in the evolutionary population.
- Only the configured live-ghost count is simulated/rendered. The default is 2.
- A click-through Windows overlay renders the live agents as ghost-car silhouettes over the TMNF game window.
- The TMNF game speed is not changed by TMRL.

This is intentionally different from the previous save-state multiplexing design, which controlled the player's physical vehicle.

## What the ghosts are

The current ghosts are **rendered overlay cars**, not native Nadeo `CGameCtnGhost` entities.

TrackMania Forever does support Ghost.Gbx files and multi-ghost MediaTracker setups, and public tooling can read/write Ghost.Gbx data. citeturn463583search3turn554475search9

However, the public legacy TMInterface Python API does not expose a supported `spawn ghost` / `spawn vehicle` API. Its public state/input interfaces operate on the current vehicle. citeturn463583search2

The overlay therefore gives the requested **live, visible, non-controlling ghost cars** without taking over the player's vehicle. A native in-engine 3D ghost entity implementation would require a separate TMNF plugin/native modification layer.

## AI

Network:

```text
8 -> 32 ReLU -> 24 ReLU -> 2 Tanh
```

50 genomes evolve with:

- elite retention;
- roulette-wheel selection from elites;
- Gaussian mutation;
- 20-second generations by default;
- forward-progress fitness;
- immediate death for stalled/backwards/out-of-bounds virtual agents.

The current detached simulator is intentionally real-time and bounded so it cannot respawn itself after falling or getting stuck.

## Control Center

The control centre shows:

- live ghost count (default 2, configurable up to 50);
- CPU usage;
- optional adaptive CPU scaling with configurable target/min/max;
- generation;
- best and mean fitness;
- 50-agent status wall;
- live TMNF window capture;
- player-control status;
- detached ghost speed;
- replay trajectory preview;
- map selection;
- checkpoint/autosave controls.

The Camera Wall labels the TMNF image as **your player camera**. The ghost layer is rendered independently on top of it.

## Installation

Requirements:

- TrackMania Nations Forever
- TMInterface 1.4.3
- Python 3.10+
- Windows

Install dependencies:

```cmd
python -m pip install -r requirements.txt
```

## Run

Use **Windows CMD**:

```cmd
cd /d C:\Users\ymonz\tmrl
git pull
run.cmd
```

Then:

1. Start/load a TMNF track normally.
2. Enter a normal race.
3. Keep driving normally.
4. The 50 TMRL ghosts appear as a click-through overlay and train independently.

You do **not** need to surrender the game's controls to TMRL.

## Important TMInterface note

TMInterface's legacy Python client uses a synchronous memory-mapped protocol, and `on_registered` is a synchronous server call. Keeping that callback tiny is important. citeturn834197search3

TMRL therefore performs no checkpoint I/O, game-speed changes, input injection, or state rewinds from `on_registered`.

## Native ghost direction

For true in-engine ghost entities rather than the overlay, the repository's next native layer should target the 32-bit TMNF runtime. Public TMNF modding projects demonstrate ASI/DLL plugin loading and runtime hooks, and TMNF exposes debug-symbol information through `TmForever.map`. citeturn654352view0turn654352view1

Until that native layer is verified against the user's exact TMNF executable, TMRL does not claim that the overlay cars are native game entities.


## Resource safety

The default runtime is intentionally conservative after high-population testing caused excessive system load:

- Default live ghosts: **2**
- Maximum manual ghosts: **50**
- Adaptive CPU scaling: **off by default**
- Default adaptive CPU target: **65%**
- Default adaptive range: **2–20 ghosts**
- Scaling happens gradually in steps and applies at generation boundaries.

For a low-power PC, leave the default 2 ghosts. Increase the live count manually only while monitoring CPU usage.
