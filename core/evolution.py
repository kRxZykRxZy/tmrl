"""Deterministic, testable evolutionary population engine."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .network import NeuralNetwork

@dataclass
class AgentResult:
    fitness: float
    distance: float
    average_speed: float
    wall_penalty: float
    survived: bool

def fitness_of(distance, average_speed, wall_penalty, distance_weight=1.5, speed_weight=0.5, wall_penalty_weight=1.0):
    return distance * distance_weight + average_speed * speed_weight - wall_penalty * wall_penalty_weight

class EvolutionEngine:
    def __init__(self, population_size=50, elite_count=5, mutation_rate=0.15, mutation_sigma=0.15, seed=None):
        if elite_count <= 0 or elite_count >= population_size:
            raise ValueError("elite_count must be between 1 and population_size-1")
        self.population_size, self.elite_count = population_size, elite_count
        self.mutation_rate, self.mutation_sigma = mutation_rate, mutation_sigma
        self.rng = np.random.default_rng(seed)
        self.population = NeuralNetwork.population(population_size, self.rng)
        self.generation, self.best_ever = 0, -np.inf
        self.best_params = self.population[0].copy()

    def _roulette(self, fitness, count):
        f = np.asarray(fitness, dtype=np.float64)
        shifted = f - np.min(f)
        weights = shifted + max(np.finfo(np.float64).eps, np.mean(shifted) * 1e-6)
        if not np.isfinite(weights.sum()) or weights.sum() <= 0:
            return self.rng.integers(0, len(f), size=count)
        return self.rng.choice(len(f), size=count, replace=True, p=weights / weights.sum())

    def evolve(self, results):
        fitness = np.asarray(results if isinstance(results, np.ndarray) else [r.fitness for r in results], dtype=np.float64)
        if fitness.shape != (self.population_size,):
            raise ValueError("fitness array must contain exactly one value per agent")
        order = np.argsort(fitness)[::-1]
        elite_indices = order[:self.elite_count]
        elites = self.population[elite_indices].copy()
        if fitness[order[0]] > self.best_ever:
            self.best_ever = float(fitness[order[0]])
            self.best_params = elites[0].copy()

        # Every non-elite child is cloned from one of the five elite parents.
        elite_fitness = fitness[elite_indices]
        parent_slots = self._roulette(elite_fitness, self.population_size - self.elite_count)
        new_population = np.empty_like(self.population)
        new_population[:self.elite_count] = elites
        for out_i, elite_slot in enumerate(parent_slots, self.elite_count):
            child = elites[elite_slot].copy()
            mask = self.rng.random(child.size) < self.mutation_rate
            if np.any(mask):
                child[mask] += self.rng.normal(0.0, self.mutation_sigma, int(mask.sum())).astype(np.float32)
            new_population[out_i] = child
        self.population = new_population
        self.generation += 1
        return {
            "generation": self.generation,
            "best_fitness": float(fitness[order[0]]),
            "mean_fitness": float(np.mean(fitness)),
            "worst_fitness": float(fitness[order[-1]]),
            "elite_indices": elite_indices.tolist(),
            "survival_rate": float(np.count_nonzero([r.survived for r in results]) / self.population_size) if not isinstance(results, np.ndarray) else float(np.count_nonzero(fitness > 0) / self.population_size),
        }

    def commands(self, observations):
        x = np.asarray(observations, dtype=np.float32)
        if x.shape != (self.population_size, NeuralNetwork.input_size):
            raise ValueError(f"expected {(self.population_size, NeuralNetwork.input_size)}, got {x.shape}")
        w1 = self.population[:, :256].reshape(self.population_size, 8, 32)
        b1 = self.population[:, 256:288]
        w2 = self.population[:, 288:1056].reshape(self.population_size, 32, 24)
        b2 = self.population[:, 1056:1080]
        w3 = self.population[:, 1080:1128].reshape(self.population_size, 24, 2)
        b3 = self.population[:, 1128:1130]
        a1 = np.maximum(np.einsum("pi,pij->pj", x, w1) + b1, 0.0)
        a2 = np.maximum(np.einsum("pi,pij->pj", a1, w2) + b2, 0.0)
        return np.tanh(np.einsum("pi,pij->pj", a2, w3) + b3), a2
