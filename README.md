# TMRL — 50-Agent TMInterface Evolution Trainer

TMRL trains 50 neural-network genomes concurrently against TrackMania Nations Forever through legacy TMInterface 1.4.x and its Python client.

## Architecture

```
50 separate TMNF/TMInterface instances
        │
        ├── TMInterface0 → genome 0
        ├── TMInterface1 → genome 1
        ├── ...
        └── TMInterface49 → genome 49
                 │
                 ▼
          one Python coordinator
                 │
                 ├── 50 observations
                 ├── one NumPy population inference
                 ├── 50 analog steering/gas commands
                 └── evolutionary reset
```

TMInterface's Python API supports multiple server connections from one script, and its `on_run_step` hook is called every physics tick. Its legacy client also exposes vehicle position, velocity, yaw/pitch/roll and analog `steer/gas` injection. citeturn897701search0turn805361search0

This means the simultaneous-population design is **50 concurrent game instances**, not 50 physical player vehicles inside one TMNF process.

## Version requirement

The official Python client is legacy and is only compatible with TMInterface versions below 2.0. The upstream client README explicitly points users who need this API to TMInterface 1.4.3. The package installed by `pip` is `tminterface==1.0.2`. citeturn549681search0turn549681search1turn549681search3

Do not launch TMInterface 2.x with this Python package. TMInterface 2.x uses its newer AngelScript plugin API instead. citeturn549681search0turn588549search0

## Install

Install TMInterface 1.4.3 for TMNF, then install the Python dependencies:

```cmd
python -m pip install -r requirements.txt
```

TMInterface is installed through the TrackMania tooling/ModLoader or its standalone distribution; the official installation guide documents both approaches. citeturn445116search1

## Start 50 game instances

The repository includes `launch_50.cmd`.

First set the executable path in Windows CMD:

```cmd
set "TMI_EXE=C:\path\to\TMInterface.exe"
```

Then:

```cmd
launch_50.cmd
```

This sends 50 independent launch requests with a one-second spacing.

After they open, verify that the TMInterface server names exposed by the instances are:

```
TMInterface0
TMInterface1
...
TMInterface49
```

TMInterface's API identifies servers by these server names; its Python client accepts the server name explicitly. citeturn897701search0

Load the **same track** into all 50 instances and leave them in normal run mode at the start of the race.

## Start training

From the repository directory:

```cmd
run.cmd
```

or:

```cmd
python main.py
```

The coordinator connects one Python client to each named instance, requests the current simulation state on every run step, updates persistent telemetry, calculates one vectorized forward pass for the 50 genomes at about 60 Hz, and injects each car's individual analog steering/gas command.

Every instance is forced to normal `1.0x` game speed through `set_speed(1.0)`; TMInterface documents 1 as normal speed. citeturn788284search0turn588549search3

## Evolution

Initial genomes are random.

The network is:

```
8 → 32 ReLU → 24 ReLU → 2 Tanh
```

The exact parameter count is **1,130**, not 1,024:

```
8×32 + 32 + 32×24 + 24 + 24×2 + 2 = 1,130
```

The top five genomes survive unchanged. The remaining 45 are cloned from the elite set and independently mutated at a 15% per-parameter rate using Gaussian noise with sigma 0.15.

Fitness is:

```
1.5 × maximum distance
+ 0.5 × average speed
− wall/contact penalty
```

A generation ends after 20 seconds or when all agents have crashed. Each instance is then reset with:

```
press system retry
```

## Crash detection

An agent enters the crashed state after 1.5 seconds if its measured speed remains below 1 km/h for the configured debounce interval. Its next commands are zeroed while the other instances continue.

## LIDAR / wall proximity

The legacy Python API exposes rich vehicle physics state, but it does not expose a generic public world-mesh raycast call. The bridge therefore uses collision-aware proximity channels derived from TMInterface's exposed lateral-contact/sliding state rather than claiming to have a geometric raycast it cannot actually obtain from the API. The three channels remain part of the 8-input network and are updated continuously.

For true geometric Front/Left/Right raycasts on arbitrary maps, the bridge needs a map-specific TMInterface plugin/raycast provider. TMInterface 2.x has a documented AngelScript plugin API, but that is a different API generation from this legacy Python-client build. citeturn503300search3turn588549search0

## HUD

`ui/standalone_ui.py` creates a click-through Windows HUD with:

- generation
- all-time best fitness
- active population count
- focused agent
- speed
- distance
- fitness
- proximity channels
- hidden-layer activation bars
- A/D global focus switching

## Important hardware reality

Fifty full TMNF game instances at 1.0x is a very heavy workload. The code is designed for concurrent operation, but whether one PC can render all 50 instances in real time depends on its CPU, RAM, GPU and graphics settings. Running the games windowed at low resolution is the practical configuration.

TMInterface identifies these as tool-assisted runs; they should not be submitted as legitimate leaderboard runs. citeturn588549search0
