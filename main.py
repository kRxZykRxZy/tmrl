"""TMRL detached ghost trainer.

The user's TMNF car is never controlled by this trainer.

TMInterface is used read-only to sample the player's world position/orientation.
Fifty AI agents run in a detached real-time kinematic simulator and are rendered
as click-through ghost cars over the TMNF window.
"""
from __future__ import annotations

import copy
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

from core.evolution import EvolutionEngine
from core.network import NeuralNetwork
from environment.telemetry import TelemetryStore
from environment.ghost_sim import GhostSimulation
from environment.resource_monitor import CPUUsage
from training.checkpoint_manager import CheckpointManager
from ui.control_center import ControlCenter

try:
    from tminterface.client import Client
    from tminterface.interface import TMInterface
except ImportError as exc:
    raise SystemExit("Install: python -m pip install -r requirements.txt") from exc

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config" / "hyperparams.json").read_text(encoding="utf-8"))
MAX_AGENTS = int(CFG["population_size"])
LOG = logging.getLogger("tmrl")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


class Trainer(Client):
    def __init__(self):
        super().__init__()

        self.telemetry = TelemetryStore(MAX_AGENTS)
        seed = CFG.get("random_seed")
        rng = np.random.default_rng(seed)

        self.engine = EvolutionEngine(
            NeuralNetwork.population(N, rng),
            elite_count=int(CFG["elite_count"]),
            mutation_rate=float(CFG["mutation_rate"]),
            mutation_sigma=float(CFG["mutation_sigma"]),
            seed=seed,
        )

        self.checkpoints = CheckpointManager(ROOT / "checkpoints", MAX_AGENTS)
        self.executor = ThreadPoolExecutor(
            max_workers=int(CFG.get("worker_threads", 2))
        )

        self.iface: TMInterface | None = None
        self.running = True
        self.training_enabled = True
        self.paused = False
        self.focus = 0
        self.worker_threads = int(CFG.get("worker_threads", 2))
        self.map_name = str(CFG.get("map_name", ""))
        self.agent_count = max(1, min(MAX_AGENTS, int(CFG.get("default_agent_count", 2))))
        self.adaptive_cpu = bool(CFG.get("adaptive_cpu", False))
        self.cpu_target = float(CFG.get("cpu_target_percent", 70.0))
        self.cpu_min_agents = max(1, min(MAX_AGENTS, int(CFG.get("cpu_min_agents", 2))))
        self.cpu_max_agents = max(self.cpu_min_agents, min(MAX_AGENTS, int(CFG.get("cpu_max_agents", MAX_AGENTS))))
        self.cpu_scale_step = max(1, int(CFG.get("cpu_scale_step", 2)))
        self.cpu_scale_interval = max(1.0, float(CFG.get("cpu_scale_interval_seconds", 5.0)))
        self.cpu_usage = None
        self.cpu_monitor = CPUUsage()
        self.last_cpu_scale = time.monotonic()
        self.pending_agent_count = self.agent_count

        # This factor only affects the detached simulator. It never changes
        # TMNF's speed or input handling.
        self.sim_speed = 1.0

        self.generation_started = time.monotonic()
        self.training_ticks = 0
        self.last_error = ""
        self.last_summary = {
            "generation": 0,
            "best_fitness": 0.0,
            "mean_fitness": 0.0,
            "survival_rate": 0.0,
            "agent_count": self.agent_count,
        }

        self.player_lock = threading.RLock()
        self.player = None
        self.sim_started = False
        self.last_sim_step = time.monotonic()
        self.generation_timeout = float(
            CFG.get("generation_timeout_seconds", 20.0)
        )

        seed2 = None if seed is None else int(seed) + 1001
        self.simulator = GhostSimulation(
            self.telemetry,
            self.engine,
            np.random.default_rng(seed2),
            MAX_AGENTS,
        )
        self.simulator.set_active_count(self.agent_count)

        self.camera_sweep = False

        self.autosave_stop = threading.Event()
        try:
            self._load_population_checkpoint_only()
        except Exception as exc:
            self.last_error = f"checkpoint load: {type(exc).__name__}: {exc}"
            LOG.exception("population checkpoint loading failed")

        self.autosave_thread = threading.Thread(
            target=self._autosave_loop,
            name="tmrl-autosave",
            daemon=True,
        )
        self.autosave_thread.start()

    # ---------- lifecycle ----------

    def on_registered(self, iface):
        # Keep this callback effectively empty. TMInterface treats
        # S_ON_REGISTERED as a synchronous server call.
        self.iface = iface
        LOG.info("registered with TMInterface in READ-ONLY mode")
        LOG.info("player controls are disabled from TMRL: ghost training only")

    def on_shutdown(self, iface):
        self.running = False

    def on_deregistered(self, iface):
        self.running = False

    def on_client_exception(self, iface, exception):
        self.last_error = f"TMInterface: {type(exception).__name__}: {exception}"
        LOG.error("TMInterface exception: %s", exception)

    # ---------- persistence ----------

    def _load_population_checkpoint_only(self):
        data = self.checkpoints.load_population()
        if data is None:
            return

        pop = data["population"]
        if pop.shape == self.engine.population.shape:
            self.engine.population[:] = pop
            self.engine.generation = data["generation"]
            self.engine.best_score = data["best_score"]
            self.map_name = data["map_name"] or self.map_name
            LOG.info(
                "loaded population checkpoint at generation %d",
                self.engine.generation,
            )

        # Intentionally do NOT restore old state blobs here. Those states
        # belonged to the old one-car rewind architecture.

    def save_now(self):
        with self.player_lock:
            population = self.engine.population.copy()
            generation = self.engine.generation
            best = self.engine.best_score
            map_name = self.map_name
            agents = [
                (copy.deepcopy(a), population[a.agent_id].copy())
                for a in self.telemetry.agents
            ]

        self.executor.submit(
            self.checkpoints.save_population,
            population,
            generation,
            best,
            map_name,
        )
        for agent, genome in agents:
            self.executor.submit(
                self.checkpoints.save_agent,
                agent,
                genome,
            )
        self.checkpoints.manifest(generation, map_name)

    def _autosave_loop(self):
        interval = max(2.0, float(CFG.get("autosave_seconds", 10.0)))
        while not self.autosave_stop.wait(interval):
            try:
                self.save_now()
            except Exception:
                LOG.exception("background autosave failed")

    # ---------- player sampling ----------

    def _read_player_state(self, iface):
        state = iface.get_simulation_state()
        position = np.asarray(state.position, np.float64)
        ypr = np.asarray(state.yaw_pitch_roll, np.float64)
        return {
            "position": position,
            "yaw": float(ypr[0]),
            "pitch": float(ypr[1]),
            "roll": float(ypr[2]),
            "speed": float(state.display_speed),
            "race_time_ms": int(state.race_time),
        }

    def player_snapshot(self):
        with self.player_lock:
            if self.player is None:
                return None
            return {
                "position": self.player["position"].copy(),
                "yaw": self.player["yaw"],
                "pitch": self.player["pitch"],
                "roll": self.player["roll"],
                "speed": self.player["speed"],
                "race_time_ms": self.player["race_time_ms"],
            }

    # ---------- simulation ----------

    def _start_sim_from_player(self):
        player = self.player_snapshot()
        if player is None:
            return
        self.simulator.start(player["position"], player["yaw"])
        self.sim_started = True
        self.last_sim_step = time.monotonic()
        self.generation_started = time.monotonic()
        LOG.info(
            "started %d detached real-time ghost agents at player position",
            self.agent_count,
        )

    def _finish_generation(self):
        results = self.simulator.fitness_results()
        self.last_summary = self.engine.evolve_subset(results, self.agent_count)

        if self.pending_agent_count != self.agent_count:
            self.agent_count = self.pending_agent_count
            self.simulator.set_active_count(self.agent_count)

        self._sample_cpu_and_maybe_scale(force=True)
        LOG.info(
            "generation %d best %.3f mean %.3f survival %.1f%%",
            self.engine.generation,
            self.last_summary["best_fitness"],
            self.last_summary["mean_fitness"],
            self.last_summary["survival_rate"] * 100.0,
        )

        if self.player_snapshot() is not None:
            self._start_sim_from_player()

    def _generation_finished(self):
        if time.monotonic() - self.generation_started >= self.generation_timeout:
            return True
        return self.telemetry.active_count() == 0

    def _on_run_step_impl(self, iface, _time):
        now = time.monotonic()

        # Read-only: no set_input_state(), no rewind_to_state(), no respawn().
        # Sampling is throttled so TMInterface stays responsive.
        if self.player is None or now - getattr(self, "_last_player_sample", 0.0) >= 0.05:
            self.player = self._read_player_state(iface)
            self._last_player_sample = now

        if not self.sim_started:
            self._start_sim_from_player()
            return

        if self.paused or not self.training_enabled:
            self.last_sim_step = now
            return

        dt = max(0.0, min(0.05, now - self.last_sim_step))
        self.last_sim_step = now
        if dt <= 0.0:
            return

        scaled_dt = dt * max(0.05, min(2.0, self.sim_speed))
        self.simulator.step(scaled_dt)
        self.training_ticks += 1
        self._sample_cpu_and_maybe_scale()

        if self._generation_finished():
            self._finish_generation()

    def on_run_step(self, iface, _time):
        try:
            self._on_run_step_impl(iface, _time)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            LOG.exception("on_run_step failure")

    # ---------- resource scaling ----------

    def _sample_cpu_and_maybe_scale(self, force=False):
        now = time.monotonic()
        usage = self.cpu_monitor.sample()
        if usage is not None:
            self.cpu_usage = usage

        if not self.adaptive_cpu:
            return
        if not force and now - self.last_cpu_scale < self.cpu_scale_interval:
            return

        self.last_cpu_scale = now
        if self.cpu_usage is None:
            return

        low = max(5.0, self.cpu_target - 10.0)
        high = min(99.0, self.cpu_target + 10.0)
        desired = self.agent_count

        if self.cpu_usage > high:
            desired = max(self.cpu_min_agents, self.agent_count - self.cpu_scale_step)
        elif self.cpu_usage < low:
            desired = min(self.cpu_max_agents, self.agent_count + self.cpu_scale_step)

        if desired != self.agent_count:
            self.pending_agent_count = desired
            LOG.info(
                "adaptive CPU scaling: %.1f%% CPU -> request %d ghosts (current %d)",
                self.cpu_usage, desired, self.agent_count,
            )

    def set_agent_count(self, count):
        count = max(1, min(MAX_AGENTS, int(count)))
        self.pending_agent_count = count
        if not self.sim_started:
            self.agent_count = count
            self.simulator.set_active_count(count)
        else:
            LOG.info(
                "ghost count change requested: %d -> %d; applying at next generation",
                self.agent_count, count,
            )

    def set_adaptive_cpu(self, enabled):
        self.adaptive_cpu = bool(enabled)
        if self.adaptive_cpu:
            self.last_cpu_scale = 0.0

    def set_cpu_target(self, target):
        self.cpu_target = max(20.0, min(95.0, float(target)))

    def set_cpu_min_agents(self, count):
        self.cpu_min_agents = max(1, min(MAX_AGENTS, int(count)))
        if self.cpu_max_agents < self.cpu_min_agents:
            self.cpu_max_agents = self.cpu_min_agents
        self.pending_agent_count = max(self.pending_agent_count, self.cpu_min_agents)

    def set_cpu_max_agents(self, count):
        self.cpu_max_agents = max(self.cpu_min_agents, min(MAX_AGENTS, int(count)))
        self.pending_agent_count = min(self.pending_agent_count, self.cpu_max_agents)

    # ---------- UI ----------

    def ui_command(self, command, value=None):
        if command == "resume":
            self.paused = False
            self.training_enabled = True
        elif command == "pause":
            self.paused = True
        elif command in ("retry", "new_race"):
            self.sim_started = False
        elif command == "single_agent":
            # Keep the button compatible with the UI; ghost simulation always
            # remains 50-agent mode so the player can keep driving normally.
            LOG.info("Single Agent is disabled in ghost-only mode; keeping 50 agents")
        elif command == "load_map":
            if value:
                self.map_name = str(value)
                # This is a map-selection operation, not car control.
                if self.iface is not None:
                    try:
                        self.iface.execute_command(f'map "{self.map_name}"')
                    except Exception as exc:
                        self.last_error = f"map: {type(exc).__name__}: {exc}"
                        LOG.exception("map command failed")
                self.sim_started = False
        elif command == "replay":
            # Replay remains a UI-only trajectory preview.
            pass

    def toggle_camera_sweep(self):
        with self.player_lock:
            self.camera_sweep = not self.camera_sweep

    def set_focus(self, agent_id):
        with self.player_lock:
            self.focus = max(0, min(MAX_AGENTS - 1, int(agent_id)))

    def set_game_speed(self, speed):
        # This is now the detached ghost simulator speed. The actual TMNF game
        # remains at the user's chosen speed.
        self.sim_speed = max(0.1, min(2.0, float(speed)))

    def set_worker_threads(self, count):
        count = max(1, min(16, int(count)))
        old = self.executor
        self.worker_threads = count
        self.executor = ThreadPoolExecutor(max_workers=count)
        old.shutdown(wait=False, cancel_futures=True)

    def start_replay(self, agent_id: int):
        # The Control Center's canvas preview remains the safe replay mechanism.
        self.set_focus(agent_id)

    def replay_snapshot(self, agent_id):
        with self.player_lock:
            a = self.telemetry.agents[
                max(0, min(N - 1, int(agent_id)))
            ]
            return {
                "time": list(a.history_time),
                "x": list(a.history_x),
                "y": list(a.history_y),
                "z": list(a.history_z),
                "speed": list(a.history_speed),
                "steer": list(a.history_steer),
                "gas": list(a.history_gas),
            }

    def find_game_window(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found = []
        proc_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM,
        )

        def callback(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title, length + 1)
            text = title.value.lower()
            if "trackmania" in text and "forever" in text:
                found.append(hwnd)
                return False
            return True

        user32.EnumWindows(proc_type(callback), 0)
        return found[0] if found else None

    def ui_snapshot(self):
        with self.player_lock:
            agents = []
            for a in self.telemetry.agents:
                fitness = self.engine.fitness(
                    a.forward_progress,
                    a.average_speed,
                    a.wall_penalty,
                )
                agents.append({
                    "id": a.agent_id,
                    "alive": a.alive,
                    "speed": a.speed_kmh,
                    "forward_speed": a.forward_speed_kmh,
                    "distance": a.forward_progress,
                    "fitness": fitness,
                    "lap": a.lap,
                    "lap_time": a.latest_lap_time,
                    "avg": a.average_speed,
                    "wall": a.wall_penalty,
                    "front": float(a.lidar[0]),
                    "left": float(a.lidar[1]),
                    "right": float(a.lidar[2]),
                    "steer": a.last_steer,
                    "gas": a.last_gas,
                    "checkpoints": len(a.checkpoint_times),
                })

            f = agents[self.focus]
            return {
                "generation": self.engine.generation,
                "best": self.engine.best_score
                if np.isfinite(self.engine.best_score)
                else 0.0,
                "mean": self.last_summary["mean_fitness"],
                "active": self.telemetry.active_count(),
                "agent_count": self.agent_count,
                "max_agents": MAX_AGENTS,
                "cpu_usage": self.cpu_usage,
                "adaptive_cpu": self.adaptive_cpu,
                "cpu_target": self.cpu_target,
                "cpu_min_agents": self.cpu_min_agents,
                "cpu_max_agents": self.cpu_max_agents,
                "pending_agent_count": self.pending_agent_count,
                "focus": self.focus,
                "focused": f,
                "agents": agents,
                "phase": (
                    "PAUSED" if self.paused else
                    "TRAINING" if self.training_enabled else
                    "STOPPED"
                ),
                "speed_factor": self.sim_speed,
                "ticks": self.training_ticks,
                "last_error": self.last_error,
                "player_control": "OFF — ghost-only",
                "ghost_render": "ON",
            }

    def save_and_stop(self):
        try:
            self.save_now()
        finally:
            self.running = False
            self.autosave_stop.set()
            self.executor.shutdown(wait=False, cancel_futures=True)

    def stop(self):
        self.save_and_stop()


def main():
    trainer = Trainer()
    iface = TMInterface("TMInterface0")
    trainer.iface = iface
    ui = ControlCenter(trainer)

    try:
        iface.register(trainer)
        LOG.info("TMInterface registration requested")
        ui.run()
    finally:
        trainer.stop()
        try:
            iface.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
