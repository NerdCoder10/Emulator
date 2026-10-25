"""Capture templates from the live emulator screen.

  python -m topwar_bot.capture screenshot           # save full screen to screen.png
  python -m topwar_bot.capture crop units/tank_01   # drag a box around the item, press Enter
  python -m topwar_bot.capture test units/tank_01   # show where a template matches now
"""
import argparse
from pathlib import Path

import cv2

from .bot import ROOT, load_config
from .device import Device
from .vision import find_all


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["screenshot", "crop", "test"])
    p.add_argument("name", nargs="?", help="template path under templates/, e.g. buttons/close_x")
    p.add_argument("-c", "--config", default=str(ROOT / "config.yaml"))
    p.add_argument("-s", "--serial")
    args = p.parse_args(argv)

    cfg = load_config(args.config)
    device = Device(serial=args.serial or cfg["emulator"].get("serial") or cfg["emulator"].get("address"),
                    adb=cfg["emulator"].get("adb", "adb"))
    screen = device.screenshot()

    if args.action == "screenshot":
        cv2.imwrite("screen.png", screen)
        print("Saved screen.png", screen.shape[1], "x", screen.shape[0])
        return

    if not args.name:
        p.error("name is required for crop/test")
    path = ROOT / cfg["templates_dir"] / f"{args.name}.png"

    if args.action == "crop":
        x, y, w, h = cv2.selectROI("Select template, then press Enter", screen, showCrosshair=False)
        cv2.destroyAllWindows()
        if w and h:
            path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(path), screen[y:y + h, x:x + w])
            print("Saved", path)
        return

    tmpl = cv2.imread(str(path))
    if tmpl is None:
        raise SystemExit(f"Template not found: {path}")
    matches = find_all(screen, tmpl, args.name, cfg["bot"]["unit_threshold"])
    for m in matches:
        cv2.circle(screen, (m.x, m.y), 20, (0, 0, 255), 3)
        print(f"match at ({m.x}, {m.y}) score={m.score:.3f}")
    print(f"{len(matches)} matches")
    cv2.imshow("matches", screen)
    cv2.waitKey(0)


if __name__ == "__main__":
    main()
