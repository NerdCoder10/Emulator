"""Main bot loop.

Button templates in templates/buttons/ are grouped by filename prefix:
  close_*    popups / ads to dismiss (tapped first)
  collect_*  resource bubbles on buildings (gold, oil, etc.)
  claim_*    free chests, daily rewards, mail, VIP rewards
  help_*     alliance help button
  buy_*      the "buy unit" button on the base (used to fill empty slots)
Unit templates live in templates/units/ named "<type>_<level>.png".
"""
import argparse
import logging
import time
from collections import Counter
from pathlib import Path

import yaml

from . import emulator
from .merge import detect_units, plan_merges, summarize
from .vision import Templates, find_all, find_best

log = logging.getLogger("topwar")
ROOT = Path(__file__).resolve().parent.parent


class TopWarBot:
    def __init__(self, cfg, device):
        self.cfg = cfg
        self.bot_cfg = cfg["bot"]
        self.device = device
        tdir = ROOT / cfg["templates_dir"]
        self.units = Templates(tdir / "units")
        self.buttons = Templates(tdir / "buttons")
        self.stats = Counter()
        if not self.units:
            log.warning("No unit templates found in %s/units - merging disabled", tdir)

    def _buttons(self, prefix):
        return [(n, t) for n, t in self.buttons if n.startswith(prefix)]

    def _tap_all(self, prefix, screen, max_taps=10):
        """Tap every visible button with the given prefix. Returns number of taps."""
        taps = 0
        thr = self.bot_cfg["button_threshold"]
        for name, tmpl in self._buttons(prefix):
            for m in find_all(screen, tmpl, name, thr):
                if taps >= max_taps:
                    return taps
                self.device.tap(m.x, m.y)
                self.stats[name] += 1
                taps += 1
                self.device.sleep(self.bot_cfg["tap_delay"])
        return taps

    def ensure_game(self):
        package = self.cfg["game"]["package"]
        if not self.device.is_app_foreground(package):
            log.info("Launching %s", package)
            self.device.start_app(package)
            self.device.sleep(self.cfg["game"]["startup_wait"])

    def dismiss_popups(self):
        for _ in range(5):
            if not self._tap_all("close_", self.device.screenshot(), max_taps=3):
                return

    def collect(self):
        screen = self.device.screenshot()
        n = self._tap_all("collect_", screen) + self._tap_all("claim_", screen) + self._tap_all("help_", screen)
        if n:
            log.info("Collected/claimed %d items", n)
            self.dismiss_popups()

    def merge_round(self):
        """Run merge scans until no more pairs are found. Returns merges done."""
        if not self.units:
            return 0
        region = self.bot_cfg.get("battlefield_region")
        thr = self.bot_cfg["unit_threshold"]
        max_level = self.bot_cfg.get("max_merge_level")
        total = 0
        for _ in range(self.bot_cfg["max_merge_passes"]):
            units = detect_units(self.device.screenshot(), self.units, thr, region)
            plan = plan_merges(units, max_level, self.bot_cfg["merge_lowest_first"])
            log.debug("Units: %s", summarize(units))
            if not plan:
                if not self.fill_slots(len(units)):
                    break
                continue
            for src, dst in plan:
                self.device.drag(src.x, src.y, dst.x, dst.y, self.bot_cfg["drag_ms"])
                self.stats[f"merge:{src.name}"] += 1
                total += 1
                self.device.sleep(self.bot_cfg["merge_delay"])
        if total:
            log.info("Merged %d pairs", total)
        return total

    def fill_slots(self, unit_count):
        """Buy units with the buy button while the base has free slots. Returns units bought."""
        slots = self.bot_cfg.get("base_slots")
        if not slots or unit_count >= slots:
            return 0
        thr = self.bot_cfg["button_threshold"]
        for name, tmpl in self._buttons("buy_"):
            btn = find_best(self.device.screenshot(), tmpl, name, thr)
            if btn:
                for _ in range(slots - unit_count):
                    self.device.tap(btn.x, btn.y)
                    self.stats[name] += 1
                    self.device.sleep(self.bot_cfg["tap_delay"])
                return slots - unit_count
        return 0

    def run(self, cycles=None):
        cycle = 0
        while cycles is None or cycle < cycles:
            cycle += 1
            try:
                self.ensure_game()
                self.dismiss_popups()
                self.collect()
                self.merge_round()
            except Exception:
                log.exception("Cycle %d failed; recovering", cycle)
                self.device.back()
            if cycle % 10 == 0:
                log.info("Stats after %d cycles: %s", cycle, dict(self.stats))
            self.device.sleep(self.bot_cfg["cycle_delay"])


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def main(argv=None):
    p = argparse.ArgumentParser(description="Top War emulator bot")
    p.add_argument("-c", "--config", default=str(ROOT / "config.yaml"))
    p.add_argument("--cycles", type=int, help="stop after N cycles (default: run forever)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config(args.config)
    device = emulator.ensure_running(cfg)
    log.info("Device ready: %s (%dx%d)", device.serial, *device.screen_size())
    bot = TopWarBot(cfg, device)
    try:
        bot.run(args.cycles)
    except KeyboardInterrupt:
        pass
    log.info("Final stats: %s", dict(bot.stats))


if __name__ == "__main__":
    main()
