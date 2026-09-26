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
        self.root.title("TMRL Ghost Overlay")
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
        set_style(hwnd, -4, ctypes.cast(self._wndproc, ctypes.c_void_p).value)

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
    def _project(agent_pos, player_pos, player_yaw, player_pitch, width, height):
        # Approximate the default chase camera using the player's car transform.
        yaw = float(player_yaw)
        pitch = float(player_pitch)
        cy = math.cos(yaw)
        sy = math.sin(yaw)
        forward = (sy, 0.0, cy)

        # Raise camera and place it behind the player's car.
        camera = (
            player_pos[0] - forward[0] * 6.0,
            player_pos[1] + 2.8,
            player_pos[2] - forward[2] * 6.0,
        )
        rel = (
            agent_pos[0] - camera[0],
            agent_pos[1] - camera[1],
            agent_pos[2] - camera[2],
        )

        right = (cy, 0.0, -sy)
        horiz = rel[0] * right[0] + rel[2] * right[2]
        depth = rel[0] * forward[0] + rel[2] * forward[2]

        # Basic pitch rotation.
        cp = math.cos(pitch)
        sp = math.sin(pitch)
        vert = rel[1] * cp - depth * sp
        depth2 = rel[1] * sp + depth * cp

        if depth2 <= 0.5:
            return None

        fov = math.radians(90.0)
        focal = (width * 0.5) / math.tan(fov * 0.5)
        sx = width * 0.5 + horiz * focal / depth2
        sy2 = height * 0.54 - vert * focal / depth2

        if sx < -100 or sx > width + 100 or sy2 < -100 or sy2 > height + 100:
            return None
        return sx, sy2, depth2

    def _draw_car(self, x, y, size, alive, agent_id, steer):
        color = "#9fe8ff" if alive else "#666666"
        outline = "#ffffff" if agent_id == self.trainer.focus else "#69b8cc"

        # Semi-transparent ghost-car silhouette: roof + body + wheels.
        body_w = max(8.0, size * 0.9)
        body_h = max(4.0, size * 0.42)
        roof_w = body_w * 0.58
        roof_h = body_h * 0.75

        self.canvas.create_polygon(
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
            self.canvas.create_oval(
                wx - wheel_r,
                y + body_h * 0.15 - wheel_r,
                wx + wheel_r,
                y + body_h * 0.15 + wheel_r,
                fill="#20252a",
                outline="",
            )

        if agent_id == self.trainer.focus:
            self.canvas.create_text(
                x,
                y - body_h - roof_h - 10,
                text=f"AI {agent_id:02d}",
                fill="white",
                font=("Consolas", 8, "bold"),
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
            self.root.after(33, self.update)
            return

        p = player["position"]
        yaw = player["yaw"]
        pitch = player["pitch"]

        for agent in self.trainer.telemetry.agents:
            projected = self._project(
                agent.position,
                p,
                yaw,
                pitch,
                width,
                height,
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
