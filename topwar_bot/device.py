"""Thin wrapper around adb for screenshots and touch input."""
import random
import subprocess
import time

import cv2
import numpy as np


class Device:
    def __init__(self, serial=None, adb="adb", tap_jitter=3):
        self.serial = serial
        self.adb_path = adb
        self.tap_jitter = tap_jitter

    def _cmd(self, *args):
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd + list(args)

    def adb(self, *args, timeout=30):
        return subprocess.run(self._cmd(*args), capture_output=True, timeout=timeout, check=True).stdout

    def shell(self, command, timeout=30):
        return self.adb("shell", command, timeout=timeout).decode(errors="replace").strip()

    def screenshot(self):
        """Return the current screen as a BGR numpy array."""
        png = self.adb("exec-out", "screencap", "-p")
        img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError("Failed to decode screenshot from device")
        return img

    def _jitter(self, x, y):
        j = self.tap_jitter
        return int(x + random.randint(-j, j)), int(y + random.randint(-j, j))

    def tap(self, x, y):
        x, y = self._jitter(x, y)
        self.shell(f"input tap {x} {y}")

    def drag(self, x1, y1, x2, y2, duration_ms=450):
        """Drag from one point to another (a slow swipe acts as a drag in Top War)."""
        x1, y1 = self._jitter(x1, y1)
        x2, y2 = self._jitter(x2, y2)
        self.shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")

    def back(self):
        self.shell("input keyevent KEYCODE_BACK")

    def start_app(self, package):
        self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")

    def is_app_foreground(self, package):
        out = self.shell("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
        return package in out

    def screen_size(self):
        out = self.shell("wm size")  # "Physical size: 1280x720"
        w, h = out.split(":")[-1].strip().split("x")
        return int(w), int(h)

    @staticmethod
    def sleep(seconds, spread=0.15):
        time.sleep(max(0.0, seconds * random.uniform(1 - spread, 1 + spread)))
