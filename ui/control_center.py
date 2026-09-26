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
        self.root.title("TMRL Control Center — Native AI Bridge Trainer")
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

    def _build_replay(self):
        """Build a lightweight replay tab compatible with the current detached trainer."""
        self.replay_frame = tk.Frame(self.replay_tab, bg="#0d1117")
        self.replay_frame.pack(fill="both", expand=True)
        tk.Label(
            self.replay_frame,
            text="Replay / training history",
            bg="#0d1117",
            fg="#e8edf2",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", padx=18, pady=(18, 8))
        self.replay_status = tk.Label(
            self.replay_frame,
            text="Replay data is generated from the detached AI simulation.",
            bg="#0d1117",
            fg="#9aa7b2",
            font=("Segoe UI", 10),
        )
        self.replay_status.pack(anchor="w", padx=18)

    def _build_race(self):
        """Build the race/training setup tab."""
        self.race_frame = tk.Frame(self.race_tab, bg="#0d1117")
        self.race_frame.pack(fill="both", expand=True)
        tk.Label(
            self.race_frame,
            text="Race Setup",
            bg="#0d1117",
            fg="#e8edf2",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", padx=18, pady=(18, 12))
        tk.Label(
            self.race_frame,
            text="AI ghosts train independently in the detached simulator. Your TMNF car is not controlled.",
            bg="#0d1117",
            fg="#9aa7b2",
            wraplength=760,
            justify="left",
        ).pack(anchor="w", padx=18, pady=6)

    def _build_settings(self):
        """Build trainer settings controls."""
        self.settings_frame = tk.Frame(self.settings_tab, bg="#0d1117")
        self.settings_frame.pack(fill="both", expand=True)
        tk.Label(
            self.settings_frame,
            text="Training Settings",
            bg="#0d1117",
            fg="#e8edf2",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", padx=18, pady=(18, 12))
        tk.Label(
            self.settings_frame,
            text="Use the controls below to keep CPU usage safe while training.",
            bg="#0d1117",
            fg="#9aa7b2",
        ).pack(anchor="w", padx=18, pady=4)

        row = tk.Frame(self.settings_frame, bg="#0d1117")
        row.pack(fill="x", padx=18, pady=12)
        tk.Label(row, text="Ghost count", bg="#0d1117", fg="#e8edf2").pack(side="left")
        self.agent_count_var = tk.IntVar(value=self.trainer.agent_count)
        tk.Spinbox(
            row,
            from_=1,
            to=int(self.trainer.engine.population.shape[0]),
            textvariable=self.agent_count_var,
            width=6,
            command=lambda: self.trainer.set_agent_count(self.agent_count_var.get()),
        ).pack(side="left", padx=10)

        tk.Label(row, text="Simulator speed", bg="#0d1117", fg="#e8edf2").pack(side="left", padx=(24, 0))
        self.speed_var = tk.DoubleVar(value=self.trainer.sim_speed)
        tk.Spinbox(
            row,
            from_=0.1,
            to=5.0,
            increment=0.1,
            textvariable=self.speed_var,
            width=6,
            command=lambda: self.trainer.set_game_speed(self.speed_var.get()),
        ).pack(side="left", padx=10)

        scale = tk.Frame(self.settings_frame, bg="#0d1117")
        scale.pack(fill="x", padx=18, pady=12)
        tk.Label(
            scale, text="Live AI scaling", bg="#0d1117", fg="#e8edf2",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")
        self.adaptive_var = tk.BooleanVar(value=self.trainer.adaptive_cpu)
        tk.Checkbutton(
            scale,
            text="Adaptive CPU scaling",
            variable=self.adaptive_var,
            command=lambda: self.trainer.set_adaptive_cpu(self.adaptive_var.get()),
            bg="#0d1117", fg="#e8edf2", selectcolor="#182028",
            activebackground="#0d1117", activeforeground="#e8edf2",
        ).pack(anchor="w", pady=4)

        scale_row = tk.Frame(scale, bg="#0d1117")
        scale_row.pack(fill="x", pady=4)
        tk.Label(scale_row, text="Minimum AI", bg="#0d1117", fg="#e8edf2").pack(side="left")
        self.min_agents_var = tk.IntVar(value=self.trainer.cpu_min_agents)
        tk.Spinbox(
            scale_row, from_=1, to=int(self.trainer.engine.population.shape[0]),
            width=5, textvariable=self.min_agents_var,
            command=lambda: self.trainer.set_cpu_min_agents(self.min_agents_var.get()),
        ).pack(side="left", padx=8)
        tk.Label(scale_row, text="Maximum AI", bg="#0d1117", fg="#e8edf2").pack(side="left", padx=(20, 0))
        self.max_agents_var = tk.IntVar(value=self.trainer.cpu_max_agents)
        tk.Spinbox(
            scale_row, from_=1, to=int(self.trainer.engine.population.shape[0]),
            width=5, textvariable=self.max_agents_var,
            command=lambda: self.trainer.set_cpu_max_agents(self.max_agents_var.get()),
        ).pack(side="left", padx=8)
        tk.Label(scale_row, text="Step", bg="#0d1117", fg="#e8edf2").pack(side="left", padx=(20, 0))
        self.scale_step_var = tk.IntVar(value=self.trainer.cpu_scale_step)
        tk.Spinbox(scale_row, from_=1, to=10, width=5, textvariable=self.scale_step_var, command=lambda: self.trainer.set_cpu_scale_step(self.scale_step_var.get())).pack(side="left", padx=8)

        camera = tk.Frame(self.settings_frame, bg="#0d1117")
        camera.pack(fill="x", padx=18, pady=12)
        tk.Label(
            camera, text="Per-car camera", bg="#0d1117", fg="#e8edf2",
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w")
        tk.Label(
            camera,
            text="Player: player_camera   |   AI: ai_camera_1 ... ai_camera_N",
            bg="#0d1117", fg="#9aa7b2",
        ).pack(anchor="w", pady=3)
        tk.Label(
            camera,
            text="Selecting an AI will target that AI's native camera once the TMNF bridge is active.",
            bg="#0d1117", fg="#9aa7b2", wraplength=800, justify="left",
        ).pack(anchor="w")

    def _build_dashboard(self):
        left=ttk.Frame(self.dashboard,padding=12); left.pack(side="left",fill="both",expand=True)
        right=ttk.Frame(self.dashboard,padding=12); right.pack(side="right",fill="y")
        self.stats=tk.Text(left,height=20,width=72,bg="#101318",fg="#e8edf2",insertbackground="white"); self.stats.pack(fill="both",expand=True)
        self.focus_label=ttk.Label(right,text="Focused agent: 0",font=("Segoe UI",14,"bold")); self.focus_label.pack(anchor="w",pady=5)
        for key in ("speed","distance","fitness","avg","lap","wall","front","left","right"):
            lab=ttk.Label(right,text=f"{key}: 0"); lab.pack(anchor="w",pady=3); setattr(self,key+"_label",lab)

    def _build_agents(self):
        cols=("id","vehicle_id","alive","speed","distance","fitness","lap","lap_time","avg","wall")
        self.tree=ttk.Treeview(self.agents_tab,columns=cols,show="headings",height=28)
        names={"id":"Agent","vehicle_id":"Vehicle ID","alive":"Alive","speed":"Speed km/h","distance":"Distance","fitness":"Fitness","lap":"Lap","lap_time":"Lap time","avg":"Avg speed","wall":"Wall penalty"}
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
            text="LIVE TMNF GAMEPLAY — PER-CAR CAMERA WALL",
            font=("Segoe UI", 12, "bold"),
        ).pack(side="left")
        self.wall_status = ttk.Label(
            header,
            text="player_car / player_camera • selecting AI targets ai_camera_N",
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

    def _select_agent(self, _event=None):
        """Handle selection in the Agents tab and focus that live AI."""
        try:
            selection = self.tree.selection()
            if not selection:
                return
            item = selection[0]
            values = self.tree.item(item, "values")
            if not values:
                return
            agent_id = int(values[0])
            self.trainer.set_focus(agent_id)
            self.camera_selected_agent = agent_id
        except (ValueError, TypeError, IndexError):
            return

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
                f"{agent.vehicle_id}  |  "
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
                text=f"{a.vehicle_id}   {a.speed_kmh:.0f} km/h",
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
        self.camera_agent_label.config(text=f"{selected.vehicle_id} — LIVE")
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
            f"Vehicle: {selected.vehicle_id}\n"
            f"Camera: {selected.camera_id}\n"
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

        for child in self.wall_inner.winfo_children():
            child.destroy()

        cols = 2 if len(live) <= 4 else 3
        for col in range(cols):
            self.wall_inner.columnconfigure(col, weight=1)

        self.wall_photos = []

        if frame is not None:
            tile_w, tile_h = 324, 182
            scale = min(tile_w / frame.width, tile_h / frame.height)
            resized = frame.resize(
                (max(1, int(frame.width * scale)),
                 max(1, int(frame.height * scale)))
            )
            tile_image = Image.new("RGB", (tile_w, tile_h), "black")
            tile_image.paste(
                resized,
                ((tile_w - resized.width) // 2,
                 (tile_h - resized.height) // 2),
            )
            status = (
                f"REAL TMNF FRAME • {len(live)} active AI • "
                f"{frame.width}x{frame.height}"
            )
        else:
            tile_image = None
            status = (
                f"TMNF capture unavailable • {len(live)} active AI • "
                "AI selection still enabled"
            )

        for index, agent in enumerate(live):
            row, col = divmod(index, cols)

            if tile_image is not None:
                tile = self._make_wall_tile(
                    self.wall_inner,
                    tile_image.copy(),
                    agent,
                )
            else:
                selected = agent.agent_id == self.camera_selected_agent
                tile = tk.Frame(
                    self.wall_inner,
                    bg="#0d1117",
                    highlightthickness=3 if selected else 1,
                    highlightbackground="#4fc3f7" if selected else "#30363d",
                    width=330,
                    height=225,
                )
                tile.pack_propagate(False)

                label = tk.Label(
                    tile,
                    text=(
                        f"{agent.vehicle_id}\n\n"
                        "LIVE AI\n"
                        f"{agent.speed_kmh:.0f} km/h\n"
                        "TMNF FRAME UNAVAILABLE"
                    ),
                    bg="#0d1117",
                    fg="#e8edf2",
                    font=("Consolas", 12, "bold"),
                    justify="center",
                    cursor="hand2",
                )
                label.pack(fill="both", expand=True)

                label.bind(
                    "<Button-1>",
                    lambda _event, aid=agent.agent_id:
                    self._select_camera_agent(aid),
                )
                tile.bind(
                    "<Button-1>",
                    lambda _event, aid=agent.agent_id:
                    self._select_camera_agent(aid),
                )

            tile.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            self.wall_photos.append(tile)

        self.wall_status.config(text=status)

    def _draw_replay(self):
        """Refresh the lightweight replay/training-history panel."""
        if not hasattr(self, "replay_status"):
            return
        try:
            snap = self.trainer.replay_snapshot(self.replay_agent)
            self.replay_status.config(
                text=(
                    f"Generation {snap.get('generation', 0)}  |  "
                    f"Agent {snap.get('agent_id', self.replay_agent)}  |  "
                    f"Frame {snap.get('index', self.replay_index)}  |  "
                    f"Samples {snap.get('samples', 0)}"
                )
            )
        except Exception:
            pass

    def refresh(self):
        try:
            s=self.trainer.ui_snapshot(); self.generation.config(text=f"Generation {s['generation']}"); self.best.config(text=f"Best {s['best']:.2f}"); self.active.config(text=f"Ghosts {s['active']}/{s['agent_count']}"); self.phase.config(text=s["phase"])
            a=s["focused"]; self.focus_label.config(text=f"Focused: {a.get('vehicle_id', 'ai_thread_1')}")
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
