"""Real-time, detached 50-agent ghost simulator.

This simulator intentionally does not call TMInterface input or rewind APIs.
The user's TMNF car remains completely independent. Agent positions are ordinary
world-space ghost trajectories that are rendered by the TMRL overlay.
"""
from __future__ import annotations

import math
import time
import numpy as np


class GhostSimulation:
    def __init__(self, telemetry, engine, rng, population_size: int):
        self.telemetry = telemetry
        self.engine = engine
        self.rng = rng
        self.size = population_size
        self.running = False
        self.elapsed = 0.0
        self.origin = np.zeros(3, np.float64)
        self.start_yaw = 0.0
        self.forward = np.array([0.0, 0.0, 1.0], np.float64)
        self.right = np.array([1.0, 0.0, 0.0], np.float64)
        self.corridor_half_width = 45.0
        self.last_step = time.monotonic()

    def _frame(self, yaw: float):
        forward = np.array([math.sin(yaw), 0.0, math.cos(yaw)], np.float64)
        right = np.array([math.cos(yaw), 0.0, -math.sin(yaw)], np.float64)
        return forward, right

    def start(self, origin, yaw):
        self.origin[:] = np.asarray(origin, np.float64)
        self.start_yaw = float(yaw)
        self.forward, self.right = self._frame(self.start_yaw)
        self.elapsed = 0.0
        self.last_step = time.monotonic()
        self.running = True

        # Stagger ghosts behind/in front and across a broad virtual starting grid.
        for i, agent in enumerate(self.telemetry.agents):
            col = i % 10
            row = i // 10
            lateral = (col - 4.5) * 4.0
            longitudinal = row * 7.0 + 10.0
            pos = self.origin + self.right * lateral + self.forward * longitudinal
            agent.position[:] = pos
            agent.velocity.fill(0.0)
            agent.yaw_pitch_roll[:] = 0.0
            agent.alive = True
            agent.crashed = False
            agent.distance = 0.0
            agent.max_distance = 0.0
            agent.speed_sum = 0.0
            agent.samples = 0
            agent.wall_penalty = 0.0
            agent.forward_progress = 0.0
            agent.forward_speed_kmh = 0.0
            agent.race_time_ms = 0
            agent.last_steer = 0.0
            agent.last_gas = 0.0
            agent.below_speed_since_ms = -1
            agent.negative_forward_since_ms = -1
            agent.lidar.fill(1.0)
            agent.history_time.clear()
            agent.history_x.clear()
            agent.history_y.clear()
            agent.history_z.clear()
            agent.history_speed.clear()
            agent.history_steer.clear()
            agent.history_gas.clear()

    def _observation_matrix(self):
        rows = []
        for agent in self.telemetry.agents:
            rel = agent.position - self.origin
            along = float(np.dot(rel, self.forward))
            lateral = float(np.dot(rel, self.right))
            yaw_err = float(agent.yaw_pitch_roll[0])
            rows.append([
                np.clip(agent.speed_kmh / 300.0, 0.0, 1.0),
                np.clip(lateral / 100.0, -1.0, 1.0),
                np.clip(along / 1000.0, -1.0, 1.0),
                np.clip(agent.position[1] / 100.0, -1.0, 1.0),
                np.clip(yaw_err / math.pi, -1.0, 1.0),
                float(agent.lidar[0]),
                float(agent.lidar[1]),
                float(agent.lidar[2]),
            ])
        return np.asarray(rows, np.float32)

    def step(self, dt: float):
        if not self.running:
            return 0

        dt = float(np.clip(dt, 0.001, 0.05))
        self.elapsed += dt
        observations = self._observation_matrix()
        commands, _h1, h2 = self.engine.batch_forward(observations)

        active = 0
        for i, agent in enumerate(self.telemetry.agents):
            if not agent.alive:
                continue

            active += 1
            steer = float(np.clip(commands[i, 0], -1.0, 1.0))
            drive = float(np.clip(commands[i, 1], -1.0, 1.0))
            throttle = max(0.0, drive)
            brake = max(0.0, -drive)

            agent.activations[:] = h2[i]

            speed_mps = agent.speed_mps
            acceleration = throttle * 24.0 - brake * 34.0 - 0.85
            speed_mps = float(np.clip(speed_mps + acceleration * dt, 0.0, 115.0))

            # Steering becomes stronger with speed, but remains controllable.
            yaw_rate = steer * (0.45 + min(speed_mps / 20.0, 3.0))
            agent.yaw_pitch_roll[0] += yaw_rate * dt
            local_yaw = float(agent.yaw_pitch_roll[0])

            world_yaw = self.start_yaw + local_yaw
            fwd, _right = self._frame(world_yaw)
            old_pos = agent.position.copy()
            agent.position[:] = agent.position + fwd * speed_mps * dt
            agent.position[1] = self.origin[1]

            agent.velocity[:] = fwd * speed_mps
            agent.race_time_ms = int(self.elapsed * 1000.0)
            agent.speed_sum += speed_mps * 3.6
            agent.samples += 1
            agent.last_steer = steer
            agent.last_gas = throttle - brake
            agent.forward_speed_kmh = float(np.dot(agent.velocity, self.forward) * 3.6)

            ds = float(np.linalg.norm(agent.position - old_pos))
            agent.distance += max(0.0, ds)
            agent.max_distance = max(agent.max_distance, agent.distance)

            rel = agent.position - self.origin
            along = float(np.dot(rel, self.forward))
            lateral = float(np.dot(rel, self.right))
            agent.forward_progress = max(0.0, along)

            wall_margin = max(0.0, self.corridor_half_width - abs(lateral))
            wall_factor = float(np.clip(wall_margin / self.corridor_half_width, 0.0, 1.0))
            front_margin = float(np.clip((200.0 - max(0.0, along)) / 200.0, 0.0, 1.0))
            agent.lidar[0] = max(0.05, front_margin)
            agent.lidar[1] = max(0.02, np.clip((lateral + self.corridor_half_width) / (2 * self.corridor_half_width), 0.0, 1.0))
            agent.lidar[2] = max(0.02, np.clip((self.corridor_half_width - lateral) / (2 * self.corridor_half_width), 0.0, 1.0))

            if abs(lateral) > self.corridor_half_width:
                agent.wall_penalty += (abs(lateral) - self.corridor_half_width) * 0.25
            if abs(local_yaw) > math.radians(115):
                agent.alive = False
                agent.crashed = True
            elif abs(lateral) > self.corridor_half_width + 20.0:
                agent.alive = False
                agent.crashed = True
            elif self.elapsed > 1.5 and speed_mps < 0.25:
                agent.alive = False
                agent.crashed = True
            elif agent.forward_progress > 5000.0:
                agent.alive = False
                agent.crashed = True
            agent.record_action(steer, throttle - brake)

        return active

    def fitness_results(self):
        from core.evolution import FitnessResult
        results = []
        for agent in self.telemetry.agents:
            fitness = self.engine.fitness(
                agent.forward_progress,
                agent.average_speed,
                agent.wall_penalty,
            )
            if not agent.alive:
                fitness -= 5.0
            results.append(FitnessResult(
                fitness=fitness,
                distance=agent.forward_progress,
                average_speed=agent.average_speed,
                wall_penalty=agent.wall_penalty,
                survived=agent.alive,
            ))
        return results
