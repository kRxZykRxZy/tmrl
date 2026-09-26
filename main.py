"""TMRL 50-instance TMInterface coordinator.

The legacy official Python client controls one TMInterface server at a time, but
its API permits multiple server connections from one process. We therefore run
one TMNF/TMInterface instance per genome and perform one vectorized population
inference over the latest 50 observations.
"""
from __future__ import annotations
import json, logging, threading, time
from pathlib import Path
import numpy as np

from core.network import NeuralNetwork
from core.evolution import EvolutionEngine, FitnessResult
from environment.telemetry import TelemetryStore
from ui.standalone_ui import StandaloneHUD

try:
    from tminterface.client import Client
    from tminterface.interface import TMInterface
except ImportError as exc:
    raise SystemExit("Install the legacy TMInterface client with: python -m pip install tminterface==1.0.2") from exc

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config" / "hyperparams.json").read_text(encoding="utf-8"))
POPULATION = int(CFG["population_size"])
SERVER_PREFIX = str(CFG.get("server_prefix", "TMInterface"))
TICK_HZ = float(CFG.get("inference_hz", 60.0))
LOG = logging.getLogger("tmrl")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(threadName)s %(message)s")

class Coordinator:
    def __init__(self):
        self.telemetry = TelemetryStore(POPULATION)
        self.engine = EvolutionEngine(
            NeuralNetwork.population(POPULATION, np.random.default_rng(CFG.get("random_seed"))),
            elite_count=int(CFG["elite_count"]),
            mutation_rate=float(CFG["mutation_rate"]),
            mutation_sigma=float(CFG["mutation_sigma"]),
            seed=CFG.get("random_seed"),
        )
        self.interfaces: list[TMInterface | None] = [None] * POPULATION
        self.observations = np.zeros((POPULATION, 8), dtype=np.float32)
        self.commands = np.zeros((POPULATION, 2), dtype=np.float32)
        self.activations = np.zeros((POPULATION, 24), dtype=np.float32)
        self.focus = 0
        self.generation_started = time.monotonic()
        self.generation_lock = threading.RLock()
        self.inference_condition = threading.Condition()
        self.running = True
        self.resetting = False
        self.last_summary = {"generation": 0, "best_fitness": 0.0, "survival_rate": 0.0}
        self.inference_thread = threading.Thread(target=self._inference_loop, name="tmrl-inference", daemon=True)

    def start(self):
        self.inference_thread.start()

    def observe(self, agent_id: int, iface: TMInterface):
        state = iface.get_simulation_state()
        self.telemetry.update(agent_id, state)
        with self.inference_condition:
            self.observations[agent_id] = self.telemetry.observation(agent_id)
            self.inference_condition.notify()

    def action(self, agent_id: int, iface: TMInterface):
        with self.inference_condition:
            command = self.commands[agent_id].copy()
            alive = self.telemetry.agents[agent_id].alive
        if alive:
            steer = int(np.clip(command[0], -1.0, 1.0) * 65536.0)
            gas = int(np.clip(command[1], -1.0, 1.0) * 65536.0)
        else:
            steer = gas = 0
        iface.set_input_state(
            sim_clear_buffer=False,
            steer=steer,
            gas=gas,
            accelerate=gas > 0,
            brake=gas < 0,
        )

    def _inference_loop(self):
        period = 1.0 / max(1.0, TICK_HZ)
        next_tick = time.perf_counter()
        while self.running:
            now = time.perf_counter()
            if now < next_tick:
                time.sleep(min(next_tick - now, 0.002))
                continue
            next_tick += period
            with self.inference_condition:
                obs = self.observations.copy()
            try:
                out, _h1, h2 = self.engine.batch_forward(obs)
                with self.inference_condition:
                    self.commands[:] = out
                    self.activations[:] = h2
                    for i, agent in enumerate(self.telemetry.agents):
                        agent.activations[:] = h2[i]
            except Exception:
                LOG.exception("population inference failed")

    def step(self, agent_id: int, iface: TMInterface):
        try:
            if iface.is_in_menus():
                return
            self.observe(agent_id, iface)
            self.action(agent_id, iface)
            self.maybe_end_generation()
        except Exception:
            LOG.exception("agent %02d physics callback failed", agent_id)

    def maybe_end_generation(self):
        with self.generation_lock:
            if self.resetting:
                return
            timeout = time.monotonic() - self.generation_started >= float(CFG["generation_timeout_seconds"])
            all_crashed = self.telemetry.active_count() == 0
            if not (timeout or all_crashed):
                return

            self.resetting = True
            try:
                results = []
                for agent in self.telemetry.agents:
                    results.append(
                        FitnessResult(
                            fitness=self.engine.fitness(
                                agent.max_distance,
                                agent.average_speed,
                                agent.wall_penalty,
                            ),
                            distance=agent.max_distance,
                            average_speed=agent.average_speed,
                            wall_penalty=agent.wall_penalty,
                            survived=agent.alive,
                        )
                    )

                self.last_summary = self.engine.evolve(results)
                self.generation_started = time.monotonic()

                LOG.info(
                    "generation=%d best=%.3f mean=%.3f survival=%.1f%%",
                    self.last_summary["generation"],
                    self.last_summary["best_fitness"],
                    self.last_summary["mean_fitness"],
                    self.last_summary["survival_rate"] * 100.0,
                )

                for agent in self.telemetry.agents:
                    agent.reset()

                with self.inference_condition:
                    self.observations.fill(0.0)
                    self.commands.fill(0.0)
                    self.activations.fill(0.0)

                for iface in self.interfaces:
                    if iface is None or not iface.running:
                        continue
                    try:
                        iface.execute_command("press system retry")
                    except Exception:
                        LOG.exception("generation retry command failed")

            finally:
                self.resetting = False

    def snapshot(self):
        with self.generation_lock:
            agent = self.telemetry.agents[self.focus]
            return {
                "generation": self.engine.generation,
                "best": self.engine.best_score if np.isfinite(self.engine.best_score) else 0.0,
                "active": self.telemetry.active_count(),
                "focus": self.focus,
                "speed": agent.speed_kmh,
                "distance": agent.max_distance,
                "fitness": self.engine.fitness(agent.max_distance, agent.average_speed, agent.wall_penalty),
                "front": agent.lidar[0],
                "left": agent.lidar[1],
                "right": agent.lidar[2],
                "activations": agent.activations.copy(),
            }

    def ui_event(self, event):
        if event[0] == "focus_delta":
            with self.generation_lock:
                self.focus = (self.focus + int(event[1])) % POPULATION
        return self.snapshot()

class AgentClient(Client):
    def __init__(self, coordinator: Coordinator, agent_id: int):
        super().__init__()
        self.coordinator = coordinator
        self.agent_id = agent_id

    def on_registered(self, iface):
        self.coordinator.interfaces[self.agent_id] = iface
        iface.set_speed(1.0)
        iface.set_timeout(int(CFG.get("tmi_timeout_ms", 5000)))
        LOG.info("agent %02d registered", self.agent_id)

    def on_run_step(self, iface, _time):
        self.coordinator.step(self.agent_id, iface)

    def on_deregistered(self, iface):
        LOG.warning("agent %02d deregistered", self.agent_id)

    def on_shutdown(self, iface):
        LOG.warning("agent %02d server shut down", self.agent_id)

    def on_client_exception(self, iface, exception):
        LOG.error("agent %02d client exception: %s", self.agent_id, exception)

def connect_agent(coordinator: Coordinator, agent_id: int):
    server_name = f"{SERVER_PREFIX}{agent_id}"
    while coordinator.running:
        iface = TMInterface(server_name)
        client = AgentClient(coordinator, agent_id)
        try:
            LOG.info("connecting agent %02d to %s", agent_id, server_name)
            iface.register(client)
            while iface.running and coordinator.running:
                time.sleep(0.1)
        except Exception:
            LOG.exception("agent %02d connection failure", agent_id)
        finally:
            try:
                iface.close()
            except Exception:
                pass
        if coordinator.running:
            time.sleep(float(CFG.get("reconnect_delay_seconds", 2.0)))

def main():
    coordinator = Coordinator()
    coordinator.start()
    workers = [
        threading.Thread(
            target=connect_agent,
            args=(coordinator, agent_id),
            name=f"tmrl-agent-{agent_id:02d}",
            daemon=True,
        )
        for agent_id in range(POPULATION)
    ]
    for worker in workers:
        worker.start()

    LOG.info("started %d TMInterface agent workers", POPULATION)
    StandaloneHUD(coordinator.ui_event).run()
    coordinator.running = False

if __name__ == "__main__":
    main()
