"""TMInterface state adapter and persistent multi-agent telemetry."""
from __future__ import annotations
from dataclasses import dataclass,field
import math,threading
import numpy as np

@dataclass
class AgentTelemetry:
    agent_id:int
    position:np.ndarray=field(default_factory=lambda:np.zeros(3,np.float64))
    velocity:np.ndarray=field(default_factory=lambda:np.zeros(3,np.float64))
    yaw_pitch_roll:np.ndarray=field(default_factory=lambda:np.zeros(3,np.float64))
    race_time_ms:int=0
    distance:float=0.0
    max_distance:float=0.0
    speed_sum:float=0.0
    samples:int=0
    wall_penalty:float=0.0
    alive:bool=True
    crashed:bool=False
    below_speed_since_ms:int=-1
    activations:np.ndarray=field(default_factory=lambda:np.zeros(24,np.float32))

    @property
    def speed_mps(self): return float(np.linalg.norm(self.velocity))
    @property
    def speed_kmh(self): return self.speed_mps*3.6
    @property
    def average_speed(self): return self.speed_sum/max(1,self.samples)

    def observation(self,speed_limit=100.0,position_scale=1000.0,lidar=(1.0,1.0,1.0)):
        x,y,z=self.position
        yaw=self.yaw_pitch_roll[0]
        return np.asarray([
            np.clip(self.speed_kmh/speed_limit,0,1),
            np.clip(x/position_scale,-1,1),np.clip(y/position_scale,-1,1),np.clip(z/position_scale,-1,1),
            np.clip(yaw/math.pi,-1,1),np.clip(lidar[0],0,1),np.clip(lidar[1],0,1),np.clip(lidar[2],0,1)
        ],np.float32)

    def update(self,state):
        p=np.asarray(state.position,dtype=np.float64)
        v=np.asarray(state.velocity,dtype=np.float64)
        if self.samples:
            self.distance+=max(0.0,float(np.linalg.norm(p-self.position)))
        self.position=p
        self.velocity=v
        self.yaw_pitch_roll=np.asarray(state.yaw_pitch_roll,dtype=np.float64)
        self.race_time_ms=int(state.race_time)
        self.max_distance=max(self.max_distance,self.distance)
        self.speed_sum+=self.speed_kmh
        self.samples+=1

    def update_crash(self,grace_ms=1500,threshold_kmh=1.0):
        if self.race_time_ms<grace_ms or not self.alive:return
        if self.speed_kmh<threshold_kmh:
            if self.below_speed_since_ms<0:self.below_speed_since_ms=self.race_time_ms
            elif self.race_time_ms-self.below_speed_since_ms>=150:
                self.crashed=True;self.alive=False
        else:self.below_speed_since_ms=-1

class TelemetryStore:
    def __init__(self,size=50):
        self.agents=[AgentTelemetry(i) for i in range(size)]
        self.lock=threading.RLock()
    def update(self,i,state):
        with self.lock:
            a=self.agents[i];a.update(state);a.update_crash()
    def observations(self):
        with self.lock:return np.stack([a.observation() for a in self.agents])
    def active_count(self):
        with self.lock:return sum(a.alive for a in self.agents)
    def results(self,evolution):
        with self.lock:
            return [evolution.FitnessResult(evolution.fitness(a.max_distance,a.average_speed,a.wall_penalty),a.max_distance,a.average_speed,a.wall_penalty,a.alive) for a in self.agents]
