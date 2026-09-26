# TMRL — 50-Agent TMInterface Evolution Trainer

This project trains a 50-genome population against Trackmania Nations Forever through the legacy TMInterface Python client.

## Architecture

```
tmrl/
├── core/
│   ├── network.py
│   └── evolution.py
├── environment/
│   └── telemetry.py
├── ui/
│   └── standalone_ui.py
├── config/
│   └── hyperparams.json
├── main.py
├── requirements.txt
└── README.md
```

## Critical architecture constraint

The Python TMInterface API controls one TMInterface server/client at a time, while a server represents one running game instance. The API explicitly supports connecting to many servers from the same script. Therefore this implementation uses:

- `TMInterface0` → genome 0
- `TMInterface1` → genome 1
- ...
- `TMInterface49` → genome 49

Those 50 TMNF/TMInterface instances must be running concurrently for 50 visible cars. This is the TMInterface-compatible equivalent of a simultaneous population; it is not a claim that one TMNF process contains 50 physical player vehicles.

TMInterface exposes physics-step callbacks and state fields including position, velocity and yaw/pitch/roll, and supports analog steering/gas input injection. The trainer keeps every instance at speed 1.0. citeturn3view0turn4view0

## Install

The original Python client is legacy and is documented for TMInterface versions below 2.0. The client package can be installed with:

```cmd
python -m pip install -r requirements.txt
```

The game installation must therefore provide compatible TMInterface server instances. Current TMInterface releases use a newer plugin API, so do not mix the legacy Python client with an incompatible server build. citeturn2search1turn5search0

## Run

Start all 50 compatible TMNF/TMInterface instances and ensure their server names are:

```
TMInterface0
TMInterface1
...
TMInterface49
```

Then:

```cmd
python main.py
```

The program connects each worker thread to one named server, runs every game at 1.0x, performs a population-level NumPy inference on the latest 50 observations, injects each agent's steering/gas command, and evolves the population when 20 seconds elapse or all agents have crashed.

## Network size

The requested `8 → 32 → 24 → 2` architecture has exactly 1,130 parameters:

`8×32 + 32 + 32×24 + 24 + 24×2 + 2 = 1,130`.

The implementation keeps the requested layer sizes. An exact 1,024-parameter network is mathematically incompatible with those exact layer sizes.

## Evolution

The initial population is randomly initialized, so no learned driving behaviour is supplied.

Each generation:

1. evaluates all 50 agents;
2. keeps the top five genomes unchanged;
3. selects parents only from those five using roulette-wheel probabilities;
4. creates the remaining 45 genomes by Gaussian mutation with a 15% per-parameter mutation rate and sigma 0.15;
5. resets all 50 game instances with `press system retry`.

Fitness is:

`1.5 × maximum forward distance + 0.5 × average speed − wall-contact penalty`.

## LIDAR

TMInterface's Python state API exposes vehicle state and input buffers, but does not expose a generic Trackmania world-mesh raycast API. The current telemetry layer therefore uses safe normalized distance channels until a map-specific collision/raycast provider is supplied; it does not fabricate wall coordinates or pretend they came from TMInterface.

The existing lateral-contact state can be used for the wall penalty. For genuine geometric Front/Left/Right LIDAR, the correct extension point is a TMInterface AngelScript plugin or another map-collision provider, while keeping the neural/evolutionary core unchanged.

## TAS warning

TMInterface is a tool-assisted environment. Runs produced with TMInterface should not be submitted as legitimate leaderboard runs. citeturn5search1
