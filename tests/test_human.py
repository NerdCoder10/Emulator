import math
import random

from topwar_bot.human import Human


def make(**cfg):
    slept = []
    h = Human(cfg, rng=random.Random(1), sleeper=slept.append)
    return h, slept


def test_delays_vary_and_stay_bounded():
    h, _ = make(hesitation_chance=0)
    ds = [h.delay() for _ in range(500)]
    assert all(0 < d <= 15 for d in ds)
    assert max(ds) > 2 * min(ds)  # not a fixed rhythm
    assert 0.4 < sum(ds) / len(ds) < 0.9


def test_taps_scatter_around_target():
    h, _ = make(tap_spread=6)
    pts = {h.point(500, 300) for _ in range(200)}
    assert len(pts) > 50
    assert all(abs(x - 500) <= 15 and abs(y - 300) <= 15 for x, y in pts)


def test_drag_path_is_curved_and_reaches_target():
    h, _ = make(tap_spread=0)
    pts = h.drag_path(100, 100, 600, 100)
    assert pts[0] == (100, 100) and pts[-1] == (600, 100)
    assert len(pts) == 8
    # Path stays near the straight line.
    assert all(abs(y - 100) < 0.2 * 500 for _, y in pts)
    assert math.isclose(sum(1 for i in range(len(pts) - 1) if pts[i + 1][0] >= pts[i][0]), 7)


def test_session_break_after_session_length():
    now = [0.0]
    slept = []
    h = Human({"session_minutes": [30, 30], "break_minutes": [10, 10], "idle_chance": 0, "active_hours": None},
              rng=random.Random(0), clock=lambda: now[0], sleeper=slept.append)
    assert h.rest_if_needed() is False  # starts a session
    now[0] = 29 * 60
    assert h.rest_if_needed() is False
    now[0] = 31 * 60
    assert h.rest_if_needed() is True
    assert slept == [600]


def test_active_hours_wraps_midnight():
    import datetime as dt
    h, _ = make(active_hours=[22, 6])
    assert h._in_active_hours(dt.datetime(2026, 1, 1, 23))
    assert h._in_active_hours(dt.datetime(2026, 1, 1, 3))
    assert not h._in_active_hours(dt.datetime(2026, 1, 1, 12))


def test_drag_falls_back_when_motionevent_unsupported():
    calls = []

    class Dev:
        def drag_path(self, pts, ms):
            raise RuntimeError("Unknown command")

        def drag(self, *a):
            calls.append(a)

    h, _ = make()
    h.drag(Dev(), 0, 0, 100, 100)
    h.drag(Dev(), 0, 0, 100, 100)
    assert len(calls) == 2 and h._motionevent_ok is False


def test_disabled_is_deterministic():
    h, _ = make(enabled=False)
    assert h.point(10, 20) == (10, 20)
    assert all(h.notices() for _ in range(100))
    assert h.order([1, 2, 3]) == [1, 2, 3]
