"""Async newline-delimited JSON control server for 50 simultaneous agents."""
from __future__ import annotations
import asyncio
import json
import logging
import pathlib
import time
import numpy as np

from core.evolution import EvolutionEngine, AgentResult, fitness_of
from environment.telemetry import parse_frame

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "config" / "hyperparams.json").read_text(encoding="utf-8"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("tmrl")

class TrainingSession:
    def __init__(self):
        self.n = int(CONFIG["population_size"])
        self.engine = EvolutionEngine(
            population_size=self.n,
            elite_count=int(CONFIG["elite_count"]),
            mutation_rate=float(CONFIG["mutation_rate"]),
            mutation_sigma=float(CONFIG["mutation_sigma"]),
            seed=CONFIG.get("random_seed"),
        )
        self.started = time.monotonic()
        self.last_frame = self.started
        self.lock = asyncio.Lock()
        self.generation = 0
        self.high_score = float("-inf")
        self.last_commands = np.zeros((self.n, 2), dtype=np.float32)

    def reset_timer(self):
        self.started = time.monotonic()

    def timed_out(self):
        return time.monotonic() - self.started >= float(CONFIG["generation_timeout_seconds"])

    def process(self, packet):
        agents = parse_frame(packet, self.n)
        obs = np.stack([a.observation() for a in agents])
        commands, activations = self.engine.commands(obs)
        self.last_commands = commands
        alive = sum(a.alive for a in agents)
        elapsed = max(0.0, time.monotonic() - self.started)
        generation_end = alive == 0 or self.timed_out() or bool(packet.get("generation_end", False))
        result = None
        if generation_end:
            results = []
            fw = CONFIG["fitness"]
            for a in agents:
                f = fitness_of(a.distance, a.speed, a.wall_penalty,
                               fw["distance_weight"], fw["speed_weight"], fw["wall_penalty_weight"])
                results.append(AgentResult(f, a.distance, a.speed, a.wall_penalty, a.alive))
            result = self.engine.evolve(results)
            self.generation = result["generation"]
            self.high_score = max(self.high_score, result["best_fitness"])
            self.reset_timer()
            commands = np.zeros_like(commands)
        self.last_frame = time.monotonic()
        return {
            "type": "commands",
            "generation": self.generation,
            "elapsed": elapsed,
            "active": alive,
            "commands": [{"steering": float(c[0]), "throttle": float(c[1])} for c in commands],
            "focused_activations": activations[0].astype(float).tolist(),
            "generation_end": generation_end,
            "summary": result,
        }

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, session: TrainingSession):
    peer = writer.get_extra_info("peername")
    LOG.info("client connected: %s", peer)
    try:
        while not reader.at_eof():
            raw = await reader.readline()
            if not raw:
                break
            if len(raw) > 2_000_000:
                raise ValueError("packet exceeds 2 MB limit")
            try:
                packet = json.loads(raw)
                async with session.lock:
                    response = session.process(packet)
                writer.write((json.dumps(response, separators=(",", ":")) + "\n").encode())
                await writer.drain()
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                error = {"type": "error", "error": str(exc)}
                writer.write((json.dumps(error) + "\n").encode())
                await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError, asyncio.CancelledError):
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        LOG.info("client disconnected: %s", peer)

async def main():
    host = CONFIG["server_host"]
    port = int(CONFIG["server_port"])
    session = TrainingSession()
    server = await asyncio.start_server(lambda r, w: handle_client(r, w, session), host, port, limit=2_500_000)
    sockets = ", ".join(str(s.getsockname()) for s in server.sockets or [])
    LOG.info("TMRL evolutionary server listening on %s", sockets)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        LOG.info("server stopped")
