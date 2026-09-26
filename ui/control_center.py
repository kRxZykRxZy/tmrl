"""Full Tkinter control centre for the single-instance 50-agent trainer."""
from __future__ import annotations
import ctypes
from tkinter import ttk, messagebox
import tkinter as tk
import time
from ctypes import wintypes
from PIL import ImageGrab, ImageTk

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
        self._build()
        self.root.after(100, self.refresh)

    def _build(self):
        style = ttk.Style(self.root)
        try: style.theme_use("clam")
        except tk.TclError: pass
        top = ttk.Frame(self.root, padding=8); top.pack(fill="x")
        self.generation = ttk.Label(top, text="Generation 0", font=("Segoe UI", 15, "bold")); self.generation.pack(side="left", padx=(0,20))
        self.best = ttk.Label(top, text="Best 0.00"); self.best.pack(side="left", padx=8)
        self.active = ttk.Label(top, text="Active 50/50"); self.active.pack(side="left", padx=8)
        self.phase = ttk.Label(top, text="TRAINING"); self.phase.pack(side="left", padx=8)
        buttons = ttk.Frame(top); buttons.pack(side="right")
        for text, cmd in [
            ("Start", lambda:self.trainer.ui_command("resume")),
            ("Pause", lambda:self.trainer.ui_command("pause")),
            ("Retry", lambda:self.trainer.ui_command("retry")),
            ("New Race", lambda:self.trainer.ui_command("new_race")),
            ("Single Agent", lambda:self.trainer.ui_command("single_agent")),
            ("Camera Sweep", self.trainer.toggle_camera_sweep),
            ("Save", self.trainer.save_now),
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
        self.live_label=ttk.Label(left,text="TMNF live camera"); self.live_label.pack(fill="both",expand=True)
        ttk.Label(left,text="Live image is the one rendered car; the right wall represents the 50 logical agents/replay telemetry.").pack(anchor="w")
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
        self.speed_var=tk.DoubleVar(value=self.trainer.game_speed)
        ttk.Label(frm,text="TMInterface game speed factor").grid(row=0,column=0,sticky="w")
        ttk.Spinbox(frm,from_=0.25,to=100.0,increment=0.25,textvariable=self.speed_var,width=10).grid(row=0,column=1,padx=8)
        ttk.Button(frm,text="Apply speed",command=self._apply_speed).grid(row=0,column=2)
        self.threads_var=tk.IntVar(value=self.trainer.worker_threads)
        ttk.Label(frm,text="Background checkpoint threads").grid(row=1,column=0,sticky="w")
        ttk.Spinbox(frm,from_=1,to=16,textvariable=self.threads_var,width=10).grid(row=1,column=1,padx=8)
        ttk.Button(frm,text="Apply threads",command=lambda:self.trainer.set_worker_threads(int(self.threads_var.get()))).grid(row=1,column=2)
        ttk.Label(frm,text="One game process owns the real camera. Virtual agents are multiplexed through saved TMInterface states.").grid(row=2,column=0,columnspan=3,pady=20,sticky="w")

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
        hwnd=self.trainer.find_game_window()
        if not hwnd:return
        try:
            rect=wintypes.RECT(); ctypes.windll.user32.GetWindowRect(hwnd,ctypes.byref(rect))
            img=ImageGrab.grab(bbox=(rect.left,rect.top,rect.right,rect.bottom),all_screens=True)
            img.thumbnail((900,620))
            self.live_photo=ImageTk.PhotoImage(img.convert("RGB")); self.live_label.configure(image=self.live_photo,text="")
        except Exception: pass

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
            s=self.trainer.ui_snapshot(); self.generation.config(text=f"Generation {s['generation']}"); self.best.config(text=f"Best {s['best']:.2f}"); self.active.config(text=f"Active {s['active']}/50"); self.phase.config(text=s["phase"])
            a=s["focused"]; self.focus_label.config(text=f"Focused agent: {a['id']}")
            for key in ("speed","distance","fitness","avg","lap","wall","front","left","right"):
                val=a[key]; getattr(self,key+"_label").config(text=f"{key}: {val:.2f}" if isinstance(val,float) else f"{key}: {val}")
            self.stats.delete("1.0","end"); self.stats.insert("end",f"Generation: {s['generation']}\nBest fitness: {s['best']:.3f}\nMean fitness: {s['mean']:.3f}\nActive: {s['active']}/50\nTraining ticks: {s.get('ticks',0)}\nGame speed: {s['speed_factor']}x\nMap: {self.trainer.map_name}\nFocused command: steer={a['steer']:+.3f}, gas={a['gas']:+.3f}\nLap: {a['lap']}  Lap time: {a['lap_time']:.3f}s\nCheckpoints: {a['checkpoints']}\n")
            self._draw_wall(s); self._draw_replay(); self._capture_game()
        except Exception: pass
        self.root.after(200,self.refresh)

    def close(self):
        self.trainer.stop(); self.root.destroy()

    def run(self): self.root.mainloop()
