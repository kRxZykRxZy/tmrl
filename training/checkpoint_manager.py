"""Atomic NumPy checkpoint persistence for the 50 virtual agents."""
from __future__ import annotations
import json
import os
import tempfile
import threading
from pathlib import Path
import numpy as np

class CheckpointManager:
    def __init__(self, root: Path, agent_count: int):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.agent_count = agent_count
        self.lock = threading.RLock()

    def _atomic_npz(self, path: Path, **arrays):
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=path.stem + "_", suffix=".tmp.npz", dir=path.parent)
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            np.savez_compressed(tmp, **arrays)
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()

    def save_population(self, population, generation: int, best_score: float, map_name: str):
        with self.lock:
            self._atomic_npz(
                self.root / "population.npz",
                population=np.asarray(population, np.float32),
                generation=np.asarray([generation], np.int64),
                best_score=np.asarray([best_score], np.float64),
                map_name=np.asarray([map_name], dtype="U512"),
            )

    def save_agent(self, agent, genome):
        with self.lock:
            self._atomic_npz(
                self.root / f"agent_{agent.agent_id:02d}.npz",
                genome=np.asarray(genome, np.float32),
                state=np.frombuffer(agent.state_blob or b"", np.uint8),
                position=agent.position.astype(np.float64),
                velocity=agent.velocity.astype(np.float64),
                yaw_pitch_roll=agent.yaw_pitch_roll.astype(np.float64),
                distance=np.asarray([agent.distance], np.float64),
                max_distance=np.asarray([agent.max_distance], np.float64),
                speed_sum=np.asarray([agent.speed_sum], np.float64),
                samples=np.asarray([agent.samples], np.int64),
                wall_penalty=np.asarray([agent.wall_penalty], np.float64),
                race_time_ms=np.asarray([agent.race_time_ms], np.int64),
                lap=np.asarray([agent.lap], np.int64),
                lap_times=np.asarray(agent.lap_times, np.float64),
                checkpoint_times=np.asarray(agent.checkpoint_times, np.float64),
                history_time=np.asarray(agent.history_time, np.float64),
                history_x=np.asarray(agent.history_x, np.float32),
                history_y=np.asarray(agent.history_y, np.float32),
                history_z=np.asarray(agent.history_z, np.float32),
                history_speed=np.asarray(agent.history_speed, np.float32),
                history_steer=np.asarray(agent.history_steer, np.float32),
                history_gas=np.asarray(agent.history_gas, np.float32),
            )

    def load_population(self):
        path = self.root / "population.npz"
        if not path.exists():
            return None
        with np.load(path, allow_pickle=False) as data:
            return {
                "population": np.asarray(data["population"], np.float32),
                "generation": int(data["generation"][0]),
                "best_score": float(data["best_score"][0]),
                "map_name": str(data["map_name"][0]),
            }

    def load_agent(self, agent):
        path = self.root / f"agent_{agent.agent_id:02d}.npz"
        if not path.exists():
            return False
        with np.load(path, allow_pickle=False) as data:
            state = np.asarray(data["state"], np.uint8)
            agent.state_blob = bytes(state.tobytes())
            agent.position[:] = data["position"]
            agent.velocity[:] = data["velocity"]
            agent.yaw_pitch_roll[:] = data["yaw_pitch_roll"]
            agent.distance = float(data["distance"][0])
            agent.max_distance = float(data["max_distance"][0])
            agent.speed_sum = float(data["speed_sum"][0])
            agent.samples = int(data["samples"][0])
            agent.wall_penalty = float(data["wall_penalty"][0])
            agent.race_time_ms = int(data["race_time_ms"][0])
            agent.lap = int(data["lap"][0])
            agent.lap_times = [float(v) for v in data["lap_times"].tolist()]
            agent.checkpoint_times = [float(v) for v in data["checkpoint_times"].tolist()]
            agent.history_time = data["history_time"].astype(np.float64).tolist()
            agent.history_x = data["history_x"].astype(np.float32).tolist()
            agent.history_y = data["history_y"].astype(np.float32).tolist()
            agent.history_z = data["history_z"].astype(np.float32).tolist()
            agent.history_speed = data["history_speed"].astype(np.float32).tolist()
            agent.history_steer = data["history_steer"].astype(np.float32).tolist()
            agent.history_gas = data["history_gas"].astype(np.float32).tolist()
        return True

    def manifest(self, generation: int, map_name: str):
        payload = {"generation": generation, "map_name": map_name}
        (self.root / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
