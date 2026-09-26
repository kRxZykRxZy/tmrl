"""Low-overhead Windows CPU usage sampler using only the standard library."""
from __future__ import annotations

import ctypes
from ctypes import wintypes


class CPUUsage:
    def __init__(self):
        self.available = False
        self.last_total = 0
        self.last_idle = 0
        try:
            self.kernel32 = ctypes.windll.kernel32
            self.FILETIME = wintypes.FILETIME
            self.available = True
        except Exception:
            self.kernel32 = None

    @staticmethod
    def _u64(filetime: wintypes.FILETIME) -> int:
        return (int(filetime.dwHighDateTime) << 32) | int(filetime.dwLowDateTime)

    def sample(self) -> float | None:
        if not self.available:
            return None

        idle = self.FILETIME()
        kernel = self.FILETIME()
        user = self.FILETIME()

        if not self.kernel32.GetSystemTimes(
            ctypes.byref(idle),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None

        idle_v = self._u64(idle)
        total_v = self._u64(kernel) + self._u64(user)

        if self.last_total == 0:
            self.last_total = total_v
            self.last_idle = idle_v
            return None

        total_delta = total_v - self.last_total
        idle_delta = idle_v - self.last_idle
        self.last_total = total_v
        self.last_idle = idle_v

        if total_delta <= 0:
            return None

        used = max(0.0, min(100.0, 100.0 * (1.0 - idle_delta / total_delta)))
        return used
