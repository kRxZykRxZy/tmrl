"""Scratch NumPy feed-forward controller used by every evolutionary agent."""
from __future__ import annotations
import numpy as np

INPUTS = 8
H1 = 32
H2 = 24
OUTPUTS = 2

PARAMETER_COUNT = INPUTS * H1 + H1 + H1 * H2 + H2 + H2 * OUTPUTS + OUTPUTS
# 256 + 32 + 768 + 24 + 48 + 2 = 1,130 parameters.
# The requested layer sizes therefore cannot mathematically produce exactly 1,024
# parameters; this implementation keeps the requested architecture intact.

def _relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(x, 0.0)

def _tanh(x: np.ndarray) -> np.ndarray:
    return np.tanh(x)

class NeuralNetwork:
    input_size = INPUTS
    hidden1_size = H1
    hidden2_size = H2
    output_size = OUTPUTS
    parameter_count = PARAMETER_COUNT

    def __init__(self, params: np.ndarray | None = None, rng: np.random.Generator | None = None):
        self.rng = rng or np.random.default_rng()
        self.W1 = self.rng.normal(0.0, np.sqrt(2.0 / INPUTS), (INPUTS, H1)).astype(np.float32)
        self.b1 = np.zeros(H1, dtype=np.float32)
        self.W2 = self.rng.normal(0.0, np.sqrt(2.0 / H1), (H1, H2)).astype(np.float32)
        self.b2 = np.zeros(H2, dtype=np.float32)
        self.W3 = self.rng.normal(0.0, np.sqrt(2.0 / H2), (H2, OUTPUTS)).astype(np.float32)
        self.b3 = np.zeros(OUTPUTS, dtype=np.float32)
        if params is not None:
            self.set_params(params)

    def forward(self, x: np.ndarray, return_activations: bool = False):
        a0 = np.asarray(x, dtype=np.float32)
        if a0.ndim == 1:
            a0 = a0[None, :]
        if a0.shape[1] != INPUTS:
            raise ValueError(f"expected {INPUTS} inputs, got {a0.shape[1]}")
        z1 = a0 @ self.W1 + self.b1
        a1 = _relu(z1)
        z2 = a1 @ self.W2 + self.b2
        a2 = _relu(z2)
        z3 = a2 @ self.W3 + self.b3
        out = _tanh(z3)
        if return_activations:
            return out, {"input": a0, "hidden1": a1, "hidden2": a2, "output": out}
        return out[0] if np.asarray(x).ndim == 1 else out

    predict = forward

    def get_params(self) -> np.ndarray:
        return np.concatenate((
            self.W1.ravel(), self.b1.ravel(),
            self.W2.ravel(), self.b2.ravel(),
            self.W3.ravel(), self.b3.ravel()
        )).astype(np.float32, copy=True)

    def set_params(self, weights: np.ndarray) -> None:
        flat = np.asarray(weights, dtype=np.float32).ravel()
        if flat.size != PARAMETER_COUNT:
            raise ValueError(f"expected {PARAMETER_COUNT} parameters, got {flat.size}")
        i = 0
        n = INPUTS * H1; self.W1 = flat[i:i+n].reshape(INPUTS, H1).copy(); i += n
        n = H1; self.b1 = flat[i:i+n].copy(); i += n
        n = H1 * H2; self.W2 = flat[i:i+n].reshape(H1, H2).copy(); i += n
        n = H2; self.b2 = flat[i:i+n].copy(); i += n
        n = H2 * OUTPUTS; self.W3 = flat[i:i+n].reshape(H2, OUTPUTS).copy(); i += n
        self.b3 = flat[i:i+OUTPUTS].copy()

    def clone(self) -> "NeuralNetwork":
        return NeuralNetwork(self.get_params(), self.rng)

    @classmethod
    def population(cls, size: int, rng: np.random.Generator | None = None) -> np.ndarray:
        rng = rng or np.random.default_rng()
        return np.stack([cls(rng=rng).get_params() for _ in range(size)], axis=0)
