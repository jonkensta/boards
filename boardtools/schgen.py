"""Generate KiCad schematics (.kicad_sch) from Python using the stock symbol libraries.

Coordinates are in millimetres, y down. Every connection point must sit on
KiCad's 1.27 mm grid or ERC reports it; use `g(k)` to convert grid units.
Pin positions returned by `Schematic.place` are already in sheet coordinates,
so wires can be drawn from symbol to symbol without hand-computing offsets.

Only what the boards in this repo have needed is implemented: single-unit
symbols (with `extends` flattened), wires, junctions, power symbols, PWR_FLAG,
local net labels, no-connect flags, text, dashed boxes, DNP and KiCad 10 design
variants. No hierarchical sheets or buses yet.
"""

from __future__ import annotations

import os
import uuid

from . import sexpr

Q = sexpr.Quoted
G = 1.27
SYMBOL_DIR = os.environ.get("KICAD_SYMBOL_DIR", "/usr/share/kicad/symbols")


def g(k: float) -> float:
    """Grid units (1.27 mm) to millimetres."""
    return round(k * G, 2)


def _u() -> Q:
    return Q(str(uuid.uuid4()))


def _n(x) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


_libcache: dict[str, sexpr.Node] = {}


def _lib(lib: str) -> sexpr.Node:
    if lib not in _libcache:
        with open(os.path.join(SYMBOL_DIR, f"{lib}.kicad_sym"), encoding="utf-8") as f:
            _libcache[lib] = sexpr.parse(f.read())
    return _libcache[lib]


def _raw_symbol(lib: str, name: str) -> sexpr.Node:
    for s in sexpr.children(_lib(lib), "symbol"):
        if s[1] == name:
            return s
    raise KeyError(f"{lib}:{name}")


def lib_symbol(lib: str, name: str) -> sexpr.Node:
    """The library symbol renamed `lib:name`, with any `extends` chain flattened.

    A derived symbol keeps its own properties and takes the parent's units,
    pin settings and everything else it does not override.
    """
    sym = _raw_symbol(lib, name)
    ext = sexpr.child(sym, "extends")
    if ext is None:
        out = list(sym)
    else:
        parent = lib_symbol(lib, ext[1])
        own_props = {p[1]: p for p in sexpr.children(sym, "property")}
        out = ["symbol", None]
        for el in parent[2:]:
            if isinstance(el, list) and el[0] == "property" and el[1] in own_props:
                out.append(own_props.pop(el[1]))
            elif isinstance(el, list) and el[0] == "symbol":
                unit = list(el)
                unit[1] = Q(unit[1].replace(ext[1], name, 1))
                out.append(unit)
            else:
                out.append(el)
        for el in sym[2:]:
            if isinstance(el, list) and el[0] == "property" and el[1] in own_props:
                out.append(el)
    out[1] = Q(f"{lib}:{name}")
    return out


def pin_offsets(sym: sexpr.Node) -> dict[str, tuple[float, float]]:
    """{pin number: (dx, dy)} sheet offsets for rotation 0 (library y is flipped)."""
    out = {}
    for unit in sexpr.children(sym, "symbol"):
        for pin in sexpr.children(unit, "pin"):
            at = sexpr.child(pin, "at")
            out[sexpr.child(pin, "number")[1]] = (float(at[1]), -float(at[2]))
    return out


def xform(dx: float, dy: float, rot: int, mirror: str | None = None) -> tuple[float, float]:
    """Apply a symbol's (mirror, rot) to a sheet-space offset."""
    if mirror == "y":
        dx = -dx
    if mirror == "x":
        dy = -dy
    for _ in range(int(rot) // 90):
        dx, dy = dy, -dx
    return dx, dy


class Schematic:
    def __init__(self, project: str, root_uuid: str, title: str, rev: str = "A", date: str = "",
                 comment: str = "", paper: str = "A4"):
        self.project, self.root_uuid = project, root_uuid
        self.title, self.rev, self.date, self.comment, self.paper = title, rev, date, comment, paper
        self.lib_symbols: dict[str, sexpr.Node] = {}
        self.items: list[sexpr.Node] = []
        self._pwr = 0
        self._flg = 0

    # ---- symbols ---------------------------------------------------------
    def place(self, lib: str, name: str, ref: str, x: float, y: float, rot: int = 0, *, value: str | None = None,
              footprint: str = "", fields: dict | None = None, mirror: str | None = None, in_bom: bool = True,
              on_board: bool = True, prop_pos: dict | None = None, hide_value: bool = False,
              description: str | None = None, dnp: bool = False, in_pos_files: bool | None = None,
              variants: dict[str, dict] | None = None, prop_rot: int | None = None) -> dict[str, tuple[float, float]]:
        """Place one symbol; returns {pin number: (x, y)} in sheet coordinates.

        `variants` = {variant name: {"dnp": bool, ...}} records per-variant overrides
        (KiCad 10 design variants); only attributes that differ from the base symbol
        are meaningful. `in_pos_files=False` keeps pad-only parts out of position files.
        `prop_rot` forces the Reference/Value text angle (default: rot % 180).
        """
        key = f"{lib}:{name}"
        sym = self.lib_symbols.setdefault(key, lib_symbol(lib, name))
        libprops = {p[1]: (p[2] if len(p) > 2 else "") for p in sexpr.children(sym, "property")}
        fp = footprint or libprops.get("Footprint", "")
        val = value if value is not None else name
        pp = prop_pos or {}

        def prop(k, v, hide=False, dx=2.54, dy=0.0, rotp=None):
            px, py = pp.get(k, (dx, dy))
            if rotp is None:
                rotp = rot % 180 if prop_rot is None else prop_rot
            e = ["effects", ["font", ["size", "1.27", "1.27"]]]
            if hide:
                e.append(["hide", "yes"])
            return ["property", Q(k), Q(v), ["at", _n(x + px), _n(y + py), _n(rotp)], e]

        node = ["symbol", ["lib_id", Q(key)], ["at", _n(x), _n(y), _n(rot)]]
        if mirror:
            node.append(["mirror", mirror])
        yn = lambda b: "yes" if b else "no"
        node += [["unit", "1"], ["exclude_from_sim", "no"], ["in_bom", yn(in_bom)], ["on_board", yn(on_board)]]
        if in_pos_files is not None:
            node.append(["in_pos_files", yn(in_pos_files)])
        node += [["dnp", yn(dnp)], ["uuid", _u()],
                 prop("Reference", ref, hide=key.startswith("power:"), dx=2.54, dy=-1.27),
                 prop("Value", val, hide=hide_value, dx=2.54, dy=1.27),
                 prop("Footprint", fp, hide=True), prop("Datasheet", libprops.get("Datasheet", ""), hide=True),
                 prop("Description", description if description is not None else libprops.get("Description", ""), hide=True)]
        for k, v in (fields or {}).items():
            node.append(prop(k, v, hide=True))
        pins = {}
        for num, (dx, dy) in pin_offsets(sym).items():
            node.append(["pin", Q(num), ["uuid", _u()]])
            ex, ey = xform(dx, dy, rot, mirror)
            pins[num] = (round(x + ex, 2), round(y + ey, 2))
        path = ["path", Q("/" + self.root_uuid), ["reference", Q(ref)], ["unit", "1"]]
        for vname, ov in (variants or {}).items():
            v = ["variant", ["name", Q(vname)]]
            for k in ("dnp", "in_bom", "on_board", "in_pos_files", "exclude_from_sim"):
                if k in ov:
                    v.append([k, yn(ov[k])])
            path.append(v)
        node.append(["instances", ["project", Q(self.project), path]])
        self.items.append(node)
        return pins

    def power(self, name: str, x: float, y: float, value: str | None = None, rot: int = 0):
        """A power symbol (auto #PWRnn); `value` renames the net (e.g. +5V -> +5V_LED)."""
        self._pwr += 1
        return self.place("power", name, f"#PWR{self._pwr:02d}", x, y, rot, value=value, in_bom=False, on_board=False)

    def flag(self, x: float, y: float, rot: int = 0):
        self._flg += 1
        return self.place("power", "PWR_FLAG", f"#FLG{self._flg:02d}", x, y, rot, in_bom=False, on_board=False,
                          hide_value=True)

    # ---- wiring / graphics -------------------------------------------------
    def wire(self, *pts):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            self.items.append(["wire", ["pts", ["xy", _n(x1), _n(y1)], ["xy", _n(x2), _n(y2)]],
                               ["stroke", ["width", "0"], ["type", "default"]], ["uuid", _u()]])

    def junction(self, x: float, y: float):
        self.items.append(["junction", ["at", _n(x), _n(y)], ["diameter", "0"], ["color", "0", "0", "0", "0"], ["uuid", _u()]])

    def label(self, name: str, x: float, y: float, rot: int = 0):
        """Local net label anchored at (x, y); rot 0 reads right, 180 left, 90 up, 270 down."""
        just = ["left", "bottom"] if rot in (0, 90) else ["right", "bottom"]
        self.items.append(["label", Q(name), ["at", _n(x), _n(y), _n(rot)],
                           ["effects", ["font", ["size", "1.27", "1.27"]], ["justify"] + just], ["uuid", _u()]])

    def no_connect(self, x: float, y: float):
        self.items.append(["no_connect", ["at", _n(x), _n(y)], ["uuid", _u()]])

    def text(self, s: str, x: float, y: float, size: float = 1.27, bold: bool = False):
        f = ["font", ["size", _n(size), _n(size)]]
        if bold:
            f.append(["bold", "yes"])
        self.items.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", _n(x), _n(y), "0"],
                           ["effects", f, ["justify", "left", "bottom"]], ["uuid", _u()]])

    def box(self, x1, y1, x2, y2):
        self.items.append(["rectangle", ["start", _n(x1), _n(y1)], ["end", _n(x2), _n(y2)],
                           ["stroke", ["width", "0.3"], ["type", "dash"]], ["fill", ["type", "none"]], ["uuid", _u()]])

    # ---- output -------------------------------------------------------------
    def node(self) -> sexpr.Node:
        tb = ["title_block", ["title", Q(self.title)], ["date", Q(self.date)], ["rev", Q(self.rev)]]
        if self.comment:
            tb.append(["comment", "1", Q(self.comment)])
        sch = ["kicad_sch", ["version", "20250114"], ["generator", Q("eeschema")], ["generator_version", Q("9.0")],
               ["uuid", Q(self.root_uuid)], ["paper", Q(self.paper)], tb,
               ["lib_symbols"] + [self.lib_symbols[k] for k in sorted(self.lib_symbols)]]
        sch += self.items
        sch.append(["sheet_instances", ["path", Q("/"), ["page", Q("1")]]])
        return sch

    def write(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(sexpr.dumps(self.node()) + "\n")


def root_uuid_of(path: str) -> str:
    """The sheet UUID of an existing schematic (keeps the .kicad_pro `sheets` entry valid)."""
    with open(path, encoding="utf-8") as f:
        return sexpr.child(sexpr.parse(f.read()), "uuid")[1]
