"""Off-grid lint for .kicad_sch files: every electrical connection point on the grid.

KiCad's ERC reports off-grid connections as `endpoint_off_grid` but needs
kicad-cli and does not always say which pin caused it. This computes each
connection point from the file alone and names it:

- symbol pins: the pin's `(at ...)` in the embedded `lib_symbols` entry (the
  connection end; the pin line runs `length` from there toward the body),
  for the placed unit and body style plus the common unit 0 / style 0 pins,
  transformed by the instance's `(mirror ...)` and `(at x y rot)`;
- wire and bus endpoints, bus entries (both ends), junctions, no-connects;
- local, global and hierarchical labels, and sheet pins;
- recursively, every child sheet file (`sheets()`; each file once).

Text, graphics and field positions are not connection points and are ignored.
"""

from __future__ import annotations

import os
import sys
from typing import NamedTuple

from . import sexpr

GRID = 1.27
TOL = 1e-4  # mm


class Point(NamedTuple):
    kind: str   # pin, wire, bus, bus_entry, junction, no_connect, label, global_label, ...
    name: str   # reference / label text / "" for anonymous items
    pin: str    # pin number (pins), sheet pin name, else ""
    x: float
    y: float


def load(path: str) -> sexpr.Node:
    with open(path, encoding="utf-8") as f:
        root = sexpr.parse(f.read())
    if root[:1] != ["kicad_sch"]:
        raise ValueError(f"{path}: not a kicad_sch file")
    return root


def _xy(node: sexpr.Node) -> tuple[float, float]:
    return float(node[1]), float(node[2])


def _int(node: sexpr.Node | None, default: int) -> int:
    return int(node[1]) if node is not None and len(node) > 1 else default


def _unit_style(name: str) -> tuple[int, int]:
    """`Name_U_S` sub-symbol name -> (unit, body style); names may contain '_'."""
    parts = name.rsplit("_", 2)
    try:
        return int(parts[1]), int(parts[2])
    except (IndexError, ValueError):
        return 0, 0


def lib_pins(lib: dict[str, sexpr.Node], lib_id: str, unit: int, style: int) -> list[tuple[str, float, float]]:
    """(number, x, y) library-space (y-up) pin positions of one unit / body style.

    Follows `extends` to the parent symbol in the same `lib_symbols` block
    (KiCad normally stores flattened symbols, so this is only a fallback).
    """
    sym = lib.get(lib_id)
    if sym is None:
        raise ValueError(f"symbol {lib_id} missing from lib_symbols")
    ext = sexpr.child(sym, "extends")
    if ext is not None:
        prefix = lib_id.rpartition(":")[0]
        return lib_pins(lib, f"{prefix}:{ext[1]}" if prefix else ext[1], unit, style)
    out = []
    for sub in sexpr.children(sym, "symbol"):
        u, s = _unit_style(sub[1])
        if u not in (0, unit) or s not in (0, style):
            continue
        for pin in sexpr.children(sub, "pin"):
            num = sexpr.child(pin, "number")
            out.append((num[1] if num is not None else "?", *_xy(sexpr.child(pin, "at"))))
    return out


def transform(px: float, py: float, x: float, y: float, rot: int, mirror: str | None) -> tuple[float, float]:
    """Library pin (y-up) -> sheet (y-down) for a symbol at (x, y, rot) with `mirror`.

    KiCad rotates first (counter-clockwise on screen), then mirrors about the
    symbol origin: `mirror x` flips vertically, `mirror y` horizontally. Order
    matters only for 90/270; verified against ERC for all 12 combinations.
    """
    dx, dy = px, -py
    for _ in range((int(rot) // 90) % 4):
        dx, dy = dy, -dx
    if mirror == "y":
        dx = -dx
    elif mirror == "x":
        dy = -dy
    return x + dx, y + dy


def points(root: sexpr.Node) -> list[Point]:
    """Every electrical connection point in the sheet."""
    ls = sexpr.child(root, "lib_symbols")
    lib = {s[1]: s for s in sexpr.children(ls, "symbol")} if ls is not None else {}
    out: list[Point] = []
    for el in root[1:]:
        if not isinstance(el, list) or not el:
            continue
        head = el[0]
        if head == "symbol":
            # `lib_name` names the cached symbol when it differs from the library's copy
            lib_id = (sexpr.child(el, "lib_name") or sexpr.child(el, "lib_id"))[1]
            at = sexpr.child(el, "at")
            m = sexpr.child(el, "mirror")
            unit = _int(sexpr.child(el, "unit"), 1)
            style = _int(sexpr.child(el, "body_style") or sexpr.child(el, "convert"), 1)
            ref = next((p[2] for p in sexpr.children(el, "property") if p[1] == "Reference"), "?")
            x, y = _xy(at)
            rot = int(float(at[3])) if len(at) > 3 else 0
            for num, px, py in lib_pins(lib, lib_id, unit, style):
                out.append(Point("pin", ref, num, *transform(px, py, x, y, rot, m[1] if m else None)))
        elif head in ("wire", "bus"):
            for xy in sexpr.children(sexpr.child(el, "pts"), "xy"):
                out.append(Point(head, "", "", *_xy(xy)))
        elif head == "bus_entry":
            x, y = _xy(sexpr.child(el, "at"))
            w, h = _xy(sexpr.child(el, "size"))
            out += [Point(head, "", "", x, y), Point(head, "", "", x + w, y + h)]
        elif head in ("junction", "no_connect"):
            out.append(Point(head, "", "", *_xy(sexpr.child(el, "at"))))
        elif head in ("label", "global_label", "hierarchical_label"):
            out.append(Point(head, el[1], "", *_xy(sexpr.child(el, "at"))))
        elif head == "sheet":
            name = next((p[2] for p in sexpr.children(el, "property") if p[1] in ("Sheetname", "Sheet name")), "?")
            for pin in sexpr.children(el, "pin"):
                out.append(Point("sheet_pin", name, pin[1], *_xy(sexpr.child(pin, "at"))))
    return out


def snap(v: float, grid: float = GRID) -> float:
    return round(round(v / grid) * grid, 4)


def off_grid(pts: list[Point], grid: float = GRID, tol: float = TOL) -> list[Point]:
    return [p for p in pts if abs(p.x - snap(p.x, grid)) > tol or abs(p.y - snap(p.y, grid)) > tol]


def _n(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".")


def format_point(p: Point, grid: float = GRID) -> str:
    who = " ".join(s for s in (p.name, f"pin {p.pin}" if p.kind == "pin" else p.pin) if s)
    return (f"{p.kind:<18} {who:<20} at ({_n(p.x)}, {_n(p.y)})"
            f"  nearest ({_n(snap(p.x, grid))}, {_n(snap(p.y, grid))})")


def _prop(node: sexpr.Node, *names: str) -> str | None:
    return next((p[2] for p in sexpr.children(node, "property") if p[1] in names and len(p) > 2), None)


def sheets(path: str) -> list[tuple[str, sexpr.Node]]:
    """(path, root) for `path` and every sheet file below it, each file once.

    Child `Sheetfile`s resolve relative to the parent's directory, as KiCad does.
    A missing child or a sheet that (indirectly) contains itself is a ValueError.
    """
    out: list[tuple[str, sexpr.Node]] = []
    seen: set[str] = set()

    def walk(p: str, stack: tuple[str, ...]):
        key = os.path.realpath(p)
        if key in stack:
            raise ValueError(f"{p}: sheet recursion ({' -> '.join(os.path.basename(s) for s in stack + (key,))})")
        if key in seen:
            return
        seen.add(key)
        root = load(p)
        out.append((p, root))
        for sh in sexpr.children(root, "sheet"):
            f = _prop(sh, "Sheetfile", "Sheet file")
            if not f:
                raise ValueError(f"{p}: sheet {_prop(sh, 'Sheetname', 'Sheet name')!r} has no Sheetfile")
            child = os.path.join(os.path.dirname(p), f)
            if not os.path.isfile(child):
                raise ValueError(f"{p}: sheet {_prop(sh, 'Sheetname', 'Sheet name')!r} file not found: {child}")
            walk(child, stack + (key,))

    walk(path, ())
    return out


def main(argv: list[str]) -> int:
    """offgrid <file.kicad_sch> [--grid MM]; exit 1 if any connection point is off-grid.

    Hierarchical child sheets are followed and linted too (each file once).
    """
    args, grid = list(argv[1:]), GRID
    if "--grid" in args:
        i = args.index("--grid")
        try:
            grid = float(args[i + 1])
        except (IndexError, ValueError):
            grid = 0
        del args[i:i + 2]
    if len(args) != 1 or grid <= 0:
        print("usage: python3 -m boardtools offgrid <file.kicad_sch> [--grid 1.27]", file=sys.stderr)
        return 2
    path = args[0]
    files = sheets(path)
    total = nbad = 0
    for f, root in files:
        pts = points(root)
        bad = off_grid(pts, grid)
        total, nbad = total + len(pts), nbad + len(bad)
        for p in bad:
            print(f"{f}: {format_point(p, grid)}")
    where = f"{path}" + (f" (+{len(files) - 1} sub-sheet files)" if len(files) > 1 else "")
    if nbad:
        print(f"{where}: {nbad} of {total} connection points off the {_n(grid)} mm grid")
        return 1
    print(f"{where}: all {total} connection points on the {_n(grid)} mm grid")
    return 0
