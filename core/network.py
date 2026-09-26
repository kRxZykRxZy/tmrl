"""NumPy-only controller: 8 -> 32 -> 24 -> 2."""
from __future__ import annotations
import numpy as np

INPUTS,H1,H2,OUTPUTS=8,32,24,2
PARAMETER_COUNT=INPUTS*H1+H1+H1*H2+H2+H2*OUTPUTS+OUTPUTS

class NeuralNetwork:
    parameter_count=PARAMETER_COUNT
    def __init__(self, params=None, rng=None):
        self.rng=rng or np.random.default_rng()
        self.W1=self.rng.normal(0,np.sqrt(2/INPUTS),(INPUTS,H1)).astype(np.float32)
        self.b1=np.zeros(H1,np.float32)
        self.W2=self.rng.normal(0,np.sqrt(2/H1),(H1,H2)).astype(np.float32)
        self.b2=np.zeros(H2,np.float32)
        self.W3=self.rng.normal(0,np.sqrt(2/H2),(H2,OUTPUTS)).astype(np.float32)
        self.b3=np.zeros(OUTPUTS,np.float32)
        if params is not None:self.set_params(params)

    @staticmethod
    def _relu(x): return np.maximum(x,0)
    def forward(self,x,return_activations=False):
        x=np.asarray(x,np.float32)
        single=x.ndim==1
        if single:x=x[None,:]
        if x.shape[-1]!=INPUTS:raise ValueError(f"expected {INPUTS} inputs, got {x.shape[-1]}")
        a1=self._relu(x@self.W1+self.b1)
        a2=self._relu(a1@self.W2+self.b2)
        out=np.tanh(a2@self.W3+self.b3)
        if return_activations:return (out[0] if single else out),{"input":x,"hidden1":a1,"hidden2":a2,"output":out}
        return out[0] if single else out

    def get_params(self):
        return np.concatenate((self.W1.ravel(),self.b1,self.W2.ravel(),self.b2,self.W3.ravel(),self.b3)).astype(np.float32)

    def set_params(self,p):
        p=np.asarray(p,np.float32).ravel()
        if p.size!=PARAMETER_COUNT:raise ValueError(f"expected {PARAMETER_COUNT} parameters, got {p.size}")
        i=0;n=256;self.W1=p[i:i+n].reshape(8,32).copy();i+=n
        n=32;self.b1=p[i:i+n].copy();i+=n
        n=768;self.W2=p[i:i+n].reshape(32,24).copy();i+=n
        n=24;self.b2=p[i:i+n].copy();i+=n
        n=48;self.W3=p[i:i+n].reshape(24,2).copy();i+=n
        self.b3=p[i:i+2].copy()

    @classmethod
    def population(cls,n,rng=None):
        rng=rng or np.random.default_rng()
        return np.stack([cls(rng=rng).get_params() for _ in range(n)])
