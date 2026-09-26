"""Async newline-delimited JSON control server for 50 simultaneous agents."""
from __future__ import annotations
import asyncio, json, logging, pathlib, sys, time
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from core.evolution import EvolutionEngine, AgentResult, fitness_of
from environment.telemetry import parse_frame

CONFIG = json.loads((ROOT / "config" / "hyperparams.json").read_text(encoding="utf-8"))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("tmrl")

class TrainingSession:
    def __init__(self):
        self.n = int(CONFIG["population_size"])
        self.engine = EvolutionEngine(self.n, int(CONFIG["elite_count"]), float(CONFIG["mutation_rate"]), float(CONFIG["mutation_sigma"]), CONFIG.get("random_seed"))
        self.started = time.monotonic()
        self.lock = asyncio.Lock()
        self.generation = 0
        self.high_score = float("-inf")

    def reset_timer(self): self.started = time.monotonic()
    def timed_out(self): return time.monotonic() - self.started >= float(CONFIG["generation_timeout_seconds"])

    def process(self, packet):
        agents = parse_frame(packet, self.n)
        obs = np.stack([a.observation() for a in agents])
        commands, activations = self.engine.commands(obs)
        alive = sum(a.alive for a in agents)
        elapsed = max(0.0, time.monotonic() - self.started)
        generation_end = alive == 0 or self.timed_out() or bool(packet.get("generation_end", False))
        summary = None
        if generation_end:
            fw = CONFIG["fitness"]
            results = []
            for a in agents:
                speed = a.average_speed if a.average_speed is not None else a.speed
                f = fitness_of(a.distance, speed, a.wall_penalty, fw["distance_weight"], fw["speed_weight"], fw["wall_penalty_weight"])
                results.append(AgentResult(f, a.distance, speed, a.wall_penalty, a.alive))
            summary = self.engine.evolve(results)
            self.generation = summary["generation"]
            self.high_score = max(self.high_score, summary["best_fitness"])
            self.reset_timer()
            commands = np.zeros_like(commands)
        return {
            "type":"commands","generation":self.generation,"elapsed":elapsed,"active":alive,
            "high_score":self.high_score,
            "commands":[{"steering":float(c[0]),"throttle":float(c[1])} for c in commands],
            "focused_activations":activations[0].astype(float).tolist(),
            "generation_end":generation_end,"summary":summary
        }

async def handle_client(reader, writer, session):
    peer = writer.get_extra_info("peername")
    LOG.info("client connected: %s", peer)
    try:
        while not reader.at_eof():
            raw = await reader.readline()
            if not raw: break
            try:
                if len(raw) > 2_000_000: raise ValueError("packet exceeds 2 MB limit")
                packet = json.loads(raw)
                async with session.lock: response = session.process(packet)
                writer.write((json.dumps(response, separators=(",",":")) + "\n").encode())
                await writer.drain()
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                writer.write((json.dumps({"type":"error","error":str(exc)}) + "\n").encode())
                await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError, asyncio.CancelledError):
        pass
    finally:
        writer.close()
        try: await writer.wait_closed()
        except Exception: pass
        LOG.info("client disconnected: %s", peer)

async def main():
    server = await asyncio.start_server(lambda r,w: handle_client(r,w,TrainingSession()), CONFIG["server_host"], int(CONFIG["server_port"]), limit=2_500_000)
    LOG.info("TMRL listening on %s", ", ".join(str(s.getsockname()) for s in server.sockets or []))
    async with server: await server.serve_forever()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: LOG.info("server stopped")
