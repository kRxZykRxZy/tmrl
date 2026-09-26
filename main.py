"""50-agent TMInterface orchestrator.

TMInterface's Python API controls one vehicle per server. Therefore 50 simultaneous
visible agents are represented by 50 concurrent TMNF/TMInterface instances named
TMInterface0 through TMInterface49.
"""
from __future__ import annotations
import json,logging,threading,time
from pathlib import Path
import numpy as np
from core.network import NeuralNetwork
from core.evolution import EvolutionEngine,FitnessResult
from environment.telemetry import TelemetryStore
from ui.standalone_ui import StandaloneHUD
try:
 from tminterface.client import Client,run_client
except ImportError as e: raise SystemExit("Install tminterface==1.0.2") from e

ROOT=Path(__file__).resolve().parent
CFG=json.loads((ROOT/"config/hyperparams.json").read_text())
N=int(CFG["population_size"]);PREFIX=CFG.get("server_prefix","TMInterface")
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
log=logging.getLogger("tmrl")

class Coordinator:
 def __init__(self):
  self.telemetry=TelemetryStore(N)
  self.engine=EvolutionEngine(NeuralNetwork.population(N),int(CFG["elite_count"]),float(CFG["mutation_rate"]),float(CFG["mutation_sigma"]),CFG.get("random_seed"))
  self.ifaces=[None]*N;self.observations=np.zeros((N,8),np.float32);self.outputs=np.zeros((N,2),np.float32)
  self.focus=0;self.generation_started=time.monotonic();self.lock=threading.RLock();self.resetting=False
  self.last_summary={"generation":0,"best_fitness":0.0,"survival_rate":0.0}

 def step(self,i,iface):
  try:
   if iface.is_in_menus():return
   state=iface.get_simulation_state()
   self.telemetry.update(i,state)
   with self.lock:
    self.observations[i]=self.telemetry.agents[i].observation()
    commands,_,h2=self.engine.batch_forward(self.observations)
    self.outputs[:]=commands
    for j,a in enumerate(self.telemetry.agents):a.activations=h2[j]
    agent=self.telemetry.agents[i]
    if agent.alive:
     steer=int(np.clip(commands[i,0],-1,1)*65536)
     gas=int(np.clip(commands[i,1],-1,1)*65536)
    else:
     steer=gas=0
   iface.set_input_state(sim_clear_buffer=False,steer=steer,gas=gas,accelerate=gas>0,brake=gas<0)
   self.maybe_evolve()
  except Exception as e:
   log.error("agent %02d physics-step failure: %s",i,e)

 def maybe_evolve(self):
  with self.lock:
   if self.resetting:return
   timeout=time.monotonic()-self.generation_started>=float(CFG["generation_timeout_seconds"])
   finished=self.telemetry.active_count()==0
   if not (timeout or finished):return
   self.resetting=True
   try:
    results=[FitnessResult(self.engine.fitness(a.max_distance,a.average_speed,a.wall_penalty),a.max_distance,a.average_speed,a.wall_penalty,a.alive) for a in self.telemetry.agents]
    self.last_summary=self.engine.evolve(results)
    log.info("generation %d best=%.3f survival=%.1f%%",self.engine.generation,self.last_summary["best_fitness"],self.last_summary["survival_rate"]*100)
    for a in self.telemetry.agents:a.reset()
    self.observations.fill(0);self.outputs.fill(0);self.generation_started=time.monotonic()
    for iface in self.ifaces:
     if iface is not None:
      try:iface.execute_command("press system retry")
      except Exception as e:log.warning("retry command failed: %s",e)
   finally:self.resetting=False

 def snapshot(self):
  with self.lock:
   a=self.telemetry.agents[self.focus]
   return type("Snapshot",(),dict(
    generation=self.engine.generation,best=self.engine.best_score,active=self.telemetry.active_count(),
    focus=self.focus,speed=a.speed_kmh,distance=a.max_distance,
    fitness=self.engine.fitness(a.max_distance,a.average_speed,a.wall_penalty),
    front=1.,left=1.,right=1.,activations=a.activations.copy()))()

 def ui(self,event):
  if event[0]=="focus_delta":
   with self.lock:self.focus=(self.focus+int(event[1]))%N
  return self.snapshot()

class Agent(Client):
 def __init__(self,c,i):super().__init__();self.c=c;self.i=i
 def on_registered(self,iface):
  self.c.ifaces[self.i]=iface;iface.set_speed(1.0);iface.set_timeout(5000)
  log.info("agent %02d registered",self.i)
 def on_run_step(self,iface,_time):self.c.step(self.i,iface)
 def on_client_exception(self,iface,e):log.error("agent %02d: %s",self.i,e)
 def on_deregistered(self,iface):log.warning("agent %02d disconnected",self.i)

def worker(c,i):
 name=f"{PREFIX}{i}"
 while True:
  try:
   log.info("connecting agent %02d -> %s",i,name);run_client(Agent(c,i),name);return
  except Exception as e:
   log.warning("agent %02d unavailable (%s); retrying",i,e);time.sleep(2)

def main():
 c=Coordinator()
 for i in range(N):threading.Thread(target=worker,args=(c,i),name=f"tmrl-{i:02d}",daemon=True).start()
 StandaloneHUD(c.ui).run()

if __name__=="__main__":main()
