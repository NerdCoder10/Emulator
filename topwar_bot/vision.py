"""Template matching helpers built on OpenCV."""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class Match:
    name: str
    x: int  # centre x
    y: int  # centre y
    score: float


class Templates:
    """Loads every PNG in a folder, keyed by file stem (e.g. units/plane_05.png -> 'plane_05')."""

    def __init__(self, folder):
        self.images = {}
        folder = Path(folder)
        if folder.is_dir():
            for path in sorted(folder.glob("*.png")):
                img = cv2.imread(str(path), cv2.IMREAD_COLOR)
                if img is not None:
                    self.images[path.stem] = img

    def __bool__(self):
        return bool(self.images)

    def __iter__(self):
        return iter(self.images.items())

    def get(self, name):
        return self.images.get(name)


def _nms(points, min_dist):
    """Keep the highest-scoring point within each min_dist neighbourhood."""
    kept = []
    for x, y, s in sorted(points, key=lambda p: -p[2]):
        if all((x - kx) ** 2 + (y - ky) ** 2 >= min_dist ** 2 for kx, ky, _ in kept):
            kept.append((x, y, s))
    return kept


def find_all(screen, template, name="", threshold=0.85, region=None):
    """Return every match of template in screen with score >= threshold."""
    ox, oy = 0, 0
    if region:
        x1, y1, x2, y2 = region
        screen = screen[y1:y2, x1:x2]
        ox, oy = x1, y1
    th, tw = template.shape[:2]
    if screen.shape[0] < th or screen.shape[1] < tw:
        return []
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(result >= threshold)
    points = [(int(x) + tw // 2 + ox, int(y) + th // 2 + oy, float(result[y, x])) for y, x in zip(ys, xs)]
    return [Match(name, x, y, s) for x, y, s in _nms(points, min(tw, th) * 0.6)]


def find_best(screen, template, name="", threshold=0.85, region=None):
    matches = find_all(screen, template, name, threshold, region)
    return max(matches, key=lambda m: m.score) if matches else None
