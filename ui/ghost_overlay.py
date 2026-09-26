"""Click-through transparent ghost-car overlay for the TMNF window."""
from __future__ import annotations

import ctypes
import math
import tkinter as tk
from ctypes import wintypes


GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

WM_NCHITTEST = 0x0084
HTTRANSPARENT = -1
SW_SHOWNOACTIVATE = 4
SW_HIDE = 0
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


class GhostOverlay:
    def __init__(self, trainer):
        self.trainer = trainer
        self.root = tk.Toplevel()
        self.root.withdraw()
        self.root.title("TMRL Ghost Overlay — up to 50")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.72)
        self.root.configure(bg="#ff00ff")
        try:
            self.root.attributes("-transparentcolor", "#ff00ff")
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(
            self.root,
            bg="#ff00ff",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)
        self._make_click_through()
        self.visible = True
        self.last_hwnd = None
        self._old_wndproc = None
        self._wndproc = None

    def _make_click_through(self):
        hwnd = self.root.winfo_id()
        user32 = ctypes.windll.user32
        get_style = user32.GetWindowLongPtrW
        set_style = user32.SetWindowLongPtrW

        # ctypes does not know the Win32 LONG_PTR signatures automatically.
        # Explicit pointer-sized types prevent 64-bit callback addresses from
        # being truncated/treated as 32-bit integers.
        ptr_t = ctypes.c_ssize_t
        get_style.argtypes = [wintypes.HWND, ctypes.c_int]
        get_style.restype = ptr_t
        set_style.argtypes = [wintypes.HWND, ctypes.c_int, ptr_t]
        set_style.restype = ptr_t

        style = get_style(hwnd, GWL_EXSTYLE)
        set_style(
            hwnd,
            GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
        )

        # WS_EX_TRANSPARENT affects painting order, but does NOT by itself
        # make mouse input pass through. Return HTTRANSPARENT from the native
        # hit-test so Windows sends clicks to the game underneath instead.
        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_longlong,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )
        self._wndproc = WNDPROC(self._overlay_wndproc)
        # Get the existing Tk window procedure and replace it. Keep both the
        # callback and old pointer alive for the lifetime of the overlay.
        get_proc = user32.GetWindowLongPtrW
        self._old_wndproc = get_proc(hwnd, -4)
        wndproc_ptr = ctypes.cast(self._wndproc, ctypes.c_void_p).value
        set_style(hwnd, -4, ctypes.c_ssize_t(wndproc_ptr).value)

        user32.SetWindowPos(
            hwnd,
            HWND_TOPMOST,
            0, 0, 0, 0,
            SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
        )

    def _overlay_wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_NCHITTEST:
            return HTTRANSPARENT

        user32 = ctypes.windll.user32
        call_proc = user32.CallWindowProcW
        call_proc.restype = ctypes.c_longlong
        call_proc.argtypes = [
            ctypes.c_void_p,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        return call_proc(
            ctypes.c_void_p(self._old_wndproc),
            hwnd,
            msg,
            wparam,
            lparam,
        )

    def _show_native(self, visible):
        hwnd = self.root.winfo_id()
        ctypes.windll.user32.ShowWindow(
            hwnd,
            SW_SHOWNOACTIVATE if visible else SW_HIDE,
        )
        if visible:
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                HWND_TOPMOST,
                0, 0, 0, 0,
                SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE,
            )

    def close(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def set_visible(self, visible: bool):
        self.visible = bool(visible)
        self._show_native(self.visible)

    def _game_rect(self):
        hwnd = self.trainer.find_game_window()
        if not hwnd:
            return None

        rect = wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        if rect.right <= rect.left or rect.bottom <= rect.top:
            return None
        return hwnd, rect.left, rect.top, rect.right, rect.bottom

    @staticmethod
    def _project(agent_pos, camera_pos, camera_yaw, camera_pitch, width, height, fov_deg=92.0):
        """Project a world point through a TMNF-like chase camera.

        TMInterface gives us the player's world transform, while the detached
        simulator gives us ghost world transforms. This keeps the overlay
        independent of TMNF input/control and makes the ghosts line up with
        the player's actual view much more reliably than the old fixed camera.
        """
        yaw = float(camera_yaw)
        pitch = float(camera_pitch)
        forward = (math.sin(yaw), 0.0, math.cos(yaw))
        right = (math.cos(yaw), 0.0, -math.sin(yaw))
        rel = (
            float(agent_pos[0]) - float(camera_pos[0]),
            float(agent_pos[1]) - float(camera_pos[1]),
            float(agent_pos[2]) - float(camera_pos[2]),
        )

        horiz = rel[0] * right[0] + rel[2] * right[2]
        depth = rel[0] * forward[0] + rel[2] * forward[2]

        cp = math.cos(pitch)
        sp = math.sin(pitch)
        vert = rel[1] * cp - depth * sp
        depth2 = rel[1] * sp + depth * cp
        if depth2 <= 0.15:
            return None

        focal = (width * 0.5) / math.tan(math.radians(fov_deg) * 0.5)
        sx = width * 0.5 + horiz * focal / depth2
        sy = height * 0.54 - vert * focal / depth2
        if sx < -180 or sx > width + 180 or sy < -180 or sy > height + 180:
            return None
        return sx, sy, depth2

    def _draw_camera_wall(self, snapshot):
        """Draw one simulated camera view for every live ghost.

        These are detached-simulator camera views: TMNF cannot expose a real
        CGameCtnGhost camera for these agents because they are not native game
        vehicles. The view is nevertheless generated from each agent's actual
        position/yaw, so every tile follows that ghost independently.
        """
        self.wall_canvas.delete("all")
        agents = self.trainer.telemetry.agents[:self.trainer.agent_count]
        live = [a for a in agents if a.alive]
        if not live:
            self.wall_canvas.create_text(
                20, 20, anchor="nw",
                text="No live ghosts",
                fill="white",
                font=("Segoe UI", 12, "bold"),
            )
            return

        cols = 3
        tile_w = 205
        tile_h = 155
        for slot, camera_agent in enumerate(live):
            col = slot % cols
            row = slot // cols
            x = col * tile_w
            y = row * tile_h
            self.wall_canvas.create_rectangle(
                x + 2, y + 2, x + tile_w - 4, y + tile_h - 4,
                fill="#090c10",
                outline="#69b8cc" if camera_agent.agent_id == self.trainer.focus else "#303840",
                width=2,
            )
            inner_w = tile_w - 10
            inner_h = tile_h - 30
            camera_pos = (
                float(camera_agent.position[0]),
                float(camera_agent.position[1]) + 1.6,
                float(camera_agent.position[2]),
            )
            camera_yaw = float(self.trainer.simulator.start_yaw + camera_agent.yaw_pitch_roll[0])
            camera_pitch = 0.0

            # Road/corridor guide, giving the camera a useful forward reference
            # even though the detached simulator does not have TMNF track meshes.
            cx = x + tile_w * 0.5
            horizon = y + 58
            self.wall_canvas.create_polygon(
                cx - 18, y + tile_h - 8,
                cx + 18, y + tile_h - 8,
                cx + 7, horizon,
                cx - 7, horizon,
                fill="#20262c",
                outline="",
            )
            self.wall_canvas.create_line(
                cx - 7, horizon, cx - 18, y + tile_h - 8,
                fill="#68737d",
            )
            self.wall_canvas.create_line(
                cx + 7, horizon, cx + 18, y + tile_h - 8,
                fill="#68737d",
            )

            for other in live:
                if other is camera_agent:
                    continue
                projected = self._project(
                    other.position, camera_pos, camera_yaw, camera_pitch,
                    inner_w, inner_h, 92.0,
                )
                if projected is None:
                    continue
                px, py, depth = projected
                px += x + 5
                py += y + 5
                size = max(3.0, min(22.0, 230.0 / max(depth, 4.0)))
                self._draw_car(px, py, size, True, other.agent_id, other.last_steer)

            self.wall_canvas.create_text(
                x + 8, y + 8, anchor="nw",
                text=f"AI {camera_agent.agent_id:02d}  {camera_agent.speed_kmh:.0f} km/h",
                fill="white",
                font=("Consolas", 9, "bold"),
            )

        self.wall_canvas.configure(scrollregion=(0, 0, cols * tile_w, max(tile_h, math.ceil(len(live) / cols) * tile_h)))


    def _draw_car(self, x, y, size, alive, agent_id, steer, canvas=None):
        if canvas is None:
            canvas = self.canvas
        color = "#9fe8ff" if alive else "#666666"
        outline = "#ffffff" if agent_id == self.trainer.focus else "#69b8cc"

        # Semi-transparent ghost-car silhouette: roof + body + wheels.
        body_w = max(8.0, size * 0.9)
        body_h = max(4.0, size * 0.42)
        roof_w = body_w * 0.58
        roof_h = body_h * 0.75

        canvas.create_polygon(
            x - body_w,
            y + body_h,
            x - body_w * 0.75,
            y - body_h,
            x - roof_w,
            y - body_h - roof_h,
            x + roof_w,
            y - body_h - roof_h,
            x + body_w * 0.75,
            y - body_h,
            x + body_w,
            y + body_h,
            fill=color,
            outline=outline,
            width=1,
        )
        wheel_r = max(2.0, body_h * 0.45)
        for wx in (x - body_w * 0.72, x + body_w * 0.72):
            canvas.create_oval(
                wx - wheel_r,
                y + body_h * 0.15 - wheel_r,
                wx + wheel_r,
                y + body_h * 0.15 + wheel_r,
                fill="#20252a",
                outline="",
            )

        if agent_id == self.trainer.focus:
            canvas.create_text(
                x,
                y - body_h - roof_h - 10,
                text=f"AI {agent_id:02d}",
                fill="white",
                font=("Consolas", 8, "bold"),
            )

    def draw_selected_camera(self, canvas, camera_agent, live_agents):
        """Render the selected ghost's simulated perspective camera."""
        canvas.delete("all")
        width = max(500, canvas.winfo_width())
        height = max(350, canvas.winfo_height())

        yaw = float(self.trainer.simulator.start_yaw + camera_agent.yaw_pitch_roll[0])
        camera_pos = (
            float(camera_agent.position[0]),
            float(camera_agent.position[1]) + 1.45,
            float(camera_agent.position[2]),
        )

        horizon = int(height * 0.43)
        canvas.create_rectangle(0, 0, width, horizon, fill="#17212b", outline="")
        canvas.create_rectangle(0, horizon, width, height, fill="#11161b", outline="")

        cx = width * 0.5
        canvas.create_polygon(
            cx - width * 0.045, height,
            cx + width * 0.045, height,
            cx + width * 0.012, horizon,
            cx - width * 0.012, horizon,
            fill="#343b42", outline="",
        )

        for sign in (-1, 1):
            canvas.create_line(
                cx + sign * width * 0.045, height,
                cx + sign * width * 0.012, horizon,
                fill="#aab3ba",
                width=2,
            )

        for i in range(5):
            y = horizon + 25 + i * 45
            if y < height:
                half = 3 + i * 2
                canvas.create_rectangle(
                    cx - half, y, cx + half, y + 14,
                    fill="#d9dde0", outline="",
                )

        for other in live_agents:
            if other is camera_agent:
                continue
            projected = self._project(
                other.position,
                camera_pos,
                yaw,
                0.0,
                width,
                height,
                90.0,
            )
            if projected is None:
                continue
            px, py, depth = projected
            size = max(6.0, min(70.0, 850.0 / max(depth, 3.0)))
            self._draw_car(
                px, py, size, True, other.agent_id, other.last_steer, canvas=canvas
            )

        canvas.create_text(
            12, 12, anchor="nw",
            text=f"AI {camera_agent.agent_id:02d} CAMERA  |  {camera_agent.speed_kmh:.0f} km/h",
            fill="white",
            font=("Segoe UI", 13, "bold"),
        )
        canvas.create_text(
            12, 38, anchor="nw",
            text="SIMULATED FIRST-PERSON / CHASE VIEW",
            fill="#9fe8ff",
            font=("Consolas", 9, "bold"),
        )

    def update(self):
        if not self.visible:
            return

        game = self._game_rect()
        if not game:
            self._show_native(False)
            self.root.after(100, self.update)
            return

        self._show_native(True)
        hwnd, left, top, right, bottom = game
        self.last_hwnd = hwnd
        width = right - left
        height = bottom - top

        self.root.geometry(f"{width}x{height}+{left}+{top}")
        self.canvas.config(width=width, height=height)
        self.canvas.delete("all")

        player = self.trainer.player_snapshot()
        if player is None:
            count = self.trainer.agent_count
            interval = 33 if count <= 10 else 50 if count <= 25 else 80
            self.root.after(interval, self.update)
            return

        p = player["position"]
        yaw = player["yaw"]
        pitch = player["pitch"]

        # Match the player's chase camera: put the virtual camera slightly
        # above and behind the user's car. Ghosts are therefore rendered in
        # the same screen space while the user keeps complete control of TMNF.
        camera_pos = (
            float(p[0]) - math.sin(yaw) * 4.5,
            float(p[1]) + 2.2,
            float(p[2]) - math.cos(yaw) * 4.5,
        )

        for agent in self.trainer.telemetry.agents[:self.trainer.agent_count]:
            if not agent.alive:
                continue
            projected = self._project(
                agent.position,
                camera_pos,
                yaw,
                pitch,
                width,
                height,
                92.0,
            )
            if projected is None:
                continue
            sx, sy, depth = projected
            size = max(5.0, min(42.0, 520.0 / max(depth, 8.0)))
            self._draw_car(
                sx,
                sy,
                size,
                agent.alive,
                agent.agent_id,
                agent.last_steer,
            )

        self.canvas.create_text(
            12,
            12,
            anchor="nw",
            text=f"TMRL GHOSTS  {sum(a.alive for a in self.trainer.telemetry.agents)}/{len(self.trainer.telemetry.agents)}",
            fill="white",
            font=("Segoe UI", 10, "bold"),
        )
        self.root.after(33, self.update)
