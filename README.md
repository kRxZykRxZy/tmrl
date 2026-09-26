# TMRL — Single-Instance 50-Agent TrackMania Evolution Trainer

TMRL trains a population of **50 neural-network-controlled virtual cars through one TMNF + TMInterface 1.4.3 process**.

This revision intentionally removes the old architecture that launched 50 game processes. A single TMInterface server can expose simulation state save/rewind operations from the Python client, so TMRL stores 50 independent trajectory states and time-slices them through one rendered game process. TMInterface documents that `rewind_to_state()` is callable from `on_run_step` and that rewinding immediately advances the restored state by the next physics step. citeturn379962search0

## What "50 cars in one instance" means

TrackMania's legacy Python API does **not** provide a public API for creating 50 simultaneous physical player vehicles inside one legacy game process.

Instead TMRL keeps:

- 50 genomes
- 50 telemetry records
- 50 replay histories
- 50 saved TMInterface simulation states
- 50 safe recovery states

and rapidly switches the one real TMNF vehicle between those states.

Therefore:

- only **one** `TmForever.exe` runs;
- only **one** TMInterface server runs;
- the 50 agents train independently in the shared physics process;
- the currently selected trajectory is what the real TMNF camera displays;
- the control centre shows the other 49 as live telemetry/replay tiles rather than 49 simultaneous rendered game cameras.

## Neural controller

```
8 inputs
  ↓
32 ReLU
  ↓
24 ReLU
  ↓
2 Tanh
```

The exact parameter count is:

```
8×32 + 32 + 32×24 + 24 + 24×2 + 2 = 1,130
```

The eight inputs are normalized speed, X, Y, Z, yaw, and three proximity channels.

## Evolution

Population: 50

Elite count: 5

The top five genomes are copied unchanged. The remaining 45 are cloned from the elite set using roulette-wheel selection and mutated with:

```
mutation probability = 15%
Gaussian sigma = 0.15
```

Fitness:

```
1.5 × maximum distance
+ 0.5 × average speed
− wall/contact penalty
```

A generation ends after 20 seconds or when no live virtual agents remain.

## Automatic recovery

Every virtual agent continuously checks for:

- falling below the configured Y coordinate;
- moving outside the configured map coordinate bounds;
- near-zero movement for the configured stuck timeout;
- very low speed for the configured stuck timeout.

When one of these conditions fires, the agent is rewound to its latest safe state instead of wasting the rest of the generation.

Safe states are updated after meaningful progress, and the generation start state is always retained as a fallback.

The controls are configurable in `config/hyperparams.json`.

## Persistent NPZ checkpoints

The trainer automatically saves approximately every second by default.

The runtime creates:

```
tmrl/
└── checkpoints/
    ├── population.npz
    ├── agent_00.npz
    ├── agent_01.npz
    ├── ...
    ├── agent_49.npz
    └── manifest.json
```

Each agent checkpoint contains its genome, state blob, position/velocity, race time, distance, speed statistics, wall penalty, lap/checkpoint timing and bounded replay history.

The population checkpoint contains all 50 genomes, generation number, best score and map name.

On startup TMRL loads the saved population and agent checkpoints. If an old TMInterface state blob cannot be reconstructed by the installed client build, the trainer falls back to the current race-start state while retaining the learned population and replay data.

## Control Center

The Tkinter control centre includes:

### Dashboard
Generation, best fitness, mean fitness, active population, training speed, focused car, commands, lap/checkpoint information, wall penalty and recovery count.

### Agents
A 50-row table containing:

- alive/dead state
- speed
- distance
- fitness
- lap
- lap time
- average speed
- wall penalty

Click an agent to focus it.

### Camera Wall
The actual TMNF window is captured into the control centre. The selected virtual car can be switched into the real game camera, while the 50-agent wall provides live state tiles.

Because there is only one physical game renderer, a true 50-way simultaneous rendered camera wall is not possible without multiple game processes.

### Replay
Select any agent and inspect its stored trajectory. You can play the trajectory as a 2D replay preview and request the selected agent to be replayed inside TMNF.

### Race Setup
Load a map from the TMNF Tracks folder with TMInterface's documented `map` command, restart the race, or toggle single-agent testing. The TMInterface command guide documents `map <filename>` and `press delete` for restarting the current race. citeturn159668search0

### Settings
Change:

- TMInterface game-speed factor;
- background checkpoint/replay worker thread count.

The trainer's logical agents are still multiplexed through one TMInterface callback stream.

## Installation

You need:

- TrackMania Nations Forever
- TMInterface **1.4.3**
- Python 3.10+
- Windows

The upstream Python client is legacy and is intended for TMInterface versions below 2.0; its README points Python-client users to TMInterface 1.4.3. citeturn549681search0

Install Python dependencies:

```cmd
python -m pip install -r requirements.txt
```

## Run

Do **not** run `launch_50.cmd`. It has been removed.

Start the one TMInterface instance and the TMRL control centre with:

```cmd
run.cmd
```

By default the repository expects:

```
C:\Program Files (x86)\Steam\steamapps\common\TrackMania Nations Forever
```

If your installation is elsewhere, edit the `TMI_DIR` line at the top of `run.cmd`.

You can also start TMInterface manually from its installation directory, load a map, put the car into normal race mode, then run:

```cmd
python main.py
```

## Training speed

Because 50 logical trajectories are time-sliced through one game process, `1x` game speed would make each individual trajectory receive only a small fraction of the normal physics tick budget.

The default training speed is therefore **50x**. It is configurable from the Settings tab.

TMInterface documents the `speed` variable and warns that very high speed factors can affect the input subsystem; TMRL caps the UI control at 100x. citeturn379962search0turn159668search0

When you want to watch one agent normally, pause training or lower the game speed, select that agent, and use the camera/replay controls.

## Important

TMInterface explicitly treats these as tool-assisted runs. They are for training, research and experimentation and should not be submitted as legitimate public leaderboard runs. citeturn159668search1
