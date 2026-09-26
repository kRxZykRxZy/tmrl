"""Single-TMInterface, 50-virtual-agent evolutionary trainer.

Important architecture:
- exactly ONE TMNF/TMInterface process;
- 50 independent logical trajectories are stored as TMInterface simulation states;
- the trainer time-slices those states through the one physics process;
- only the currently rendered trajectory can appear in the actual TMNF camera;
- every trajectory has its own genome, telemetry, replay history and recovery state.
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

from core.evolution import EvolutionEngine, FitnessResult
from core.network import NeuralNetwork
from environment.telemetry import AgentTelemetry, TelemetryStore
from training.checkpoint_manager import CheckpointManager
from ui.control_center import ControlCenter

try:
    from tminterface.client import Client
    from tminterface.interface import TMInterface
    from tminterface.structs import SimStateData, CheckpointData
except ImportError as exc:
    raise SystemExit("Install: python -m pip install -r requirements.txt") from exc

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config" / "hyperparams.json").read_text(encoding="utf-8"))
N = int(CFG["population_size"])
LOG = logging.getLogger("tmrl")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def clone_state(state: SimStateData) -> SimStateData:
    return copy.deepcopy(state)


def decode_state(blob: bytes):
    if not blob:
        return None
    try:
        state = SimStateData(blob)
        state.cp_data.resize(CheckpointData.cp_states_field, state.cp_data.cp_states_length)
        state.cp_data.resize(CheckpointData.cp_times_field, state.cp_data.cp_times_length)
        return state
    except Exception as exc:
        LOG.warning("could not decode persisted TMInterface state: %s", exc)
        return None


class Trainer(Client):
    def __init__(self):
        super().__init__()
        self.telemetry = TelemetryStore(N)
        seed = CFG.get("random_seed")
        rng = np.random.default_rng(seed)
        population = NeuralNetwork.population(N, rng)
        self.engine = EvolutionEngine(
            population,
            elite_count=int(CFG["elite_count"]),
            mutation_rate=float(CFG["mutation_rate"]),
            mutation_sigma=float(CFG["mutation_sigma"]),
            seed=seed,
        )

        self.checkpoints = CheckpointManager(ROOT / "checkpoints", N)
        self.executor = ThreadPoolExecutor(max_workers=int(CFG.get("worker_threads", 2)))
        self.iface: TMInterface | None = None
        self.running = True
        self.training_enabled = True
        self.single_agent_mode = False
        self.map_name = str(CFG.get("map_name", ""))
        self.game_speed = float(CFG.get("training_game_speed", 50.0))
        self.worker_threads = int(CFG.get("worker_threads", 2))
        self.focus = 0
        self.current_agent = 0
        self.phase = "advance"
        self.initialized = False
        self.generation_started = time.monotonic()
        self.last_autosave = 0.0
        self.last_summary = {"generation": 0, "best_fitness": 0.0, "mean_fitness": 0.0, "survival_rate": 0.0}

        # One saved simulation state and one last-known safe state per logical car.
        self.states: list[SimStateData | None] = [None] * N
        self.safe_states: list[SimStateData | None] = [None] * N
        self.generation_start_state: SimStateData | None = None

        self.paused = False
        self.replay_mode = False
        self.replay_agent = 0
        self.replay_index = 0
        self.replay_active = False
        self.camera_request = 0
        self.lock = threading.RLock()

    # ---------- lifecycle ----------

    def on_registered(self, iface):
        self.iface = iface
        iface.set_timeout(int(CFG.get("tmi_timeout_ms", 5000)))
        iface.set_speed(self.game_speed)
        LOG.info("connected to ONE TMInterface instance")
        LOG.info("50 logical cars will be multiplexed through this process")
        self._load_persisted_population()

    def on_shutdown(self, iface):
        self.running = False

    def on_deregistered(self, iface):
        self.running = False

    def on_client_exception(self, iface, exception):
        LOG.error("TMInterface exception: %s", exception)

    # ---------- initialization / persistence ----------

    def _load_persisted_population(self):
        data = self.checkpoints.load_population()
        if data is None:
            return
        pop = data["population"]
        if pop.shape == self.engine.population.shape:
            self.engine.population[:] = pop
            self.engine.generation = data["generation"]
            self.engine.best_score = data["best_score"]
            self.map_name = data["map_name"] or self.map_name
            LOG.info("loaded population checkpoint at generation %d", self.engine.generation)

        for agent in self.telemetry.agents:
            self.checkpoints.load_agent(agent)

    def _initialize_from_live_state(self, live_state):
        with self.lock:
            self.generation_start_state = clone_state(live_state)
            for i, agent in enumerate(self.telemetry.agents):
                loaded = decode_state(agent.state_blob)
                self.states[i] = loaded if loaded is not None else clone_state(live_state)
                self.safe_states[i] = clone_state(self.states[i])
            self.current_agent = self.focus
            self.phase = "advance"
            self.initialized = True
            self.generation_started = time.monotonic()
            LOG.info("initialized 50 virtual trajectories from current TMNF race state")

    def save_now(self):
        with self.lock:
            population = self.engine.population.copy()
            generation = self.engine.generation
            best = self.engine.best_score
            map_name = self.map_name
            agents = [(copy.deepcopy(a), population[a.agent_id].copy()) for a in self.telemetry.agents]
        self.executor.submit(self.checkpoints.save_population, population, generation, best, map_name)
        for agent, genome in agents:
            self.executor.submit(self.checkpoints.save_agent, agent, genome)
        self.checkpoints.manifest(generation, map_name)

    def _autosave(self):
        now = time.monotonic()
        if now - self.last_autosave < float(CFG.get("autosave_seconds", 2.0)):
            return
        self.last_autosave = now
        self.save_now()

    # ---------- simulation ----------

    def _population_commands(self):
        observations = self.telemetry.observation_matrix(
            float(CFG.get("speed_limit_kmh", 300.0)),
            float(CFG.get("position_scale", 1000.0)),
        )
        commands, _h1, h2 = self.engine.batch_forward(observations)
        for i, agent in enumerate(self.telemetry.agents):
            agent.activations[:] = h2[i]
        return commands

    def _issue_action(self, agent_id: int):
        if self.iface is None:
            return
        agent = self.telemetry.agents[agent_id]
        if not self.training_enabled or self.paused:
            steer_norm = 0.0
            gas_norm = 0.0
        elif self.replay_active and agent_id == self.replay_agent:
            hist = agent.history_steer
            gas = agent.history_gas
            idx = min(self.replay_index, max(0, len(hist) - 1))
            steer_norm = hist[idx] if hist else 0.0
            gas_norm = gas[idx] if gas else 0.0
        else:
            commands = self._population_commands()
            steer_norm = float(np.clip(commands[agent_id, 0], -1.0, 1.0))
            gas_norm = float(np.clip(commands[agent_id, 1], -1.0, 1.0))

        self.iface.set_input_state(
            sim_clear_buffer=False,
            steer=int(steer_norm * 65536),
            gas=int(gas_norm * 65536),
            accelerate=gas_norm > 0,
            brake=gas_norm < 0,
        )
        agent.record_action(steer_norm, gas_norm)

    def _is_bad_state(self, agent: AgentTelemetry) -> bool:
        y = float(agent.position[1])
        x = abs(float(agent.position[0]))
        z = abs(float(agent.position[2]))

        if y < float(CFG.get("fall_y_min", -40.0)):
            return True
        if x > float(CFG.get("map_abs_coordinate_limit", 5000.0)):
            return True
        if z > float(CFG.get("map_abs_coordinate_limit", 5000.0)):
            return True

        if agent.samples < 2:
            return False

        stuck_ms = int(CFG.get("stuck_timeout_ms", 1500))
        movement_eps = float(CFG.get("movement_epsilon", 0.05))
        speed_threshold = float(CFG.get("stuck_speed_kmh", 1.0))
        previous = np.asarray(getattr(agent, "_last_recovery_position", agent.position))
        moved = float(np.linalg.norm(agent.position - previous))
        if moved > movement_eps or agent.speed_kmh > speed_threshold:
            agent._last_recovery_position = agent.position.copy()
            agent._last_movement_ms = agent.race_time_ms
            return False
        last_movement = int(getattr(agent, "_last_movement_ms", agent.race_time_ms))
        return agent.race_time_ms - last_movement >= stuck_ms

    def _recover_agent(self, agent_id: int):
        state = self.safe_states[agent_id] or self.states[agent_id] or self.generation_start_state
        if state is None or self.iface is None:
            return
        agent = self.telemetry.agents[agent_id]
        agent.recoveries = getattr(agent, "recoveries", 0) + 1
        self.iface.rewind_to_state(clone_state(state))
        agent.below_speed_since_ms = -1
        agent.alive = True
        agent.crashed = False
        agent.lidar.fill(1.0)

    def _store_progress_state(self, agent_id: int, state):
        agent = self.telemetry.agents[agent_id]
        min_progress = float(CFG.get("safe_state_distance", 2.0))
        if agent.max_distance - getattr(agent, "_last_safe_distance", -1.0) >= min_progress:
            self.safe_states[agent_id] = clone_state(state)
            agent._last_safe_distance = agent.max_distance

    def _evolve_generation(self):
        results = []
        for agent in self.telemetry.agents:
            results.append(
                FitnessResult(
                    fitness=self.engine.fitness(agent.max_distance, agent.average_speed, agent.wall_penalty),
                    distance=agent.max_distance,
                    average_speed=agent.average_speed,
                    wall_penalty=agent.wall_penalty,
                    survived=agent.alive,
                )
            )
        self.last_summary = self.engine.evolve(results)
        LOG.info(
            "generation %d best %.3f mean %.3f survival %.1f%%",
            self.engine.generation,
            self.last_summary["best_fitness"],
            self.last_summary["mean_fitness"],
            self.last_summary["survival_rate"] * 100,
        )

        base = self.generation_start_state
        if base is not None:
            for i, agent in enumerate(self.telemetry.agents):
                self.states[i] = clone_state(base)
                self.safe_states[i] = clone_state(base)
                agent.reset()
        self.current_agent = self.focus
        self.phase = "advance"
        self.generation_started = time.monotonic()

    def _generation_finished(self):
        timeout = time.monotonic() - self.generation_started >= float(CFG["generation_timeout_seconds"])
        all_dead = self.telemetry.active_count() == 0
        return timeout or all_dead

    def on_run_step(self, iface, _time):
        with self.lock:
            if not self.initialized:
                live = iface.get_simulation_state()
                self._initialize_from_live_state(live)

            agent_id = self.current_agent
            agent = self.telemetry.agents[agent_id]
            state = iface.get_simulation_state()

            # This callback is the post-action state for the current logical car.
            if self.phase == "advance":
                blob = bytes(state.data)
                self.telemetry.update(agent_id, state, blob)
                self.states[agent_id] = clone_state(state)
                self._store_progress_state(agent_id, state)

                if self._is_bad_state(agent):
                    self._recover_agent(agent_id)

                if self.reset_requested:
                    self.reset_requested = False
                    self._reset_all_states()
                    base = self.generation_start_state
                    if base is not None:
                        self.iface.rewind_to_state(clone_state(base))
                    self.phase = "advance"
                    return

                if self._generation_finished():
                    self._evolve_generation()
                    base = self.generation_start_state
                    if base is not None:
                        self.iface.rewind_to_state(clone_state(base))
                    self.phase = "advance"
                    self._autosave()
                    return

                if self.replay_active:
                    self.replay_index += 1
                    if self.replay_index >= len(agent.history_time):
                        self.replay_active = False
                        self.training_enabled = True

                self._autosave()

                # Advance this logical car with a new action on this callback.
                self._issue_action(agent_id)
                self.phase = "post"
                return

            # The previous callback injected the current agent's command. We now
            # retain the resulting state, then rewind the single game to the next
            # logical agent. rewind_to_state() immediately simulates its next step.
            blob = bytes(state.data)
            self.telemetry.update(agent_id, state, blob)
            self.states[agent_id] = clone_state(state)
            self._store_progress_state(agent_id, state)

            if self._is_bad_state(agent):
                self._recover_agent(agent_id)
                self.current_agent = agent_id
                self.phase = "advance"
                return

            if self.reset_requested:
                self.reset_requested = False
                self._reset_all_states()
                base = self.generation_start_state
                if base is not None:
                    self.iface.rewind_to_state(clone_state(base))
                self.phase = "advance"
                return

            if self._generation_finished():
                self._evolve_generation()
                base = self.generation_start_state
                if base is not None:
                    self.iface.rewind_to_state(clone_state(base))
                self.phase = "advance"
                return

            if self.single_agent_mode:
                next_agent = self.focus
            else:
                next_agent = (agent_id + 1) % N

            # A requested camera focus changes which logical state gets rendered next.
            if self.camera_request is not None:
                requested = int(self.camera_request)
                if 0 <= requested < N:
                    next_agent = requested
                self.camera_request = None

            next_state = self.states[next_agent] or self.generation_start_state
            if next_state is not None:
                self.current_agent = next_agent
                self.iface.rewind_to_state(clone_state(next_state))
                self.phase = "advance"

    # ---------- UI / controls ----------

    def ui_command(self, command, value=None):
        with self.lock:
            if command == "resume":
                self.paused = False
                self.training_enabled = True
            elif command == "pause":
                self.paused = True
            elif command == "retry":
                self.reset_requested = True
            elif command == "new_race":
                self.initialized = False
                for agent in self.telemetry.agents:
                    agent.state_blob = b""
                self._safe_tm_command("press delete")
            elif command == "single_agent":
                self.single_agent_mode = not self.single_agent_mode
            elif command == "load_map":
                if value:
                    self.map_name = str(value)
                    self._safe_tm_command(f'map "{self.map_name}"')
                    for agent in self.telemetry.agents:
                        agent.state_blob = b""
                    self.initialized = False
            elif command == "replay":
                self.start_replay(int(value) if value is not None else self.focus)

    def _safe_tm_command(self, command):
        if self.iface is not None:
            try:
                self.iface.execute_command(command)
            except Exception:
                LOG.exception("TMInterface command failed: %s", command)

    def _reset_all_states(self):
        if self.generation_start_state is None:
            return
        for i, agent in enumerate(self.telemetry.agents):
            self.states[i] = clone_state(self.generation_start_state)
            self.safe_states[i] = clone_state(self.generation_start_state)
            agent.reset()
        self.current_agent = self.focus
        self.phase = "advance"

    def start_replay(self, agent_id: int):
        with self.lock:
            self.replay_agent = max(0, min(N - 1, int(agent_id)))
            self.focus = self.replay_agent
            self.replay_index = 0
            self.replay_active = bool(self.telemetry.agents[self.replay_agent].history_time)
            self.training_enabled = not self.replay_active
            self.camera_request = self.replay_agent
            self.current_agent = self.replay_agent
            if self.replay_active and self.generation_start_state is not None:
                self.states[self.replay_agent] = clone_state(self.generation_start_state)
                self.safe_states[self.replay_agent] = clone_state(self.generation_start_state)
                self.telemetry.agents[self.replay_agent].reset(keep_history=True)

    def set_focus(self, agent_id):
        with self.lock:
            self.focus = max(0, min(N - 1, int(agent_id)))
            self.camera_request = self.focus

    def set_game_speed(self, speed):
        self.game_speed = max(0.1, min(100.0, float(speed)))
        if self.iface is not None:
            self.iface.set_speed(self.game_speed)

    def set_worker_threads(self, count):
        count = max(1, min(16, int(count)))
        old = self.executor
        self.worker_threads = count
        self.executor = ThreadPoolExecutor(max_workers=count)
        old.shutdown(wait=False, cancel_futures=True)

    def find_game_window(self):
        import ctypes
        return ctypes.windll.user32.FindWindowW(None, "TrackMania Nations Forever")

    def ui_snapshot(self):
        with self.lock:
            def one(agent):
                return {
                    "id": agent.agent_id,
                    "alive": agent.alive,
                    "speed": agent.speed_kmh,
                    "distance": agent.max_distance,
                    "fitness": self.engine.fitness(agent.max_distance, agent.average_speed, agent.wall_penalty),
                    "lap": agent.lap,
                    "lap_time": agent.latest_lap_time,
                    "avg": agent.average_speed,
                    "wall": agent.wall_penalty,
                    "front": float(agent.lidar[0]),
                    "left": float(agent.lidar[1]),
                    "right": float(agent.lidar[2]),
                    "steer": agent.last_steer,
                    "gas": agent.last_gas,
                    "checkpoints": len(agent.checkpoint_times),
                    "recoveries": getattr(agent, "recoveries", 0),
                }

            agents = [one(a) for a in self.telemetry.agents]
            f = agents[self.focus]
            return {
                "generation": self.engine.generation,
                "best": self.engine.best_score if np.isfinite(self.engine.best_score) else 0.0,
                "mean": self.last_summary.get("mean_fitness", 0.0),
                "active": self.telemetry.active_count(),
                "focus": self.focus,
                "focused": f,
                "agents": agents,
                "phase": "PAUSED" if self.paused else ("REPLAY" if self.replay_active else "TRAINING"),
                "speed_factor": self.game_speed,
            }

    def replay_snapshot(self, agent_id):
        with self.lock:
            a = self.telemetry.agents[max(0, min(N - 1, int(agent_id)))]
            return {
                "time": list(a.history_time),
                "x": list(a.history_x),
                "y": list(a.history_y),
                "z": list(a.history_z),
                "speed": list(a.history_speed),
                "steer": list(a.history_steer),
                "gas": list(a.history_gas),
            }

    def save_and_stop(self):
        try:
            self.save_now()
        finally:
            self.running = False
            self.executor.shutdown(wait=False, cancel_futures=True)

    def stop(self):
        self.save_and_stop()


def main():
    trainer = Trainer()
    iface = TMInterface("TMInterface0")
    trainer.iface = iface
    iface.register(trainer)
    ui = ControlCenter(trainer)
    try:
        ui.run()
    finally:
        trainer.stop()
        try:
            iface.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
