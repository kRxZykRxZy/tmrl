"""Strict wire-format telemetry parsing and normalization."""
from __future__ import annotations
from dataclasses import dataclass
import math, numpy as np

@dataclass
class Telemetry:
    agent_id:int; position:tuple; velocity:tuple; pitch:float; roll:float; yaw:float
    checkpoint_time:float; lidar_left:float; lidar_right:float; lidar_front:float
    alive:bool=True; elapsed:float=0.0; distance:float=0.0; wall_penalty:float=0.0
    average_speed:float|None=None
    @property
    def speed(self): return math.sqrt(sum(v*v for v in self.velocity))
    def observation(self, speed_limit=100.0, position_scale=100.0):
        x,y,z=self.position
        return np.asarray([np.clip(self.speed/speed_limit,0,1),np.clip(x/position_scale,-1,1),np.clip(y/position_scale,-1,1),np.clip(z/position_scale,-1,1),np.clip(self.yaw/math.pi,-1,1),np.clip(self.lidar_left,0,1),np.clip(self.lidar_right,0,1),np.clip(self.lidar_front,0,1)],dtype=np.float32)

def parse_agent(obj):
    def vec3(k):
        v=obj.get(k,[0,0,0])
        if not isinstance(v,(list,tuple)) or len(v)!=3: raise ValueError(f"{k} must be a 3-vector")
        return tuple(float(i) for i in v)
    return Telemetry(int(obj["id"]),vec3("position"),vec3("velocity"),float(obj.get("pitch",0)),float(obj.get("roll",0)),float(obj.get("yaw",0)),float(obj.get("checkpoint_time",0)),float(obj.get("lidar_left",1)),float(obj.get("lidar_right",1)),float(obj.get("lidar_front",1)),bool(obj.get("alive",True)),float(obj.get("elapsed",0)),float(obj.get("distance",0)),float(obj.get("wall_penalty",0)),None if obj.get("average_speed") is None else float(obj["average_speed"]))

def parse_frame(packet,population_size=50):
    agents=packet.get("agents")
    if not isinstance(agents,list) or len(agents)!=population_size: raise ValueError(f"frame must contain exactly {population_size} agents")
    parsed=sorted((parse_agent(a) for a in agents),key=lambda x:x.agent_id)
    if [a.agent_id for a in parsed]!=list(range(population_size)): raise ValueError("agent ids must be exactly 0..population_size-1")
    return parsed
