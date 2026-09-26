"""50-agent TMInterface orchestrator."""
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
ROOT=Path(__file__).resolve().parent;CFG=json.loads((ROOT/"config/hyperparams.json").read_text())
N=int(CFG["population_size"]);PREFIX=CFG.get("server_prefix","TMInterface")
logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s");log=logging.getLogger("tmrl")

class Coordinator:
 def __init__(self):
  self.telemetry=TelemetryStore(N);self.engine=EvolutionEngine(NeuralNetwork.population(N),int(CFG["elite_count"]),float(CFG["mutation_rate"]),float(CFG["mutation_sigma"]),CFG.get("random_seed"))
  self.ifaces=[None]*N;self.observations=np.zeros((N,8),np.float32);self.outputs=np.zeros((N,2),np.float32);self.focus=0
  self.step_barrier=threading.Barrier(N);self.release_barrier=threading.Barrier(N);self.generation_barrier=threading.Barrier(N);self.generation_started=time.monotonic();self.lock=threading.RLock()
 def step(self,i,iface):
  if iface.is_in_menus():return
  state=iface.get_simulation_state();self.telemetry.update(i,state)
  with self.lock:self.observations[i]=self.telemetry.agents[i].observation()
  try:
   token=self.step_barrier.wait(1.)
   if token==0:
    out,_,h2=self.engine.batch_forward(self.observations)
    with self.lock:self.outputs[:]=out
    for j,a in enumerate(self.telemetry.agents):a.activations=h2[j]
   self.release_barrier.wait(1.)
  except threading.BrokenBarrierError:return
  a=self.telemetry.agents[i]
  if a.alive:
   steer=int(np.clip(self.outputs[i,0],-1,1)*65536);gas=int(np.clip(self.outputs[i,1],-1,1)*65536)
   try:iface.set_input_state(sim_clear_buffer=False,steer=steer,gas=gas,accelerate=gas>0,brake=gas<0)
   except Exception:log.exception("agent %d input failure",i)
  if self.generation_done():self.end_generation(iface)
 def generation_done(self):
  return time.monotonic()-self.generation_started>=float(CFG["generation_timeout_seconds"]) or self.telemetry.active_count()==0
 def end_generation(self,iface):
  try:
   token=self.generation_barrier.wait(3.)
   if token==0:
    results=[FitnessResult(self.engine.fitness(a.max_distance,a.average_speed,a.wall_penalty),a.max_distance,a.average_speed,a.wall_penalty,a.alive) for a in self.telemetry.agents]
    self.last_summary=self.engine.evolve(results);self.generation_started=time.monotonic()
    for a in self.telemetry.agents:a.reset()
    for x in self.ifaces:
     if x:
      try:x.execute_command("press system retry")
      except Exception:log.exception("retry failed")
   self.generation_barrier.wait(3.)
  except threading.BrokenBarrierError:log.error("generation barrier broken")
 def snapshot(self):
  a=self.telemetry.agents[self.focus]
  return type("Snapshot",(),dict(generation=self.engine.generation,best=self.engine.best_score,active=self.telemetry.active_count(),focus=self.focus,speed=a.speed_kmh,distance=a.max_distance,fitness=self.engine.fitness(a.max_distance,a.average_speed,a.wall_penalty),front=1.,left=1.,right=1.,activations=a.activations))()
 def ui(self,event):
  if event[0]=="focus_delta":self.focus=(self.focus+int(event[1]))%N
  return self.snapshot()

class Agent(Client):
 def __init__(self,c,i):super().__init__();self.c=c;self.i=i
 def on_registered(self,iface):self.c.ifaces[self.i]=iface;iface.set_speed(1.0);iface.set_timeout(5000)
 def on_run_step(self,iface,t):self.c.step(self.i,iface)
 def on_client_exception(self,iface,e):log.error("agent %02d: %s",self.i,e)
 def on_deregistered(self,iface):log.warning("agent %02d disconnected",self.i)

def worker(c,i):
 name=f"{PREFIX}{i}"
 while True:
  try:log.info("connecting agent %02d -> %s",i,name);run_client(Agent(c,i),name);return
  except Exception:log.exception("agent %02d failed; retrying",i);time.sleep(2)

def main():
 c=Coordinator()
 for i in range(N):threading.Thread(target=worker,args=(c,i),name=f"tmrl-{i:02d}",daemon=True).start()
 StandaloneHUD(c.ui).run()
if __name__=="__main__":main()
