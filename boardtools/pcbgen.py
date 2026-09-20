"""Generate KiCad boards (.kicad_pcb) from Python: placement, routing, pours, outline, silk.

Starts from the repo's template board (a KiCad-10-native file with setup and
layers), takes nets and component identities from a `kicad-cli sch export
netlist --format kicadsexpr` file, and embeds footprints from the stock
libraries. All coordinates passed in are board-local millimetres (origin at the
board's top-left corner, y down); `Board.footprint` returns pad centres in the
same frame so routes can be drawn pad to pad.

Only what the boards in this repo have needed: SMD/THT footprints with
rotation, straight segments, vias, rectangular pours, circular keepouts,
outline lines, graphic lines and text.
"""

from __future__ import annotations

import math
import os
import re
import uuid

from . import sexpr

Q = sexpr.Quoted
FOOTPRINT_DIR = os.environ.get("KICAD_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
REPO_FOOTPRINT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib", "footprints", "boards.pretty")
SIG, PWR = 0.25, 0.4


def _u() -> Q:
    return Q(str(uuid.uuid4()))


def _n(v) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)


def rot_pt(px: float, py: float, rot: float) -> tuple[float, float]:
    """Footprint-local offset rotated by the footprint angle (KiCad's y-down, CCW-positive)."""
    r = math.radians(rot)
    return (px * math.cos(r) + py * math.sin(r), -px * math.sin(r) + py * math.cos(r))


class Netlist:
    """Nets and components from a kicadsexpr netlist."""

    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            net = sexpr.parse(f.read())
        self.codes: dict[str, int] = {}
        self.node_net: dict[tuple[str, str], str] = {}
        for nn in sexpr.children(sexpr.child(net, "nets"), "net"):
            name = sexpr.child(nn, "name")[1]
            self.codes[name] = int(sexpr.child(nn, "code")[1])
            for x in sexpr.children(nn, "node"):
                self.node_net[(sexpr.child(x, "ref")[1], sexpr.child(x, "pin")[1])] = name
        self.comps: dict[str, dict] = {}
        for c in sexpr.children(sexpr.child(net, "components"), "comp"):
            ref = c[1][1]
            fields = {}
            flags = set()
            for pr in sexpr.children(c, "property"):          # top-level (property (name "dnp")) etc.
                if len(pr) > 1 and isinstance(pr[1], list) and pr[1][0] == "name" and pr[1][1] in ("dnp", "exclude_from_bom", "exclude_from_pos_files"):
                    flags.add(str(pr[1][1]))
            fl = sexpr.child(c, "fields")
            if fl:
                for f in sexpr.children(fl, "field"):
                    if len(f) > 2:
                        fields[f[1][1]] = f[2]

            def opt(k):
                el = sexpr.child(c, k)
                return el[1] if el is not None and len(el) > 1 else ""

            # (variants (variant (name "vib") (property (name "dnp") (value "1")) ...)): per-variant
            # overrides of dnp / exclude_from_bom / exclude_from_pos_files, only where they differ.
            variants: dict[str, dict[str, bool]] = {}
            vs = sexpr.child(c, "variants")
            for v in (sexpr.children(vs, "variant") if vs else []):
                ov = {}
                for pr in sexpr.children(v, "property"):
                    k, val = sexpr.child(pr, "name")[1], sexpr.child(pr, "value")[1]
                    if k in ("dnp", "exclude_from_bom", "exclude_from_pos_files"):
                        ov[str(k)] = val == "1"
                variants[str(sexpr.child(v, "name")[1])] = ov
            self.comps[ref] = dict(uuid=sexpr.child(c, "tstamps")[1], value=sexpr.child(c, "value")[1],
                                   footprint=sexpr.child(c, "footprint")[1], datasheet=opt("datasheet"),
                                   description=opt("description"), fields=fields, flags=flags, variants=variants)
        self.variants: list[str] = sorted({v for c in self.comps.values() for v in c["variants"]})


class Board:
    def __init__(self, template_pcb: str, netlist: Netlist, sheetfile: str, width: float, height: float,
                 origin: tuple[float, float] = (50.0, 50.0), copper_layers: int = 2):
        self.net = netlist
        self.sheetfile = sheetfile
        self.W, self.H = width, height
        self.OX, self.OY = origin
        with open(template_pcb, encoding="utf-8") as f:
            board = sexpr.parse(f.read())
        drop = ("gr_line", "gr_rect", "footprint", "segment", "via", "zone", "gr_text", "net")
        self.board = [x for x in board if not (isinstance(x, list) and x[0] in drop)]
        # Inner copper layers, KiCad 9+ numbering (In1.Cu = 4, In2.Cu = 6, ...). Existing InN.Cu
        # entries are dropped first so a generator that reads its own output stays idempotent.
        layers = sexpr.child(self.board, "layers")
        layers[:] = [el for el in layers if not (isinstance(el, list) and re.fullmatch(r"In\d+\.Cu", str(el[1])))]
        i = next(k for k, el in enumerate(layers) if isinstance(el, list) and el[1] == "F.Cu")
        layers[i + 1:i + 1] = [[str(2 * n + 2), Q(f"In{n}.Cu"), "signal"] for n in range(1, copper_layers - 1)]
        setup = sexpr.child(self.board, "setup")
        for el in setup:
            if isinstance(el, list) and el[0] == "aux_axis_origin":
                el[1:] = [_n(self.OX), _n(self.OY + self.H)]
            if isinstance(el, list) and el[0] == "grid_origin":
                el[1:] = [_n(self.OX), _n(self.OY)]
        if self.net.variants:
            self.board.append(["variants"] + [["variant", ["name", Q(v)]] for v in self.net.variants])
        self.board.append(["net", "0", Q("")])
        for name, code in sorted(self.net.codes.items(), key=lambda kv: kv[1]):
            self.board.append(["net", str(code), Q(name)])
        self.items: list[sexpr.Node] = []

    def P(self, x: float, y: float) -> tuple[float, float]:
        return (self.OX + x, self.OY + y)

    # ---- footprints -----------------------------------------------------------
    def footprint(self, ref: str, x: float, y: float, rot: float = 0, *, ref_pos=None, ref_fab=False,
                  val_pos=None) -> dict[str, tuple[float, float]]:
        """Place the footprint the netlist assigns to `ref`; returns {pad: (x, y)} board-local.

        ref_pos: (dx, dy) offset of the Reference text on F.SilkS (default: library position);
        ref_fab: put the Reference on F.Fab hidden instead; val_pos: show the Value on F.SilkS
        at this offset. Offsets are unrotated board-local millimetres.
        """
        comp = self.net.comps[ref]
        lib, name = comp["footprint"].split(":")
        lib_dir = REPO_FOOTPRINT_DIR if lib == "boards" else os.path.join(FOOTPRINT_DIR, f"{lib}.pretty")
        with open(os.path.join(lib_dir, f"{name}.kicad_mod"), encoding="utf-8") as f:
            fp = sexpr.parse(f.read())
        out = ["footprint", Q(f"{lib}:{name}"), ["layer", Q("F.Cu")], ["uuid", _u()],
               ["at", _n(self.OX + x), _n(self.OY + y), _n(rot)]]
        props_seen = set()
        has_attr = any(isinstance(el, list) and el[0] == "attr" for el in fp[2:])
        if not has_attr and comp["flags"]:     # footprints without an attr clause still need the flags
            out.append(["attr"] + sorted(comp["flags"]))
        for vname, ov in comp["variants"].items():
            out.append(["variant", ["name", Q(vname)]] + [[k, "yes" if on else "no"] for k, on in ov.items()])
        pads: dict[str, tuple[float, float]] = {}
        for el in fp[2:]:
            if not isinstance(el, list):
                continue
            head = el[0]
            if head in ("version", "generator", "generator_version", "tedit", "tstamp", "uuid", "layer"):
                continue
            if head == "attr":      # keep smd/through_hole, add the schematic's dnp / exclude flags
                el = ["attr"] + [a for a in el[1:] if a in ("smd", "through_hole")] + sorted(comp["flags"])
            if head == "property":
                k = el[1]
                props_seen.add(k)
                val = {"Reference": ref, "Value": comp["value"], "Footprint": comp["footprint"],
                       "Datasheet": comp["datasheet"], "Description": comp["description"]}.get(k, el[2] if len(el) > 2 else "")
                el = ["property", Q(k), Q(val)] + [c for c in el[3:] if isinstance(c, list)]
                if k in ("Reference", "Value"):
                    el = [c for c in el if not (isinstance(c, list) and c[0] in ("hide", "at", "layer", "effects"))]
                    pos = ref_pos if k == "Reference" else val_pos
                    on_silk = (k == "Reference" and not ref_fab) or (k == "Value" and val_pos is not None)
                    el.append(["at", _n(pos[0]) if pos else "0", _n(pos[1]) if pos else "0", "0"])
                    el.append(["layer", Q("F.SilkS" if on_silk else "F.Fab")])
                    if not on_silk and not (k == "Reference" and not ref_fab):
                        el.append(["hide", "yes"])
                    el.append(["effects", ["font", ["size", "0.8", "0.8"], ["thickness", "0.15"]]])
            if head in ("fp_text", "pad"):
                at = sexpr.child(el, "at")
                if at is not None:
                    a = float(at[3]) if len(at) > 3 else 0.0
                    at[:] = ["at", at[1], at[2], _n((a + rot) % 360)]
                if head == "pad":
                    nname = self.net.node_net.get((ref, el[1]))
                    el = [c for c in el if not (isinstance(c, list) and c[0] == "net")]
                    if nname:
                        el.append(["net", str(self.net.codes[nname]), Q(nname)])
                    if el[1]:
                        dx, dy = rot_pt(float(at[1]), float(at[2]), rot)
                        pads[el[1]] = (round(x + dx, 4), round(y + dy, 4))
            if head in ("property", "fp_text", "fp_line", "fp_rect", "fp_circle", "fp_arc", "fp_poly", "pad", "model"):
                el = [c for c in el if not (isinstance(c, list) and c[0] == "uuid")]
                if head != "model":
                    el.append(["uuid", _u()])
            out.append(el)
        for k, v in [("Footprint", comp["footprint"]), ("Datasheet", comp["datasheet"]), ("Description", comp["description"])]:
            if k not in props_seen:
                out.append(["property", Q(k), Q(v), ["at", "0", "0", _n(rot)], ["layer", Q("F.Fab")], ["hide", "yes"], ["uuid", _u()],
                            ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]])
        for k, v in comp["fields"].items():
            if k in ("MPN", "Manufacturer", "LCSC"):
                out.append(["property", Q(k), Q(v), ["at", "0", "0", _n(rot)], ["layer", Q("F.Fab")], ["hide", "yes"], ["uuid", _u()],
                            ["effects", ["font", ["size", "1", "1"], ["thickness", "0.15"]]]])
        out.append(["path", Q("/" + comp["uuid"])])
        out.append(["sheetname", Q("/")])
        out.append(["sheetfile", Q(self.sheetfile)])
        self.items.append(out)
        return pads

    # ---- copper -------------------------------------------------------------------
    def seg(self, net_name: str, width: float, *pts, layer: str = "F.Cu"):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            (X1, Y1), (X2, Y2) = self.P(x1, y1), self.P(x2, y2)
            self.items.append(["segment", ["start", _n(X1), _n(Y1)], ["end", _n(X2), _n(Y2)], ["width", _n(width)],
                               ["layer", Q(layer)], ["net", str(self.net.codes[net_name])], ["uuid", _u()]])

    def via(self, net_name: str, x: float, y: float, size: float = 0.6, drill: float = 0.3):
        X, Y = self.P(x, y)
        self.items.append(["via", ["at", _n(X), _n(Y)], ["size", _n(size)], ["drill", _n(drill)],
                           ["layers", Q("F.Cu"), Q("B.Cu")], ["net", str(self.net.codes[net_name])], ["uuid", _u()]])

    def zone(self, net_name: str, zname: str, x1, y1, x2, y2, layer: str = "B.Cu", pad_clearance: float = 0.3, priority: int = 0):
        pts = [self.P(x1, y1), self.P(x2, y1), self.P(x2, y2), self.P(x1, y2)]
        self.items.append(["zone", ["net", str(self.net.codes[net_name])], ["net_name", Q(net_name)], ["layers", Q(layer)],
                           ["uuid", _u()], ["name", Q(zname)], ["hatch", "edge", "0.5"], ["priority", str(priority)],
                           ["connect_pads", ["clearance", _n(pad_clearance)]], ["min_thickness", "0.25"],
                           ["filled_areas_thickness", "no"], ["fill", "yes", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
                           ["polygon", ["pts"] + [["xy", _n(X), _n(Y)] for X, Y in pts]]])

    def keepout(self, x: float, y: float, r: float = 3.2, nseg: int = 24, name: str = "mounting keepout"):
        """Circular rule area: no tracks, vias or pour on either copper layer (pads allowed)."""
        pts = [self.P(x + r * math.cos(2 * math.pi * i / nseg), y + r * math.sin(2 * math.pi * i / nseg)) for i in range(nseg)]
        self.items.append(["zone", ["net", "0"], ["net_name", Q("")], ["layers", Q("*.Cu")], ["uuid", _u()],
                           ["name", Q(name)], ["hatch", "edge", "0.5"],
                           ["keepout", ["tracks", "not_allowed"], ["vias", "not_allowed"], ["pads", "allowed"],
                            ["copperpour", "not_allowed"], ["footprints", "allowed"]],
                           ["connect_pads", ["clearance", "0"]], ["min_thickness", "0.25"], ["filled_areas_thickness", "no"],
                           ["fill", ["thermal_gap", "0.5"], ["thermal_bridge_width", "0.5"]],
                           ["polygon", ["pts"] + [["xy", _n(X), _n(Y)] for X, Y in pts]]])

    # ---- graphics -----------------------------------------------------------------
    def gr_line(self, x1, y1, x2, y2, layer: str, width: float):
        (X1, Y1), (X2, Y2) = self.P(x1, y1), self.P(x2, y2)
        self.items.append(["gr_line", ["start", _n(X1), _n(Y1)], ["end", _n(X2), _n(Y2)],
                           ["stroke", ["width", _n(width)], ["type", "default"]], ["layer", Q(layer)], ["uuid", _u()]])

    def outline_rect(self):
        W, H = self.W, self.H
        for (x1, y1, x2, y2) in [(0, 0, W, 0), (W, 0, W, H), (W, H, 0, H), (0, H, 0, 0)]:
            self.gr_line(x1, y1, x2, y2, "Edge.Cuts", 0.1)

    def gr_text(self, s: str, x: float, y: float, layer: str = "F.SilkS", size: float = 0.8, rot: float = 0, justify=None):
        X, Y = self.P(x, y)
        eff = ["effects", ["font", ["size", _n(size), _n(size)], ["thickness", _n(size * 0.15)]]]
        if justify:
            eff.append(["justify"] + list(justify))
        self.items.append(["gr_text", Q(s), ["at", _n(X), _n(Y), _n(rot)], ["layer", Q(layer)], ["uuid", _u()], eff])

    # ---- output ---------------------------------------------------------------------
    def write(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(sexpr.dumps(self.board + self.items) + "\n")
