"""Offline tests using synthetic screens and a fake device (no emulator needed)."""
import cv2
import numpy as np
import pytest

from topwar_bot.bot import TopWarBot
from topwar_bot.merge import detect_units, parse_unit, plan_merges
from topwar_bot.vision import Match, Templates, find_all

RNG = np.random.default_rng(0)


def make_template(size=40):
    return RNG.integers(0, 256, (size, size, 3), dtype=np.uint8)


def paste(screen, tmpl, cx, cy):
    h, w = tmpl.shape[:2]
    screen[cy - h // 2:cy - h // 2 + h, cx - w // 2:cx - w // 2 + w] = tmpl


def blank():
    return np.full((720, 1280, 3), 40, np.uint8)


def test_parse_unit():
    assert parse_unit("tank_03") == ("tank", 3)
    assert parse_unit("air_plane_12") == ("air_plane", 12)
    assert parse_unit("weird") == ("weird", 0)


def test_find_all_locates_each_copy():
    t = make_template()
    screen = blank()
    for x, y in [(100, 100), (400, 300), (900, 600)]:
        paste(screen, t, x, y)
    found = sorted((m.x, m.y) for m in find_all(screen, t, "t"))
    assert found == [(100, 100), (400, 300), (900, 600)]


def test_plan_merges_pairs_same_units_lowest_first():
    units = [Match("tank_02", 0, 0, 1), Match("tank_02", 10, 0, 1), Match("tank_02", 500, 0, 1),
             Match("tank_01", 0, 100, 1), Match("tank_01", 50, 100, 1), Match("plane_05", 0, 200, 1)]
    plan = plan_merges(units)
    assert [s.name for s, _ in plan] == ["tank_01", "tank_02"]
    used = [id(u) for pair in plan for u in pair]
    assert len(used) == len(set(used))


def test_plan_merges_respects_max_level():
    units = [Match("tank_09", 0, 0, 1), Match("tank_09", 10, 0, 1)]
    assert plan_merges(units, max_level=9) == []


def test_detect_units_ignores_overlapping_duplicates():
    a, b = make_template(), make_template()
    screen = blank()
    paste(screen, a, 200, 200)
    paste(screen, a, 600, 200)
    paste(screen, b, 400, 500)
    units = detect_units(screen, [("tank_01", a), ("tank_02", b)], 0.9)
    assert sorted(u.name for u in units) == ["tank_01", "tank_01", "tank_02"]


class FakeDevice:
    """Simulates a merge grid: dragging a unit onto an identical one levels it up."""

    def __init__(self, tmpls, units):
        self.tmpls = tmpls  # level -> template
        self.units = dict(units)  # (x, y) -> level
        self.drags = 0

    def screenshot(self):
        s = blank()
        for (x, y), lvl in self.units.items():
            paste(s, self.tmpls[lvl], x, y)
        return s

    def drag(self, x1, y1, x2, y2, duration_ms=0):
        self.drags += 1
        src = min(self.units, key=lambda p: (p[0] - x1) ** 2 + (p[1] - y1) ** 2)
        dst = min(self.units, key=lambda p: (p[0] - x2) ** 2 + (p[1] - y2) ** 2)
        if src != dst and self.units[src] == self.units[dst]:
            lvl = self.units.pop(src)
            self.units[dst] = lvl + 1

    def drag_path(self, points, duration_ms):
        (x1, y1), (x2, y2) = points[0], points[-1]
        self.drag(x1, y1, x2, y2)

    def tap(self, x, y): pass
    def press(self, x, y, ms): pass


@pytest.mark.parametrize("human", [{"enabled": False}, {"enabled": True, "miss_chance": 0}])
def test_merge_round_chains_to_highest_level(tmp_path, human):
    tmpls = {lvl: make_template() for lvl in range(1, 5)}
    (tmp_path / "units").mkdir()
    (tmp_path / "buttons").mkdir()
    for lvl, t in tmpls.items():
        cv2.imwrite(str(tmp_path / "units" / f"tank_{lvl:02d}.png"), t)

    # Four level-1 units should chain: 1+1, 1+1 -> 2+2 -> one level 3.
    dev = FakeDevice(tmpls, {(150, 150): 1, (350, 150): 1, (550, 150): 1, (750, 150): 1})
    cfg = {"templates_dir": str(tmp_path), "game": {"package": "x"}, "bot": {
        "unit_threshold": 0.9, "button_threshold": 0.85, "max_merge_passes": 10,
        "merge_lowest_first": True}, "human": human}
    bot = TopWarBot(cfg, dev)
    bot.human.sleeper = lambda s: None
    assert bot.merge_round() == 3
    assert list(dev.units.values()) == [3]
    assert Templates(tmp_path / "units")
