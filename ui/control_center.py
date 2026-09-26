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
        # The wall shows real pixels captured from the TMNF window.
        # It deliberately does not fabricate a road/sky scene for the wall.
        outer = ttk.Frame(self.camera_tab, padding=8)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 6))
        ttk.Label(
            header,
            text="LIVE TMNF GAMEPLAY — AI CAMERA WALL",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")
        self.wall_status = ttk.Label(
            header,
            text="Waiting for TMNF window...",
        )
        self.wall_status.pack(side="right")

        body = ttk.Frame(outer)
        body.pack(fill="both", expand=True)

        wall_frame = ttk.Frame(body)
        wall_frame.pack(side="left", fill="both", expand=True)

        self.wall_canvas = tk.Canvas(
            wall_frame,
            bg="#080b0f",
            highlightthickness=0,
        )
        self.wall_scroll = ttk.Scrollbar(
            wall_frame,
            orient="vertical",
            command=self.wall_canvas.yview,
        )
        self.wall_canvas.configure(yscrollcommand=self.wall_scroll.set)
        self.wall_scroll.pack(side="right", fill="y")
        self.wall_canvas.pack(side="left", fill="both", expand=True)

        self.wall_inner = ttk.Frame(self.wall_canvas)
        self.wall_window = self.wall_canvas.create_window(
            (0, 0),
            window=self.wall_inner,
            anchor="nw",
        )
        self.wall_inner.bind(
            "<Configure>",
            lambda _e: self.wall_canvas.configure(
                scrollregion=self.wall_canvas.bbox("all")
            ),
        )
        self.wall_canvas.bind(
            "<Configure>",
            lambda e: self.wall_canvas.itemconfigure(
                self.wall_window,
                width=max(e.width, 700),
            ),
        )

        right = ttk.Frame(body, padding=(8, 0, 0, 0), width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        ttk.Label(
            right,
            text="SELECT AI",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        self.active_ghost_frame = ttk.Frame(right)
        self.active_ghost_frame.pack(fill="x")

        ttk.Separator(right).pack(fill="x", pady=10)
        self.camera_agent_label = ttk.Label(
            right,
            text="Select a live ghost",
            font=("Segoe UI", 12, "bold"),
        )
        self.camera_agent_label.pack(anchor="w", pady=3)

        self.camera_stats = tk.Text(
            right,
            height=18,
            width=32,
            bg="#101318",
            fg="#e8edf2",
            insertbackground="white",
            state="disabled",
        )
        self.camera_stats.pack(fill="x", pady=4)

        ttk.Label(
            right,
            text=(
                "Each tile contains the actual TMNF gameplay frame captured "
                "from the game window. AI telemetry and the selected car are "
                "shown on top of the real frame. Click an AI to focus it."
            ),
            wraplength=280,
        ).pack(anchor="w", pady=8)

        self.camera_selected_agent = 0
        self.wall_photos = []
        self.wall_last_capture = 0.0
        self.wall_capture_interval = 0.20
        self.wall_frame_image = None

    def _select_camera_agent(self, agent_id):
        self.camera_selected_agent = int(agent_id)
        self.trainer.set_focus(int(agent_id))

    def _capture_tm_gameplay(self):
        """Capture the real TMNF window; return a PIL image or None."""
        try:
            hwnd = self.trainer.find_game_window()
            if not hwnd:
                return None

            user32 = ctypes.windll.user32
            rect = wintypes.RECT()
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return None

            left, top = int(rect.left), int(rect.top)
            right, bottom = int(rect.right), int(rect.bottom)
            if right <= left or bottom <= top:
                return None

            # ImageGrab captures the rendered TMNF window, not our synthetic
            # simulator. The Control Center itself is outside this rectangle.
            return ImageGrab.grab(
                bbox=(left, top, right, bottom),
                include_layered_windows=True,
            ).convert("RGB")
        except Exception:
            return None

    def _make_wall_tile(self, parent, image, agent):
        selected = agent.agent_id == self.camera_selected_agent
        tile = tk.Frame(
            parent,
            bg="#0d1117",
            highlightthickness=3 if selected else 1,
            highlightbackground="#4fc3f7" if selected else "#30363d",
            bd=0,
        )
        tile.pack_propagate(False)
        tile.configure(width=330, height=225)

        # Keep the complete gameplay frame visible, with no fake camera scene.
        tile_image = ImageTk.PhotoImage(image)
        label = tk.Label(
            tile,
            image=tile_image,
            bg="#000000",
            bd=0,
            cursor="hand2",
        )
        label.image = tile_image
        label.pack(fill="both", expand=True)

        def select(_event=None, aid=agent.agent_id):
            self._select_camera_agent(aid)

        label.bind("<Button-1>", select)
        tile.bind("<Button-1>", select)

        overlay = tk.Label(
            tile,
            text=(
                f"AI {agent.agent_id:02d}  |  "
                f"{agent.speed_kmh:.0f} km/h\n"
                f"FIT {self.trainer.engine.fitness(agent.forward_progress, agent.average_speed, agent.wall_penalty):.1f}"
            ),
            justify="left",
            anchor="nw",
            bg="#000000",
            fg="#ffffff",
            padx=6,
            pady=4,
            font=("Consolas", 9, "bold"),
        )
        overlay.place(x=5, y=5)
        overlay.bind("<Button-1>", select)

        return tile_image

    def _refresh_ghost_camera(self, snapshot):
        if not hasattr(self, "wall_inner"):
            return

        live = [
            a for a in self.trainer.telemetry.agents[:self.trainer.agent_count]
            if a.alive
        ]

        if live and self.camera_selected_agent not in [a.agent_id for a in live]:
            self.camera_selected_agent = live[0].agent_id

        # Active-agent selector on the right.
        for child in self.active_ghost_frame.winfo_children():
            child.destroy()

        for a in live:
            selected = a.agent_id == self.camera_selected_agent
            btn = tk.Button(
                self.active_ghost_frame,
                text=f"AI {a.agent_id:02d}   {a.speed_kmh:.0f} km/h",
                command=lambda aid=a.agent_id: self._select_camera_agent(aid),
                relief="sunken" if selected else "raised",
                bd=2,
                anchor="w",
            )
            btn.pack(fill="x", pady=2)

        if not live:
            self.camera_selected_agent = 0
            for child in self.wall_inner.winfo_children():
                child.destroy()
            self.wall_status.config(text="No active AI ghosts")
            self.camera_agent_label.config(text="No live ghost")
            self.camera_stats.config(state="normal")
            self.camera_stats.delete("1.0", "end")
            self.camera_stats.insert("end", "No active agents in this generation.")
            self.camera_stats.config(state="disabled")
            self.wall_photos = []
            return

        selected = next(
            (a for a in live if a.agent_id == self.camera_selected_agent),
            live[0],
        )
        self.camera_selected_agent = selected.agent_id

        # Stats are still per simulated AI, while the image itself is real TMNF.
        self.camera_agent_label.config(text=f"AI {selected.agent_id:02d} — LIVE")
        self.camera_stats.config(state="normal")
        self.camera_stats.delete("1.0", "end")
        avg = selected.average_speed
        fitness = self.trainer.engine.fitness(
            selected.forward_progress,
            avg,
            selected.wall_penalty,
        )
        self.camera_stats.insert(
            "end",
            f"Generation: {self.trainer.engine.generation}\n"
            f"Status: ACTIVE / TRAINING\n"
            f"Speed: {selected.speed_kmh:.1f} km/h\n"
            f"Average speed: {avg:.1f} km/h\n"
            f"Distance: {selected.distance:.2f} m\n"
            f"Forward progress: {selected.forward_progress:.2f} m\n"
            f"Fitness: {fitness:.2f}\n"
            f"Steer: {selected.last_steer:+.3f}\n"
            f"Throttle/brake: {selected.last_gas:+.3f}\n"
            f"Yaw: {selected.yaw_pitch_roll[0]:+.3f} rad\n"
            f"Wall penalty: {selected.wall_penalty:.2f}\n"
            f"Alive time: {selected.race_time_ms / 1000.0:.2f} s\n"
        )
        self.camera_stats.config(state="disabled")

        now = time.monotonic()
        if now - self.wall_last_capture < self.wall_capture_interval:
            return
        self.wall_last_capture = now

        frame = self._capture_tm_gameplay()
        if frame is None:
            self.wall_status.config(text="TMNF window not found / capture unavailable")
            return

        # Resize the real game frame once, then reuse it for all AI tiles.
        tile_w, tile_h = 324, 182
        scale = min(tile_w / frame.width, tile_h / frame.height)
        resized = frame.resize(
            (max(1, int(frame.width * scale)), max(1, int(frame.height * scale)))
        )
        tile_image = Image.new("RGB", (tile_w, tile_h), "black")
        tile_image.paste(
            resized,
            ((tile_w - resized.width) // 2, (tile_h - resized.height) // 2),
        )

        for child in self.wall_inner.winfo_children():
            child.destroy()

        cols = 2 if len(live) <= 4 else 3
        for col in range(cols):
            self.wall_inner.columnconfigure(col, weight=1)

        self.wall_photos = []
        for index, agent in enumerate(live):
            row, col = divmod(index, cols)
            tile = self._make_wall_tile(
                self.wall_inner,
                tile_image.copy(),
                agent,
            )
            tile.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self.wall_photos.append(tile)

        self.wall_status.config(
            text=f"REAL TMNF FRAME • {len(live)} active AI • {frame.width}x{frame.height}"
        )
    def _select_camera_agent(self, agent_id):
        self.camera_selected_agent = int(agent_id)
        self.trainer.set_focus(int(agent_id))

    def _refresh_ghost_camera(self, snapshot):
        if not hasattr(self, "ghost_camera_canvas"):
            return

        frame = self.active_ghost_frame
        for child in frame.winfo_children():
            child.destroy()

        live = [
            a for a in self.trainer.telemetry.agents[:self.trainer.agent_count]
            if a.alive
        ]
        if live and self.camera_selected_agent not in [a.agent_id for a in live]:
            self.camera_selected_agent = live[0].agent_id

        for a in live:
            selected = a.agent_id == self.camera_selected_agent
            btn = tk.Button(
                frame,
                text=f"AI {a.agent_id:02d}   {a.speed_kmh:.0f} km/h",
                command=lambda aid=a.agent_id: self._select_camera_agent(aid),
                relief="sunken" if selected else "raised",
                bd=2,
                anchor="w",
            )
            btn.pack(fill="x", pady=2)

        if not live:
            self.camera_selected_agent = 0
            self.ghost_camera_canvas.delete("all")
            self.ghost_camera_canvas.create_text(
                20, 20, anchor="nw",
                text="NO ACTIVE GHOSTS",
                fill="white",
                font=("Segoe UI", 16, "bold"),
            )
            self.camera_agent_label.config(text="No live ghost")
            self.camera_stats.config(state="normal")
            self.camera_stats.delete("1.0", "end")
            self.camera_stats.insert("end", "No active agents in this generation.")
            self.camera_stats.config(state="disabled")
            return

        selected = next(
            (a for a in live if a.agent_id == self.camera_selected_agent),
            live[0],
        )
        self.camera_selected_agent = selected.agent_id

        self.camera_agent_label.config(
            text=f"AI {selected.agent_id:02d} — LIVE"
        )
        self.camera_stats.config(state="normal")
        self.camera_stats.delete("1.0", "end")
        avg = selected.average_speed
        fitness = self.trainer.engine.fitness(
            selected.forward_progress, avg, selected.wall_penalty
        )
        self.camera_stats.insert(
            "end",
            f"Generation: {self.trainer.engine.generation}\n"
            f"Status: ACTIVE / TRAINING\n"
            f"Speed: {selected.speed_kmh:.1f} km/h\n"
            f"Average speed: {avg:.1f} km/h\n"
            f"Distance: {selected.distance:.2f} m\n"
            f"Forward progress: {selected.forward_progress:.2f} m\n"
            f"Fitness: {fitness:.2f}\n"
            f"Steer: {selected.last_steer:+.3f}\n"
            f"Throttle/brake: {selected.last_gas:+.3f}\n"
            f"Yaw: {selected.yaw_pitch_roll[0]:+.3f} rad\n"
            f"Wall penalty: {selected.wall_penalty:.2f}\n"
            f"Alive time: {selected.race_time_ms / 1000.0:.2f} s\n"
        )
        self.camera_stats.config(state="disabled")

        self.ghost_overlay.draw_selected_camera(
            self.ghost_camera_canvas,
            selected,
            live,
        )

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

    def refresh(self):
        try:
            s=self.trainer.ui_snapshot(); self.generation.config(text=f"Generation {s['generation']}"); self.best.config(text=f"Best {s['best']:.2f}"); self.active.config(text=f"Ghosts {s['active']}/{s['agent_count']}"); self.phase.config(text=s["phase"])
            a=s["focused"]; self.focus_label.config(text=f"Focused agent: {a['id']}")
            for key in ("speed","distance","fitness","avg","lap","wall","front","left","right"):
                val=a[key]; getattr(self,key+"_label").config(text=f"{key}: {val:.2f}" if isinstance(val,float) else f"{key}: {val}")
            self.stats.delete("1.0","end"); self.stats.insert("end",f"Generation: {s['generation']}\nBest fitness: {s['best']:.3f}\nMean fitness: {s['mean']:.3f}\nActive: {s['active']}/50\nTraining ticks: {s.get('ticks',0)}\nGame speed: {s['speed_factor']}x\nMap: {self.trainer.map_name}\nLast error: {s.get('last_error','')}\nFocused command: steer={a['steer']:+.3f}, gas={a['gas']:+.3f}\nLap: {a['lap']}  Lap time: {a['lap_time']:.3f}s\nCheckpoints: {a['checkpoints']}\n")
            self._refresh_ghost_camera(s); self._draw_replay()
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
