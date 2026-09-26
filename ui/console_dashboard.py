"""Low-overhead ANSI terminal dashboard; works on Windows and POSIX."""
from __future__ import annotations
import os
import sys
import time
from dataclasses import dataclass

@dataclass
class DashboardState:
    generation: int = 0
    active: int = 50
    best: float = 0.0
    mean: float = 0.0
    survival: float = 0.0
    focused: int = 0
    fps: float = 0.0

class ConsoleDashboard:
    def __init__(self):
        self.state = DashboardState()
        self._last = time.monotonic()

    def update(self, **values):
        for k, v in values.items():
            if hasattr(self.state, k):
                setattr(self.state, k, v)

    def render(self):
        s = self.state
        os.system("cls" if os.name == "nt" else "clear")
        print("TMRL — SIMULTANEOUS EVOLUTIONARY TRAINER")
        print("=" * 56)
        print(f"Generation        : {s.generation}")
        print(f"Active cars       : {s.active}/50")
        print(f"Best fitness      : {s.best:12.4f}")
        print(f"Mean fitness      : {s.mean:12.4f}")
        print(f"Generation survive: {s.survival * 100:8.2f}%")
        print(f"Focused agent     : {s.focused}")
        print(f"Telemetry rate    : {s.fps:8.2f} Hz")
        print("=" * 56)
        print("A/D focus selection is handled by the in-game Openplanet overlay.")
        sys.stdout.flush()
