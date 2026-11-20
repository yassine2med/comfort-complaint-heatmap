"""Load comfort complaints and summarise them by zone and by time."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from html import escape

KINDS = ("Too Hot", "Too Cold", "Stuffy", "Drafty")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
SHADES = " .:*#"


@dataclass(frozen=True)
class Complaint:
    when: datetime
    zone: str
    kind: str


def load(path: str) -> tuple[list[Complaint], list[str]]:
    """Read a CSV with columns timestamp, zone, kind. Bad rows are skipped and reported."""
    items, problems = [], []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = {"timestamp", "zone", "kind"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError("missing column(s): " + ", ".join(sorted(missing)))
        for n, row in enumerate(reader, start=2):
            zone = (row["zone"] or "").strip()
            kind = (row["kind"] or "").strip()
            try:
                when = datetime.strptime((row["timestamp"] or "").strip(), "%Y-%m-%d %H:%M")
            except ValueError:
                problems.append(f"row {n}: bad timestamp '{row['timestamp']}'")
                continue
            if not zone:
                problems.append(f"row {n}: zone is empty")
            elif kind not in KINDS:
                problems.append(f"row {n}: kind '{kind}' is not one of {list(KINDS)}")
            else:
                items.append(Complaint(when, zone, kind))
    return items, problems


def select(items: list[Complaint], kind: str = "all") -> list[Complaint]:
    """Filter by 'hot', 'cold' or 'all'."""
    wanted = {"hot": ("Too Hot",), "cold": ("Too Cold",), "all": KINDS}[kind]
    return [c for c in items if c.kind in wanted]


def matrix(items: list[Complaint], by: str = "weekday"):
    """Return (zones, column labels, {zone: [count per column]}). Columns: Mon-Fri or hours that occur."""
    zones = sorted({c.zone for c in items})
    if by == "weekday":
        cols = list(WEEKDAYS[:5])
        index = lambda c: c.when.weekday() if c.when.weekday() < 5 else None
    else:
        hours = sorted({c.when.hour for c in items})
        cols = [f"{h:02d}h" for h in range(hours[0], hours[-1] + 1)] if hours else []
        index = lambda c: c.when.hour - hours[0]
    grid = {z: [0] * len(cols) for z in zones}
    for c in items:
        i = index(c)
        if i is not None:
            grid[c.zone][i] += 1
    return zones, cols, grid


def balance(items: list[Complaint]) -> list[tuple[str, int, int, int]]:
    """Return (zone, hot, cold, net) sorted by the largest absolute net first. Net is hot minus cold."""
    out = {}
    for c in items:
        hot, cold = out.setdefault(c.zone, [0, 0])
        if c.kind == "Too Hot":
            out[c.zone][0] += 1
        elif c.kind == "Too Cold":
            out[c.zone][1] += 1
    rows = [(z, h, k, h - k) for z, (h, k) in out.items()]
    return sorted(rows, key=lambda r: (-abs(r[3]), r[0]))


def shade(count: int, peak: int) -> str:
    if count == 0 or peak == 0:
        return SHADES[0]
    return SHADES[max(1, min(len(SHADES) - 1, round(count / peak * (len(SHADES) - 1))))]


def text_table(items: list[Complaint], by: str = "weekday") -> str:
    zones, cols, grid = matrix(items, by)
    if not zones:
        return "no complaints"
    peak = max(max(v) for v in grid.values())
    width = max(len(z) for z in zones)
    lines = [" " * width + "  " + " ".join(f"{c:>4}" for c in cols) + "  total"]
    for z in zones:
        cells = " ".join(f"{v:>3}{shade(v, peak)}" for v in grid[z])
        lines.append(f"{z:<{width}}  {cells}  {sum(grid[z]):>5}")
    return "\n".join(lines)


def _colour(count: int, peak: int) -> str:
    t = 0 if peak == 0 else count / peak
    r, g, b = 255, round(245 - 170 * t), round(235 - 195 * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def svg_heatmap(items: list[Complaint], by: str = "weekday", title: str = "Comfort complaints") -> str:
    zones, cols, grid = matrix(items, by)
    peak = max((max(v) for v in grid.values()), default=0)
    cw, ch, left, top = 56, 34, 110, 64
    w, h = left + cw * len(cols) + 20, top + ch * len(zones) + 20
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="sans-serif" font-size="13">',
           f'<text x="10" y="24" font-size="16" font-weight="bold">{escape(title)}</text>']
    for i, c in enumerate(cols):
        out.append(f'<text x="{left + i * cw + cw / 2}" y="{top - 10}" text-anchor="middle">{escape(c)}</text>')
    for r, z in enumerate(zones):
        y = top + r * ch
        out.append(f'<text x="{left - 8}" y="{y + ch / 2 + 4}" text-anchor="end">{escape(z)}</text>')
        for i, v in enumerate(grid[z]):
            out.append(f'<rect x="{left + i * cw}" y="{y}" width="{cw - 2}" height="{ch - 2}" fill="{_colour(v, peak)}"/>')
            out.append(f'<text x="{left + i * cw + cw / 2 - 1}" y="{y + ch / 2 + 4}" text-anchor="middle">{v}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"
