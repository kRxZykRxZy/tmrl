"""Population-level genetic engine."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

@dataclass
class FitnessResult:
    fitness:float
    distance:float
    average_speed:float
    wall_penalty:float
    survived:bool

class EvolutionEngine:
    def __init__(self,population,elite_count=5,mutation_rate=.15,mutation_sigma=.15,seed=None):
        self.population=np.asarray(population,dtype=np.float32).copy()
        self.size,self.genome_size=self.population.shape
        self.elite_count=elite_count
        self.mutation_rate=mutation_rate
        self.mutation_sigma=mutation_sigma
        self.rng=np.random.default_rng(seed)
        self.generation=0
        self.best_score=-np.inf
        self.best_agent=0

    def fitness(self,distance,average_speed,wall_penalty):
        return float(distance*1.5+average_speed*.5-wall_penalty)

    def evolve(self,results):
        fitness=np.asarray([r.fitness for r in results],np.float64)
        order=np.argsort(fitness)[::-1]
        elites=self.population[order[:self.elite_count]].copy()
        self.best_score=max(self.best_score,float(fitness[order[0]]))
        self.best_agent=int(order[0])
        new=np.empty_like(self.population)
        new[:self.elite_count]=elites
        elite_fit=fitness[order[:self.elite_count]]
        shifted=elite_fit-elite_fit.min()
        probs=shifted+1e-9
        probs/=probs.sum()
        parents=self.rng.choice(self.elite_count,self.size-self.elite_count,replace=True,p=probs)
        for dst,parent in enumerate(parents,start=self.elite_count):
            child=elites[parent].copy()
            mask=self.rng.random(self.genome_size)<self.mutation_rate
            child[mask]+=self.rng.normal(0,self.mutation_sigma,int(mask.sum())).astype(np.float32)
            new[dst]=child
        self.population=new
        self.generation+=1
        return {"generation":self.generation,"best_fitness":float(fitness[order[0]]),"mean_fitness":float(fitness.mean()),"survival_rate":float(sum(r.survived for r in results)/self.size),"best_agent":self.best_agent}

    def batch_forward(self,observations):
        x=np.asarray(observations,np.float32)
        if x.shape!=(self.size,8):raise ValueError(f"expected {(self.size,8)}, got {x.shape}")
        w1=self.population[:,:256].reshape(self.size,8,32);b1=self.population[:,256:288]
        w2=self.population[:,288:1056].reshape(self.size,32,24);b2=self.population[:,1056:1080]
        w3=self.population[:,1080:1128].reshape(self.size,24,2);b3=self.population[:,1128:1130]
        h1=np.maximum(np.einsum("pi,pij->pj",x,w1)+b1,0)
        h2=np.maximum(np.einsum("pi,pij->pj",h1,w2)+b2,0)
        return np.tanh(np.einsum("pi,pij->pj",h2,w3)+b3),h1,h2
