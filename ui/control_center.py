"""Full Tkinter control centre for the single-instance 50-agent trainer."""
from __future__ import annotations
import ctypes
from tkinter import ttk, messagebox
import tkinter as tk
import time
from ctypes import wintypes
from PIL import ImageGrab, ImageTk
from ui.ghost_overlay import GhostOverlay

class ControlCenter:
    def __init__(self, trainer):
        self.trainer = trainer
        self.root = tk.Tk()
        self.root.title("TMRL Control Center — 50 Agent Trainer")
        self.root.geometry("1450x900")
        self.root.minsize(1180, 720)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.focus_agent = 0
        self.replay_agent = 0
        self.replay_index = 0
        self.replay_playing = False
        self.live_photo = None
        self.last_sweep = 0.0
        self.last_capture = 0.0
        self._build()
        self.ghost_overlay = GhostOverlay(trainer)
        self.root.after(100, self.refresh)
        self.root.after(33, self.ghost_overlay.update)

    def _build(self):
        style = ttk.Style(self.root)
        try: style.theme_use("clam")
        except tk.TclError: pass
        top = ttk.Frame(self.root, padding=8); top.pack(fill="x")
        self.generation = ttk.Label(top, text="Generation 0", font=("Segoe UI", 15, "bold")); self.generation.pack(side="left", padx=(0,20))
        self.best = ttk.Label(top, text="Best 0.00"); self.best.pack(side="left", padx=8)
        self.active = ttk.Label(top, text="Ghosts 2/2"); self.active.pack(side="left", padx=8)
        self.phase = ttk.Label(top, text="TRAINING"); self.phase.pack(side="left", padx=8)
        buttons = ttk.Frame(top); buttons.pack(side="right")
        for text, cmd in [
            ("Start", lambda:self.trainer.ui_command("resume")),
            ("Pause", lambda:self.trainer.ui_command("pause")),
            ("Retry", lambda:self.trainer.ui_command("retry")),
            ("New Race", lambda:self.trainer.ui_command("new_race")),
            ("Single Agent", lambda:self.trainer.ui_command("single_agent")),
            ("Camera Sweep", self.trainer.toggle_camera_sweep),
            ("Save Checkpoint", lambda:self.trainer.ui_command("save_checkpoint")),
            ("Load Checkpoint", lambda:self.trainer.ui_command("load_checkpoint")),
        ]:
            ttk.Button(buttons, text=text, command=cmd).pack(side="left", padx=2)
        nb = ttk.Notebook(self.root); nb.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.dashboard = ttk.Frame(nb); nb.add(self.dashboard,text="Dashboard")
        self.agents_tab = ttk.Frame(nb); nb.add(self.agents_tab,text="Agents")
        self.camera_tab = ttk.Frame(nb); nb.add(self.camera_tab,text="Camera Wall")
        self.replay_tab = ttk.Frame(nb); nb.add(self.replay_tab,text="Replay")
        self.race_tab = ttk.Frame(nb); nb.add(self.race_tab,text="Race Setup")
        self.settings_tab = ttk.Frame(nb); nb.add(self.settings_tab,text="Settings")
        self._build_dashboard(); self._build_agents(); self._build_camera()
        self._build_replay(); self._build_race(); self._build_settings()

    def _build_dashboard(self):
        left=ttk.Frame(self.dashboard,padding=12); left.pack(side="left",fill="both",expand=True)
        right=ttk.Frame(self.dashboard,padding=12); right.pack(side="right",fill="y")
        self.stats=tk.Text(left,height=20,width=72,bg="#101318",fg="#e8edf2",insertbackground="white"); self.stats.pack(fill="both",expand=True)
        self.focus_label=ttk.Label(right,text="Focused agent: 0",font=("Segoe UI",14,"bold")); self.focus_label.pack(anchor="w",pady=5)
        for key in ("speed","distance","fitness","avg","lap","wall","front","left","right"):
            lab=ttk.Label(right,text=f"{key}: 0"); lab.pack(anchor="w",pady=3); setattr(self,key+"_label",lab)

    def _build_agents(self):
        cols=("id","alive","speed","distance","fitness","lap","lap_time","avg","wall")
        self.tree=ttk.Treeview(self.agents_tab,columns=cols,show="headings",height=28)
        names={"id":"Agent","alive":"Alive","speed":"Speed km/h","distance":"Distance","fitness":"Fitness","lap":"Lap","lap_time":"Lap time","avg":"Avg speed","wall":"Wall penalty"}
        for c in cols:
            self.tree.heading(c,text=names[c]); self.tree.column(c,width=105,anchor="center")
        self.tree.pack(fill="both",expand=True); self.tree.bind("<<TreeviewSelect>>",self._select_agent)

    def _build_camera(self):
        left=ttk.Frame(self.camera_tab,padding=8); left.pack(side="left",fill="both",expand=True)
        right=ttk.Frame(self.camera_tab,padding=8); right.pack(side="right",fill="y")
        self.live_label=ttk.Label(left,text="TMNF player camera — your car remains yours",anchor="center"); self.live_label.pack(fill="both",expand=True)
        ttk.Label(left,text="50 detached AI ghost cars are rendered as a click-through overlay. Your TMNF controls are never injected.").pack(anchor="w")
        self.wall_canvas=tk.Canvas(right,width=650,height=720,bg="#0d1117",highlightthickness=0); self.wall_canvas.pack(fill="both",expand=True)

    def _build_replay(self):
        bar=ttk.Frame(self.replay_tab,padding=8); bar.pack(fill="x")
        self.replay_spin=ttk.Spinbox(bar,from_=0,to=49,width=6,command=self._replay_agent_changed); self.replay_spin.set("0"); self.replay_spin.pack(side="left",padx=4)
        ttk.Button(bar,text="Play Preview",command=self._toggle_replay).pack(side="left",padx=4)
        ttk.Button(bar,text="Play in TMNF",command=lambda:self.trainer.start_replay(self.replay_agent)).pack(side="left",padx=4)
        self.replay_time=ttk.Label(bar,text="0.00s"); self.replay_time.pack(side="left",padx=8)
        self.replay_canvas=tk.Canvas(self.replay_tab,bg="#101318",height=680,highlightthickness=0); self.replay_canvas.pack(fill="both",expand=True,padx=8,pady=8)

    def _build_race(self):
        frm=ttk.Frame(self.race_tab,padding=16); frm.pack(fill="x")
        ttk.Label(frm,text="Map filename in TMNF Tracks folder:").grid(row=0,column=0,sticky="w")
        self.map_var=tk.StringVar(value=self.trainer.map_name); ttk.Entry(frm,textvariable=self.map_var,width=70).grid(row=0,column=1,sticky="ew",padx=8)
        ttk.Button(frm,text="Load Map",command=self._load_map).grid(row=0,column=2,padx=4)
        ttk.Button(frm,text="Start / Reset",command=lambda:self.trainer.ui_command("new_race")).grid(row=1,column=0,pady=12)
        ttk.Button(frm,text="Single Agent Test",command=lambda:self.trainer.ui_command("single_agent")).grid(row=1,column=1,sticky="w")
        ttk.Label(frm,text="The map command uses TMInterface's Tracks-folder map loader.").grid(row=2,column=0,columnspan=3,sticky="w")
        frm.columnconfigure(1,weight=1)

    def _build_settings(self):
        frm=ttk.Frame(self.settings_tab,padding=16); frm.pack(anchor="nw")

        self.count_var=tk.IntVar(value=self.trainer.agent_count)
        ttk.Label(frm,text="Live ghost cars").grid(row=0,column=0,sticky="w")
        ttk.Spinbox(frm,from_=1,to=50,increment=1,
                    textvariable=self.count_var,width=10).grid(row=0,column=1,padx=8)
        ttk.Button(frm,text="Apply ghost count",command=self._apply_agent_count).grid(row=0,column=2)

        self.speed_var=tk.DoubleVar(value=self.trainer.sim_speed)
        ttk.Label(frm,text="Detached ghost training speed").grid(row=1,column=0,sticky="w")
        ttk.Spinbox(frm,from_=0.25,to=2.0,increment=0.05,textvariable=self.speed_var,width=10).grid(row=1,column=1,padx=8)
        ttk.Button(frm,text="Apply speed",command=self._apply_speed).grid(row=1,column=2)

        self.adaptive_var=tk.BooleanVar(value=self.trainer.adaptive_cpu)
        ttk.Checkbutton(frm,text="Adaptive CPU scaling",variable=self.adaptive_var,
                        command=self._apply_adaptive).grid(row=2,column=0,columnspan=2,sticky="w",pady=(10,0))

        self.cpu_target_var=tk.DoubleVar(value=self.trainer.cpu_target)
        ttk.Label(frm,text="CPU target %").grid(row=3,column=0,sticky="w")
        ttk.Spinbox(frm,from_=20,to=95,increment=5,textvariable=self.cpu_target_var,width=10).grid(row=3,column=1,padx=8)
        ttk.Button(frm,text="Apply CPU target",command=self._apply_cpu_target).grid(row=3,column=2)

        self.cpu_min_var=tk.IntVar(value=self.trainer.cpu_min_agents)
        self.cpu_max_var=tk.IntVar(value=self.trainer.cpu_max_agents)
        ttk.Label(frm,text="Adaptive minimum ghosts").grid(row=4,column=0,sticky="w")
        ttk.Spinbox(frm,from_=1,to=50,increment=1,textvariable=self.cpu_min_var,width=10).grid(row=4,column=1,padx=8)
        ttk.Label(frm,text="Adaptive maximum ghosts").grid(row=5,column=0,sticky="w")
        ttk.Spinbox(frm,from_=1,to=50,increment=1,textvariable=self.cpu_max_var,width=10).grid(row=5,column=1,padx=8)
        ttk.Button(frm,text="Apply CPU range",command=self._apply_cpu_range).grid(row=5,column=2)

        self.threads_var=tk.IntVar(value=self.trainer.worker_threads)
        ttk.Label(frm,text="Background checkpoint threads").grid(row=6,column=0,sticky="w")
        ttk.Spinbox(frm,from_=1,to=16,textvariable=self.threads_var,width=10).grid(row=6,column=1,padx=8)
        ttk.Button(frm,text="Apply threads",command=lambda:self.trainer.set_worker_threads(int(self.threads_var.get()))).grid(row=6,column=2)

        ttk.Label(frm,text="Quick checkpoint interval (seconds)").grid(row=7,column=0,sticky="w")
        self.quick_save_var=tk.DoubleVar(value=self.trainer.quick_checkpoint_seconds)
        ttk.Spinbox(frm,from_=0.5,to=30.0,increment=0.5,textvariable=self.quick_save_var,width=10).grid(row=7,column=1,padx=8)
        ttk.Button(frm,text="Apply checkpoint interval",command=self._apply_checkpoint_intervals).grid(row=7,column=2)

        ttk.Label(frm,text="Full history checkpoint interval (seconds)").grid(row=8,column=0,sticky="w")
        self.full_save_var=tk.DoubleVar(value=self.trainer.full_checkpoint_seconds)
        ttk.Spinbox(frm,from_=2.0,to=300.0,increment=1.0,textvariable=self.full_save_var,width=10).grid(row=8,column=1,padx=8)

        self.cpu_status=ttk.Label(frm,text="CPU: measuring...")
        self.cpu_status.grid(row=9,column=0,columnspan=3,pady=(14,4),sticky="w")
        ttk.Label(frm,text="PLAYER CONTROL: OFF | TMNF game speed is untouched | checkpointing runs in the background.").grid(row=10,column=0,columnspan=3,pady=8,sticky="w")

    def _apply_checkpoint_intervals(self):
        try:
            quick=float(self.quick_save_var.get())
            full=float(self.full_save_var.get())
            self.trainer.set_checkpoint_intervals(quick, full)
        except (ValueError, tk.TclError):
            messagebox.showerror("Checkpoint interval","Enter valid positive intervals.")

    def _apply_agent_count(self):
        try:
            count=int(self.count_var.get())
            self.trainer.set_agent_count(count)
        except (ValueError, tk.TclError):
            messagebox.showerror("Ghost count","Enter a whole number from 1 to 50.")

    def _apply_adaptive(self):
        self.trainer.set_adaptive_cpu(bool(self.adaptive_var.get()))

    def _apply_cpu_target(self):
        try:
            self.trainer.set_cpu_target(float(self.cpu_target_var.get()))
        except (ValueError, tk.TclError):
            messagebox.showerror("CPU target","Enter a percentage from 20 to 95.")

    def _apply_cpu_range(self):
        try:
            low=int(self.cpu_min_var.get())
            high=int(self.cpu_max_var.get())
            self.trainer.set_cpu_min_agents(low)
            self.trainer.set_cpu_max_agents(high)
        except (ValueError, tk.TclError):
            messagebox.showerror("CPU range","Enter whole numbers from 1 to 50.")

    def _select_agent(self,_=None):
        sel=self.tree.selection()
        if sel:
            aid=int(sel[0]); self.focus_agent=aid; self.trainer.set_focus(aid); self.replay_spin.set(str(aid)); self.replay_agent=aid

    def _replay_agent_changed(self):
        try:self.replay_agent=int(self.replay_spin.get())
        except ValueError:self.replay_agent=0
        self.replay_index=0; self._draw_replay()

    def _toggle_replay(self):
        self.replay_playing=not self.replay_playing
        if self.replay_playing:self._replay_tick()

    def _replay_tick(self):
        if not self.replay_playing:return
        hist=self.trainer.replay_snapshot(self.replay_agent)
        if not hist["time"]:
            self.replay_playing=False; return
        self.replay_index=min(self.replay_index+1,len(hist["time"])-1); self._draw_replay()
        if self.replay_index < len(hist["time"])-1:self.root.after(40,self._replay_tick)
        else:self.replay_playing=False

    def _draw_replay(self):
        hist=self.trainer.replay_snapshot(self.replay_agent); self.replay_canvas.delete("all")
        if len(hist["time"])<2:return
        xs,zs=hist["x"],hist["z"]; minx,maxx,minz,maxz=min(xs),max(xs),min(zs),max(zs)
        sx=max(maxx-minx,1.0); sz=max(maxz-minz,1.0); w=max(self.replay_canvas.winfo_width(),800); h=max(self.replay_canvas.winfo_height(),600)
        pts=[]
        for i in range(min(self.replay_index+1,len(xs))):
            pts.extend((40+(xs[i]-minx)/sx*(w-80),40+(zs[i]-minz)/sz*(h-80)))
        if len(pts)>=4:self.replay_canvas.create_line(*pts,fill="#4fc3f7",width=3)
        if pts:self.replay_canvas.create_oval(pts[-2]-6,pts[-1]-6,pts[-2]+6,pts[-1]+6,fill="#ffca28",outline="")
        self.replay_time.config(text=f"{hist['time'][self.replay_index]:.2f}s")
        self.replay_canvas.create_text(20,18,anchor="w",text=f"Agent {self.replay_agent} replay",fill="white",font=("Segoe UI",14,"bold"))

    def _load_map(self):
        self.trainer.map_name=self.map_var.get().strip(); self.trainer.ui_command("load_map",self.trainer.map_name)

    def _apply_speed(self):
        try:self.trainer.set_game_speed(float(self.speed_var.get()))
        except ValueError:messagebox.showerror("Speed","Enter a number.")

    def _capture_game(self):
        now=time.monotonic()
        if now - self.last_capture < 1.0:
            return
        self.last_capture = now

        hwnd=self.trainer.find_game_window()
        if not hwnd:
            self.live_label.configure(image="", text="TMNF live camera — game window not found")
            return
        try:
            rect=wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if rect.right <= rect.left or rect.bottom <= rect.top:
                return
            img=ImageGrab.grab(bbox=(rect.left,rect.top,rect.right,rect.bottom),all_screens=True)
            img.thumbnail((900,620))
            self.live_photo=ImageTk.PhotoImage(img.convert("RGB"))
            self.live_label.configure(image=self.live_photo,text="")
        except Exception as exc:
            self.live_label.configure(image="", text=f"Camera capture error: {exc}")

    def _draw_wall(self,snapshot):
        self.wall_canvas.delete("all"); cols=5; tile_w=126; tile_h=115
        for a in snapshot["agents"]:
            aid=a["id"]; col=aid%cols; row=aid//cols; x=col*tile_w+4; y=row*tile_h+4; sel=aid==snapshot["focus"]
            self.wall_canvas.create_rectangle(x,y,x+tile_w-8,y+tile_h-8,outline="#4fc3f7" if sel else "#333",width=2)
            self.wall_canvas.create_text(x+5,y+5,anchor="nw",text=f"#{aid:02d} {'RUN' if a['alive'] else 'DEAD'}",fill="white",font=("Consolas",9))
            self.wall_canvas.create_text(x+5,y+23,anchor="nw",text=f"{a['speed']:.0f} km/h",fill="#b8d8ff",font=("Consolas",9))
            self.wall_canvas.create_text(x+5,y+41,anchor="nw",text=f"D {a['distance']:.1f}",fill="white",font=("Consolas",9))
            self.wall_canvas.create_text(x+5,y+59,anchor="nw",text=f"F {a['fitness']:.1f}",fill="white",font=("Consolas",9))
            self.wall_canvas.create_rectangle(x+5,y+80,x+tile_w-20,y+88,fill="#222",outline="")
            self.wall_canvas.create_rectangle(x+5,y+80,x+5+(tile_w-25)*min(1,a['speed']/300),y+88,fill="#66bb6a",outline="")

    def refresh(self):
        try:
            s=self.trainer.ui_snapshot(); self.generation.config(text=f"Generation {s['generation']}"); self.best.config(text=f"Best {s['best']:.2f}"); self.active.config(text=f"Ghosts {s['active']}/{s['agent_count']}"); self.phase.config(text=s["phase"])
            a=s["focused"]; self.focus_label.config(text=f"Focused agent: {a['id']}")
            for key in ("speed","distance","fitness","avg","lap","wall","front","left","right"):
                val=a[key]; getattr(self,key+"_label").config(text=f"{key}: {val:.2f}" if isinstance(val,float) else f"{key}: {val}")
            self.stats.delete("1.0","end"); self.stats.insert("end",f"Generation: {s['generation']}\nBest fitness: {s['best']:.3f}\nMean fitness: {s['mean']:.3f}\nActive: {s['active']}/50\nTraining ticks: {s.get('ticks',0)}\nGame speed: {s['speed_factor']}x\nMap: {self.trainer.map_name}\nLast error: {s.get('last_error','')}\nFocused command: steer={a['steer']:+.3f}, gas={a['gas']:+.3f}\nLap: {a['lap']}  Lap time: {a['lap_time']:.3f}s\nCheckpoints: {a['checkpoints']}\n")
            self._draw_wall(s); self._draw_replay(); self._capture_game()
            cpu=s.get('cpu_usage')
            if hasattr(self,'cpu_status'):
                self.cpu_status.config(text=f"CPU: {cpu:.1f}%  |  ghosts: {s['agent_count']}  |  adaptive: {'ON' if s.get('adaptive_cpu') else 'OFF'}" if cpu is not None else "CPU: measuring...")
        except Exception as exc:
            try:
                self.trainer.last_error = f"UI: {type(exc).__name__}: {exc}"
            except Exception:
                pass
        self.root.after(200,self.refresh)

    def close(self):
        self.trainer.stop()
        try:
            self.ghost_overlay.close()
        finally:
            self.root.destroy()

    def run(self): self.root.mainloop()
