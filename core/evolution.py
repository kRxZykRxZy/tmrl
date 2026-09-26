"""Population-level genetic engine."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass
class FitnessResult:
    fitness: float
    distance: float
    average_speed: float
    wall_penalty: float
    survived: bool

class EvolutionEngine:
    def __init__(self, population, elite_count=5, mutation_rate=.15, mutation_sigma=.15, seed=None):
        self.population = np.asarray(population, dtype=np.float32).copy()
        self.size, self.genome_size = self.population.shape
        self.elite_count = int(elite_count)
        self.mutation_rate = float(mutation_rate)
        self.mutation_sigma = float(mutation_sigma)
        self.rng = np.random.default_rng(seed)
        self.generation = 0
        self.best_score = -np.inf
        self.best_agent = 0

    def fitness(self, distance, average_speed, wall_penalty):
        return float(distance * 1.5 + average_speed * 0.5 - wall_penalty)

    def _evolve_slice(self, results, active_size):
        active_size = max(1, min(int(active_size), self.size))
        if len(results) != active_size:
            raise ValueError(f"expected {active_size} fitness results, got {len(results)}")

        fitness = np.asarray([r.fitness for r in results], np.float64)
        order = np.argsort(fitness)[::-1]
        elite_n = 1 if active_size == 1 else max(1, min(self.elite_count, active_size - 1))

        elites = self.population[:active_size][order[:elite_n]].copy()
        best_idx = int(order[0])
        self.best_score = max(self.best_score, float(fitness[best_idx]))
        self.best_agent = best_idx

        new_active = np.empty((active_size, self.genome_size), dtype=np.float32)
        new_active[:elite_n] = elites

        if active_size > elite_n:
            elite_fit = fitness[order[:elite_n]]
            shifted = elite_fit - elite_fit.min()
            probs = shifted + 1e-9
            probs /= probs.sum()

            parents = self.rng.choice(
                elite_n,
                active_size - elite_n,
                replace=True,
                p=probs,
            )
            for dst, parent in enumerate(parents, start=elite_n):
                child = elites[parent].copy()
                mask = self.rng.random(self.genome_size) < self.mutation_rate
                if np.any(mask):
                    child[mask] += self.rng.normal(
                        0,
                        self.mutation_sigma,
                        int(mask.sum()),
                    ).astype(np.float32)
                new_active[dst] = child

        self.population[:active_size] = new_active
        self.generation += 1

        return {
            "generation": self.generation,
            "best_fitness": float(fitness[best_idx]),
            "mean_fitness": float(fitness.mean()),
            "survival_rate": float(sum(r.survived for r in results) / active_size),
            "best_agent": self.best_agent,
            "agent_count": active_size,
        }

    def evolve(self, results):
        return self._evolve_slice(results, self.size)

    def evolve_subset(self, results, active_size):
        return self._evolve_slice(results, active_size)

    def batch_forward(self, observations):
        x = np.asarray(observations, np.float32)
        if x.ndim != 2 or x.shape[1] != 8:
            raise ValueError(f"expected (N, 8), got {x.shape}")

        count = x.shape[0]
        if count < 1 or count > self.size:
            raise ValueError(f"expected 1..{self.size} agents, got {count}")

        w1 = self.population[:count, :256].reshape(count, 8, 32)
        b1 = self.population[:count, 256:288]
        w2 = self.population[:count, 288:1056].reshape(count, 32, 24)
        b2 = self.population[:count, 1056:1080]
        w3 = self.population[:count, 1080:1128].reshape(count, 24, 2)
        b3 = self.population[:count, 1128:1130]

        h1 = np.maximum(np.einsum("pi,pij->pj", x, w1) + b1, 0)
        h2 = np.maximum(np.einsum("pi,pij->pj", h1, w2) + b2, 0)
        return np.tanh(np.einsum("pi,pij->pj", h2, w3) + b3), h1, h2
