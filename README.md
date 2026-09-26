# TMRL Simultaneous Evolutionary Trainer

This repository contains a modular 50-agent evolutionary controller for Trackmania Nations Forever through an Openplanet bridge.

## Layout

- `config/` — training configuration.
- `core/` — NumPy neural network and evolutionary engine.
- `environment/` — reference LIDAR geometry and telemetry normalization.
- `server/` — asyncio newline-delimited JSON control server.
- `ui/` — terminal diagnostics.
- `openplanet/` — AngelScript transport/overlay layer.

## Python

```text
python -m pip install -r requirements.txt
python -m server.async_server
```

The wire protocol is one JSON object per line. A frame contains exactly 50 agents with IDs `0..49`; the response contains 50 steering/throttle pairs.

## Network size

With the requested `8 -> 32 -> 24 -> 2` architecture, the exact parameter count is **1,130**, not 1,024: `8*32+32 + 32*24+24 + 24*2+2 = 1,130`. The implementation preserves the requested layer sizes rather than silently changing the architecture to hit 1,024.

## Evolution

The top five genomes are copied unchanged. Every other genome is cloned from the elite set using roulette-wheel parent selection and then receives independent Gaussian mutations at the configured 15% gene rate with sigma 0.15.

The Openplanet scripts deliberately isolate the game-specific vehicle adapter. Trackmania/Openplanet builds differ in what vehicle state and replay/ghost interfaces expose; unsupported raw memory offsets are not guessed or embedded into the trainer.
