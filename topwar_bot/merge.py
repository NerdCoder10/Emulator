"""Merge planning: find pairs of identical units on the base and drag them together.

Unit templates are named "<type>_<level>", e.g. "tank_03.png", "plane_12.png".
"""
import re
from collections import defaultdict

from .vision import Match, find_all

_LEVEL_RE = re.compile(r"^(?P<type>.+?)_(?P<level>\d+)$")


def parse_unit(name):
    m = _LEVEL_RE.match(name)
    if not m:
        return name, 0
    return m.group("type"), int(m.group("level"))


def detect_units(screen, unit_templates, threshold, region=None):
    """Detect units, keeping only the best template per location so one unit isn't counted twice."""
    found = []
    for name, tmpl in unit_templates:
        found += find_all(screen, tmpl, name, threshold, region)
    found.sort(key=lambda m: -m.score)
    kept = []
    for m in found:
        if all((m.x - k.x) ** 2 + (m.y - k.y) ** 2 >= 30 ** 2 for k in kept):
            kept.append(m)
    return kept


def plan_merges(units, max_level=None, lowest_first=True):
    """Return (source, target) pairs to drag, each unit used at most once.

    Merging lowest levels first frees grid slots fastest and lets new units
    chain into higher merges on the next scan.
    """
    groups = defaultdict(list)
    for u in units:
        groups[u.name].append(u)

    def level(name):
        return parse_unit(name)[1]

    plan = []
    for name in sorted(groups, key=level, reverse=not lowest_first):
        if max_level is not None and level(name) >= max_level:
            continue
        members = groups[name]
        # Pair nearest neighbours to keep drags short.
        while len(members) >= 2:
            src = members.pop()
            dst = min(members, key=lambda m: (m.x - src.x) ** 2 + (m.y - src.y) ** 2)
            members.remove(dst)
            plan.append((src, dst))
    return plan


def summarize(units):
    counts = defaultdict(int)
    for u in units:
        counts[u.name] += 1
    return dict(sorted(counts.items()))


__all__ = ["Match", "detect_units", "plan_merges", "parse_unit", "summarize"]
