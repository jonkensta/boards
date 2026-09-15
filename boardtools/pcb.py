"""Read-only facts about a .kicad_pcb file."""

from __future__ import annotations

import re

from . import sexpr

COPPER = re.compile(r"^(?:F|B|In\d+)\.Cu$")


def load(path: str) -> sexpr.Node:
    with open(path, encoding="utf-8") as f:
        root = sexpr.parse(f.read())
    if root[:1] != ["kicad_pcb"]:
        raise ValueError(f"{path}: not a kicad_pcb file")
    return root


def copper_layers(root: sexpr.Node) -> list[str]:
    """Copper layer names from the layer table, in stackup order (F.Cu first)."""
    table = sexpr.child(root, "layers")
    if table is None:
        return []
    names = [e[1] for e in table[1:] if isinstance(e, list) and len(e) >= 2]
    return list(dict.fromkeys(n for n in names if COPPER.match(n)))


def title_block(root: sexpr.Node) -> dict[str, str]:
    """title/date/rev/company from the board's title block (missing keys omitted)."""
    tb = sexpr.child(root, "title_block")
    out: dict[str, str] = {}
    if tb is None:
        return out
    for key in ("title", "date", "rev", "company"):
        el = sexpr.child(tb, key)
        if el is not None and len(el) > 1:
            out[key] = el[1]
    return out
