from __future__ import annotations

import os
from pathlib import Path


PIPE_NAME = r"\\.\pipe\TMRL.TMNF.Bridge.v1"


def find_bridge_pipe() -> str | None:
    """Return the configured named pipe when running on Windows."""
    if os.name != "nt":
        return None
    # Do not attempt arbitrary process injection or scanning here.
    # The native bridge creates the named pipe when it is actually loaded.
    return PIPE_NAME


def find_native_bridge_root(project_root: str | Path | None = None) -> Path:
    root = Path(project_root) if project_root else Path(__file__).resolve().parents[2]
    return root / "bridge"
