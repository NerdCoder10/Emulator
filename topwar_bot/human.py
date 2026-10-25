"""Human-like input timing, movement and play sessions."""
import datetime as dt
import logging
import math
import random
import time

log = logging.getLogger("topwar")

DEFAULTS = {
    "enabled": True,
    "reaction_mean": 0.55,        # typical seconds between actions
    "reaction_sigma": 0.35,       # log-normal spread; a few actions are much slower
    "hesitation_chance": 0.06,    # chance of an extra 1-4 s pause before an action
    "tap_spread": 6,              # std-dev in px around the target centre
    "press_ms": [45, 130],        # finger-down time for a tap
    "drag_ms": [350, 750],
    "drag_steps": 7,              # points along a curved drag
    "curved_drags": True,         # needs Android 11+ (input motionevent); falls back to swipe
    "miss_chance": 0.04,          # chance to overlook a target this cycle
    "shuffle_chance": 0.3,        # chance to do merges in a looser order
    "session_minutes": [25, 70],  # play this long...
    "break_minutes": [4, 25],     # ...then take a break this long
    "idle_chance": 0.08,          # chance per cycle of a short idle (reading the screen)
    "idle_seconds": [5, 40],
    "active_hours": None,         # e.g. [8, 23] - only play between 08:00 and 23:00
}


class Human:
    def __init__(self, cfg=None, rng=None, clock=time.monotonic, sleeper=time.sleep):
        self.cfg = {**DEFAULTS, **(cfg or {})}
        self.rng = rng or random.Random()
        self.clock = clock
        self.sleeper = sleeper
        self._session_end = None
        self._motionevent_ok = None

    @property
    def enabled(self):
        return self.cfg["enabled"]

    def _uniform(self, key):
        lo, hi = self.cfg[key]
        return self.rng.uniform(lo, hi)

    # Timing ---------------------------------------------------------------

    def delay(self, scale=1.0):
        """Seconds to wait before the next action."""
        if not self.enabled:
            return 0.4 * scale
        c = self.cfg
        mu = math.log(c["reaction_mean"] * scale)
        d = self.rng.lognormvariate(mu, c["reaction_sigma"])
        if self.rng.random() < c["hesitation_chance"]:
            d += self.rng.uniform(1, 4)
        return min(d, 15)

    def pause(self, scale=1.0):
        self.sleeper(self.delay(scale))

    # Movement -------------------------------------------------------------

    def point(self, x, y):
        if not self.enabled:
            return int(x), int(y)
        s = self.cfg["tap_spread"]
        dx = max(-2.5 * s, min(2.5 * s, self.rng.gauss(0, s)))
        dy = max(-2.5 * s, min(2.5 * s, self.rng.gauss(0, s)))
        return int(x + dx), int(y + dy)

    def drag_path(self, x1, y1, x2, y2):
        """Points along a slightly curved quadratic Bezier, eased in and out."""
        (x1, y1), (x2, y2) = self.point(x1, y1), self.point(x2, y2)
        dist = math.hypot(x2 - x1, y2 - y1) or 1
        # Control point pushed sideways from the midpoint.
        bend = self.rng.uniform(-0.25, 0.25) * dist
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        cx, cy = mx - (y2 - y1) / dist * bend, my + (x2 - x1) / dist * bend
        n = max(2, self.cfg["drag_steps"])
        pts = []
        for i in range(n + 1):
            t = i / n
            t = t * t * (3 - 2 * t)  # smoothstep easing
            px = (1 - t) ** 2 * x1 + 2 * (1 - t) * t * cx + t ** 2 * x2
            py = (1 - t) ** 2 * y1 + 2 * (1 - t) * t * cy + t ** 2 * y2
            pts.append((int(px), int(py)))
        pts[-1] = (x2, y2)
        return pts

    def tap(self, device, x, y):
        x, y = self.point(x, y)
        if self.enabled:
            device.press(x, y, int(self._uniform("press_ms")))
        else:
            device.tap(x, y)

    def drag(self, device, x1, y1, x2, y2):
        if not self.enabled:
            device.drag(x1, y1, x2, y2)
            return
        duration = int(self._uniform("drag_ms"))
        if self.cfg["curved_drags"] and self._motionevent_ok is not False:
            pts = self.drag_path(x1, y1, x2, y2)
            try:
                device.drag_path(pts, duration)
                self._motionevent_ok = True
                return
            except Exception:
                if self._motionevent_ok is None:
                    log.info("Curved drags unsupported on this device; using straight swipes")
                self._motionevent_ok = False
        (x1, y1), (x2, y2) = self.point(x1, y1), self.point(x2, y2)
        device.drag(x1, y1, x2, y2, duration)

    # Decisions ------------------------------------------------------------

    def notices(self):
        """False occasionally, so a target is left for a later cycle."""
        return not self.enabled or self.rng.random() >= self.cfg["miss_chance"]

    def order(self, items):
        """Mostly keep the planned order, sometimes loosen it like a person would."""
        items = list(items)
        if self.enabled and self.rng.random() < self.cfg["shuffle_chance"]:
            for i in range(len(items) - 1):
                if self.rng.random() < 0.5:
                    items[i], items[i + 1] = items[i + 1], items[i]
        return items

    # Sessions -------------------------------------------------------------

    def _in_active_hours(self, now=None):
        hours = self.cfg["active_hours"]
        if not hours:
            return True
        h = (now or dt.datetime.now()).hour
        start, end = hours
        return start <= h < end if start <= end else (h >= start or h < end)

    def rest_if_needed(self):
        """Block for a break when the session is over or outside active hours. Returns True if it rested."""
        if not self.enabled:
            return False
        if not self._in_active_hours():
            log.info("Outside active hours; resting 15 min")
            self.sleeper(15 * 60)
            self._session_end = None
            return True
        now = self.clock()
        if self._session_end is None:
            self._session_end = now + self._uniform("session_minutes") * 60
            return False
        if now >= self._session_end:
            minutes = self._uniform("break_minutes")
            log.info("Taking a %.0f min break", minutes)
            self.sleeper(minutes * 60)
            self._session_end = None
            return True
        if self.rng.random() < self.cfg["idle_chance"]:
            self.sleeper(self._uniform("idle_seconds"))
        return False
