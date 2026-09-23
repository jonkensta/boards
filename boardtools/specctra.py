"""Specctra DSN writer and SES reader for autorouting KiCad boards with Freerouting.

kicad-cli (KiCad 10) cannot export DSN or import SES; that exists only in the pcbnew GUI
and its SWIG bindings. This module does both ends textually and stays parse-only: `dsn()`
turns a parsed .kicad_pcb (+ the .kicad_pro design rules) into DSN text, and `read_ses()`
turns a Freerouting session into plain wire/via records in KiCad board millimetres.
Writing those into a board is scripts/route.py's job.

Frames: KiCad is mm, y down; DSN here is `(unit um)` with `(resolution um 10)`, y up.
Every footprint becomes its own image placed `front` at rotation 0 with the pads already
rotated and positioned, so DSN image rotation/mirroring rules never come into play; pad
shapes are written pre-rotated (rect, polygon, oval as a round-ended path, circle).
"""

from __future__ import annotations

import fnmatch
import math

from . import pcb, sexpr

RES = 10  # DSN resolution: 10 units per um
UNITS_PER_MM = {"mm": 1.0, "um": 1000.0, "mil": 1000 / 25.4, "inch": 1 / 25.4, "cm": 0.1}


# ---- helpers ------------------------------------------------------------------------
def _f(node, head, i=1, default=None):
    el = sexpr.child(node, head)
    return el[i] if el is not None and len(el) > i else default


def _xy(node, head: str) -> tuple[float, float]:
    """(head x y) child as floats; a missing one is a malformed file, reported as ValueError."""
    el = sexpr.child(node, head)
    if el is None or len(el) < 3:
        raise ValueError(f"({node[0]} ...) has no ({head} x y)")
    return float(el[1]), float(el[2])


def _net(node) -> str | None:
    """Net name of an item: KiCad 10 writes (net "name"), older boards (net code "name")."""
    el = sexpr.child(node, "net")
    if el is None or len(el) < 2 or (len(el) == 2 and not isinstance(el[1], sexpr.Quoted)):
        return None  # missing, or a bare code such as (net 0)
    return el[-1]


def _q(name: str) -> str:
    """Quote a DSN identifier that is already DSN-safe (see `Names`)."""
    assert Names.safe(name), name
    return f'"{name}"'


class Names:
    """Reversible KiCad name <-> DSN identifier mapping.

    The DSN declares `(string_quote ")`, so an identifier cannot contain `"`; Freerouting also
    warns about and mangles non-ASCII. Safe names (printable ASCII without `"` or `\\`) are
    kept as they are for readable logs; anything else becomes `~<prefix><n>`. Every KiCad name
    maps to exactly one identifier and back, so distinct names never collide.
    """

    def __init__(self, prefix: str):
        self.prefix, self.to_dsn, self.to_kicad = prefix, {}, {}

    @staticmethod
    def safe(name: str) -> bool:
        return bool(name) and all(" " <= c <= "~" and c not in '"\\' for c in name)

    def __call__(self, name: str) -> str:
        if name not in self.to_dsn:
            ident = name if self.safe(name) else f"~{self.prefix}{len(self.to_dsn)}"
            while ident in self.to_kicad:
                ident = f"~{self.prefix}{len(self.to_kicad)}_{len(ident)}"
            self.to_dsn[name], self.to_kicad[ident] = ident, name
        return self.to_dsn[name]


def _c(v_mm: float) -> str:
    """mm -> DSN um, rounded to the 0.1 um resolution."""
    return f"{round(v_mm * 1000, 1) + 0.0:g}"  # + 0.0 turns -0.0 into 0


def _rot(x: float, y: float, deg: float) -> tuple[float, float]:
    """Rotate a y-up offset counter-clockwise by `deg` (KiCad angles are CCW on screen)."""
    r = math.radians(deg)
    return (x * math.cos(r) - y * math.sin(r), x * math.sin(r) + y * math.cos(r))


def to_dsn(x_mm: float, y_mm: float) -> tuple[float, float]:
    """KiCad board point (mm, y down) -> DSN point (mm, y up)."""
    return (x_mm, -y_mm)


def pad_position(fp_at, pad_at) -> tuple[float, float]:
    """Absolute KiCad position of a pad: footprint (x, y, rot) plus the local pad offset."""
    fx, fy, frot = fp_at
    dx, dy = _rot(pad_at[0], -pad_at[1], frot)  # into y-up, rotate CCW
    return (fx + dx, fy - dy)


def copper_of(layers: list[str], copper: list[str]) -> list[str]:
    """Expand a pad/zone layer list (`*.Cu`, `F&B.Cu`, names) to board copper layers."""
    out = []
    for name in layers:
        if name == "*.Cu":
            out += copper
        elif name == "F&B.Cu":
            out += [c for c in ("F.Cu", "B.Cu") if c in copper]
        elif name in copper:
            out.append(name)
    return list(dict.fromkeys(out))


def _pts(node, extent: bool = False) -> list[tuple[float, float]]:
    """(pts (xy ..) (arc (start) (mid) (end)) ...) -> points.

    Arcs become 16 chords for polygon outlines, or, with `extent`, `arc_extent` points whose
    bounding box is exactly the arc's (for pad envelopes).
    """
    out = []
    for p in node[1:]:
        if isinstance(p, list) and p[0] == "xy":
            out.append((float(p[1]), float(p[2])))
        elif isinstance(p, list) and p[0] == "arc":
            s, m, e = (_xy(p, k) for k in ("start", "mid", "end"))
            out += arc_extent(s, m, e) if extent else _arc(s, m, e)
    return out


# ---- pad shapes ---------------------------------------------------------------------
def slot(w: float, h: float, angle: float) -> tuple[float, float, float]:
    """An oval w x h turned by `angle` as (width, dx, dy): a round-ended stroke of that width
    from (-dx, -dy) to (dx, dy) about the centre, y up. dx = dy = 0 for a circle."""
    d = abs(w - h) / 2
    dx, dy = _rot(d, 0, angle) if w > h else _rot(0, d, angle)
    return min(w, h), dx, dy


def pad_shape(shape: str, w: float, h: float, angle: float, rratio: float = 0.0):
    """Pad outline as ('circle', d) | ('rect', x1, y1, x2, y2) | ('path', width, x1, y1, x2, y2)
    | ('polygon', [(x, y), ...]), centred on the pad, y up, mm, `angle` applied.

    chamfered_rect is its `size` rectangle (chamfers only remove copper); trapezoid and custom
    pads go through `pad_envelope` instead, because their copper can exceed `size`.
    """
    a = angle % 360
    if shape == "circle":
        return ("circle", w)
    if shape == "oval":
        if abs(w - h) < 1e-9:
            return ("circle", w)
        width, x, y = slot(w, h, a)
        return ("path", width, -x, -y, x, y)
    r = rratio * min(w, h) if shape == "roundrect" else 0.0
    if r <= 1e-9 and a % 90 == 0:
        if a % 180:
            w, h = h, w
        return ("rect", -w / 2, -h / 2, w / 2, h / 2)
    if r <= 1e-9:
        corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    else:
        # Circumscribed 30-degree chords (vertices at 15/45/75 deg on r / cos 15): the polygon
        # contains the true arc, so routes never end up closer than the clearance.
        rr = r / math.cos(math.radians(15))
        corners = []
        for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
                           (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)):
            corners += [(cx + rr * math.cos(math.radians(a0 + t)), cy + rr * math.sin(math.radians(a0 + t)))
                        for t in (15, 45, 75)]
    return ("polygon", [_rot(x, y, a) for x, y in corners])


def pad_envelope(pad, w: float, h: float) -> tuple[float, float, float, float]:
    """(x1, y1, x2, y2) bounding the copper of a trapezoid or custom pad, pad-local, y down.

    Trapezoid: `rect_delta` (dx, dy) widens the y extent by dx / 2 and the x extent by dy / 2
    (matches KiCad's effective polygon). Custom: the anchor (`size`) plus every primitive with
    half its stroke width; arcs (standalone or inside polygons) are bounded exactly by
    `arc_extent`, curves by their control points (the curve lies inside their hull).
    """
    if pad[3] == "trapezoid":
        d = sexpr.child(pad, "rect_delta")
        dx, dy = (abs(float(d[1])), abs(float(d[2]))) if d is not None and len(d) > 2 else (0.0, 0.0)
        return (-w / 2 - dy / 2, -h / 2 - dx / 2, w / 2 + dy / 2, h / 2 + dx / 2)
    xs, ys = [-w / 2, w / 2], [-h / 2, h / 2]
    prims = sexpr.child(pad, "primitives")
    for g in (prims[1:] if prims is not None else []):
        if not isinstance(g, list):
            continue
        half = float(_f(g, "width", default=0) or 0) / 2
        pts: list[tuple[float, float]] = []
        if g[0] == "gr_poly" and sexpr.child(g, "pts") is not None:
            pts = _pts(sexpr.child(g, "pts"), extent=True)
        elif g[0] in ("gr_line", "gr_rect"):
            pts = [_xy(g, "start"), _xy(g, "end")]
        elif g[0] == "gr_circle":
            (cx, cy), (ex, ey) = _xy(g, "center"), _xy(g, "end")
            r = math.hypot(ex - cx, ey - cy)
            pts = [(cx - r, cy - r), (cx + r, cy + r)]
        elif g[0] == "gr_arc":
            pts = arc_extent(_xy(g, "start"), _xy(g, "mid"), _xy(g, "end"))
        elif g[0] == "gr_curve" and sexpr.child(g, "pts") is not None:
            pts = _pts(sexpr.child(g, "pts"))
        xs += [x - half for x, _ in pts] + [x + half for x, _ in pts]
        ys += [y - half for _, y in pts] + [y + half for _, y in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def envelope_shape(box: tuple[float, float, float, float], angle: float):
    """A pad-local (y down) box as a DSN ('polygon', ...) centred on the pad, y up, turned."""
    x1, y1, x2, y2 = box
    return ("polygon", [_rot(x, -y, angle) for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2))])


def _shape_dsn(layer: str, s) -> str:
    kind = s[0]
    if kind == "circle":
        return f"(circle {_q(layer)} {_c(s[1])})"
    if kind == "rect":
        return f"(rect {_q(layer)} {' '.join(_c(v) for v in s[1:])})"
    if kind == "path":
        return f"(path {_q(layer)} {_c(s[1])} {' '.join(_c(v) for v in s[2:])})"
    pts = " ".join(f"{_c(x)} {_c(y)}" for x, y in s[1])
    return f"(polygon {_q(layer)} 0 {pts})"


# ---- design rules -------------------------------------------------------------------
RULE_KEYS = ("track_width", "clearance", "via_diameter", "via_drill")
FALLBACK = dict(track_width=0.2, clearance=0.2, via_diameter=0.6, via_drill=0.3)


def netclasses(project: dict, nets: list[str]) -> tuple[dict[str, dict], dict[str, str]]:
    """({class: {track_width, clearance, via_diameter, via_drill}}, {net: class}) from .kicad_pro.

    Like KiCad 10's effective netclass: every class a net gets (explicit
    `netclass_assignments` plus every matching `netclass_patterns` wildcard) is sorted by
    `priority` (lowest first), and each rule is taken separately from the first of those
    classes that sets it, then from `Default`. A net with several classes gets a composite
    class named like KiCad's, e.g. `Power,Wide`.
    """
    ns = project.get("net_settings", {})
    raw = {c["name"]: c for c in ns.get("classes", []) if "name" in c}
    base = {k: v for k, v in raw.get("Default", {}).items() if v is not None}
    default = {k: float(base.get(k, FALLBACK[k])) for k in RULE_KEYS}
    prio = {n: c.get("priority", 0) for n, c in raw.items()}
    assigned = ns.get("netclass_assignments") or {}
    patterns = ns.get("netclass_patterns") or []
    classes: dict[str, dict] = {"Default": default}
    out = {}
    for net in nets:
        names = [c for c in (assigned.get(net) or []) if c in raw and c != "Default"]
        names += [p["netclass"] for p in patterns if p.get("netclass") in raw and p["netclass"] != "Default"
                  and fnmatch.fnmatchcase(net, p.get("pattern", ""))]
        names = sorted(dict.fromkeys(names), key=lambda c: (prio[c], c))
        cname = ",".join(names) or "Default"
        if cname not in classes:
            rules = dict(default)
            for k in RULE_KEYS:
                v = next((raw[c][k] for c in names if raw[c].get(k) is not None), None)
                if v is not None:
                    rules[k] = float(v)
            classes[cname] = rules
        out[net] = cname
    return classes, out


def via_name(size: float, drill: float, n_layers: int) -> str:
    return f"Via[0-{n_layers - 1}]_{_c(size)}:{_c(drill)}_um"


def parse_via_name(name: str) -> tuple[float, float]:
    """`Via[0-1]_600:300_um` -> (0.6, 0.3) mm."""
    size, drill = name.rsplit("_", 2)[1].split(":")
    return float(size) / 1000, float(drill) / 1000


# ---- board outline ------------------------------------------------------------------
def _edges(root) -> list[list[tuple[float, float]]]:
    """Edge.Cuts graphics as polylines (arcs and circles approximated by chords)."""
    out = []
    for el in root[1:]:
        if not isinstance(el, list) or _f(el, "layer") != "Edge.Cuts":
            continue
        head = el[0]
        pt = lambda k: _xy(el, k)
        if head == "gr_line":
            out.append([pt("start"), pt("end")])
        elif head == "gr_rect":
            (x1, y1), (x2, y2) = pt("start"), pt("end")
            out.append([(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)])
        elif head == "gr_poly":
            pts = sexpr.child(el, "pts")
            p = _pts(pts) if pts is not None else []
            out.append(p + p[:1])
        elif head == "gr_circle":
            (cx, cy), (ex, ey) = pt("center"), pt("end")
            r = math.hypot(ex - cx, ey - cy)
            out.append([(cx + r * math.cos(2 * math.pi * i / 48), cy + r * math.sin(2 * math.pi * i / 48))
                        for i in range(49)])
        elif head == "gr_arc":
            out.append(_arc(pt("start"), pt("mid"), pt("end")))
    return out


def _circle(s, m, e):
    """(cx, cy, r, t0, sweep) of the arc from s through m to e (sweep signed, radians), or
    None for collinear points (a straight segment)."""
    ax, ay, bx, by, cx, cy = *s, *m, *e
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    t0, tm, t1 = (math.atan2(p[1] - uy, p[0] - ux) for p in (s, m, e))
    sweep = (t1 - t0) % (2 * math.pi)
    if (tm - t0) % (2 * math.pi) > sweep:  # mid not on the CCW sweep: go the other way
        sweep -= 2 * math.pi
    return ux, uy, math.hypot(ax - ux, ay - uy), t0, sweep


def _arc(s, m, e, nseg: int = 16) -> list[tuple[float, float]]:
    """The arc as nseg chords (inscribed: fine for outlines, not for clearance bounds)."""
    c = _circle(s, m, e)
    if c is None:
        return [s, e]
    ux, uy, r, t0, sweep = c
    return [(ux + r * math.cos(t0 + sweep * i / nseg), uy + r * math.sin(t0 + sweep * i / nseg)) for i in range(nseg + 1)]


def arc_extent(s, m, e) -> list[tuple[float, float]]:
    """Points whose bounding box is exactly the arc's: its ends plus every axis extreme
    (0/90/180/270 deg on its circle) that the swept angle crosses."""
    c = _circle(s, m, e)
    if c is None:
        return [s, e]
    ux, uy, r, t0, sweep = c
    out = [s, e]
    for k in range(4):
        a = k * math.pi / 2
        if ((a - t0) if sweep > 0 else (t0 - a)) % (2 * math.pi) <= abs(sweep):
            out.append((ux + r * math.cos(a), uy + r * math.sin(a)))
    return out


def outline_loops(root, tol: float = 1e-3) -> list[list[tuple[float, float]]]:
    """Chain Edge.Cuts pieces into closed loops, largest (by area) first."""
    pieces = _edges(root)
    loops = []
    while pieces:
        loop = pieces.pop(0)
        grown = True
        while grown and math.dist(loop[0], loop[-1]) > tol:
            grown = False
            for i, p in enumerate(pieces):
                if math.dist(loop[-1], p[0]) <= tol:
                    loop += p[1:]
                elif math.dist(loop[-1], p[-1]) <= tol:
                    loop += p[-2::-1]
                else:
                    continue
                pieces.pop(i)
                grown = True
                break
        if math.dist(loop[0], loop[-1]) > tol:
            raise ValueError(f"Edge.Cuts outline is not closed near {loop[-1]}")
        loops.append(loop)
    area = lambda l: abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(l, l[1:])))
    return sorted(loops, key=area, reverse=True)


# ---- DSN ------------------------------------------------------------------------------
def _area(z, copper: list[str]) -> tuple[list[str], list[list[tuple[float, float]]]]:
    """Copper layers and polygons (outline first, then holes) of a zone, in DSN mm.

    KiCad writes a zone as one `(polygon)` outline followed by one `(polygon)` per hole
    (verified: a second outline added through the API is dropped on save).
    """
    zl = sexpr.child(z, "layers") or sexpr.child(z, "layer")
    layers = copper_of(list(zl[1:]) if zl is not None else [], copper)
    polys = []
    for poly in sexpr.children(z, "polygon"):
        pts = sexpr.child(poly, "pts")
        if pts is not None:
            polys.append([to_dsn(x, y) for x, y in _pts(pts)])
    return layers, [p for p in polys if len(p) >= 3]


def _area_dsn(layer: str, polys) -> str:
    """`(polygon ...)` outline plus `(window (polygon ...))` holes, as Freerouting reads them."""
    coords = [" ".join(f"{_c(x)} {_c(y)}" for x, y in p) for p in polys]
    return f"(polygon {_q(layer)} 0 {coords[0]})" + "".join(
        f" (window (polygon {_q(layer)} 0 {c}))" for c in coords[1:])


def dsn(root, project: dict, name: str = "board") -> tuple[str, dict[str, str]]:
    """Specctra DSN text for a parsed .kicad_pcb and its parsed .kicad_pro.

    Returns (text, nets) where `nets` maps each DSN net identifier back to its KiCad net name;
    pass it to `read_ses`.
    """
    copper = pcb.copper_layers(root)
    if not copper:
        raise ValueError("board has no copper layers")
    table = sexpr.child(root, "layers")
    types = {e[1]: e[2] for e in (table[1:] if table is not None else []) if isinstance(e, list) and len(e) > 2}
    rules = project.get("board", {}).get("design_settings", {}).get("rules", {})
    loops = outline_loops(root)
    if not loops:
        raise ValueError("board has no Edge.Cuts outline")
    net_id, ref_id, cls_id = Names("net"), Names("ref"), Names("class")

    base_clearance = netclasses(project, [])[0]["Default"]["clearance"]
    # Freerouting keeps only `clearance` from keepouts. KiCad 10 DRC (verified) applies
    # min_hole_clearance to a round NPTH hole, but treats a slot's wall as board edge too.
    hole_rule = float(rules.get("min_hole_clearance", 0) or 0)
    hole_extra = max(hole_rule - base_clearance, 0)
    slot_extra = max(max(hole_rule, float(rules.get("min_copper_edge_clearance", 0) or 0)) - base_clearance, 0)
    padstacks: dict[str, str] = {}   # name -> shapes
    padstack_of: dict[str, str] = {}  # (shapes + pad kind) -> name
    images, places, keepouts = [], [], []
    pins_of: dict[str, list[str]] = {}
    zones = list(sexpr.children(root, "zone"))
    for fp in sexpr.children(root, "footprint"):
        zones += sexpr.children(fp, "zone")  # footprint rule areas are stored in board coordinates
        ref = ref_id(next((p[2] for p in sexpr.children(fp, "property") if len(p) > 2 and p[1] == "Reference"), "") or "?")
        at = sexpr.child(fp, "at")
        fp_at = (float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0) if at is not None else (0.0, 0.0, 0.0)
        fx, fy = to_dsn(fp_at[0], fp_at[1])
        pins, pin_id = [], Names("pin")
        for pad in sexpr.children(fp, "pad"):
            num, kind, shape = pad[1], pad[2], pad[3]
            pat = sexpr.child(pad, "at")
            if pat is None:
                continue
            # Pad angles are stored absolute (footprint rotation included) and omitted when 0;
            # positions are footprint-local, already mirrored on flipped footprints.
            angle = float(pat[3]) if len(pat) > 3 else 0.0
            px, py = to_dsn(*pad_position(fp_at, (float(pat[1]), float(pat[2]))))
            size = sexpr.child(pad, "size")
            w = float(size[1]) if size is not None else 0.0
            h = float(size[2]) if size is not None and len(size) > 2 else w
            pl = sexpr.child(pad, "layers")
            layers = copper_of(list(pl[1:]) if pl is not None else [], copper)
            if kind == "np_thru_hole":
                drill = sexpr.child(pad, "drill")
                if drill is not None and len(drill) > 1:
                    # Grow the keepout by what KiCad wants beyond Freerouting's clearance (see
                    # hole_extra/slot_extra above). Slots stay slots.
                    dw, dh = (float(drill[2]), float(drill[3] if len(drill) > 3 else drill[2])) if drill[1] == "oval" \
                        else (float(drill[1]), float(drill[1]))
                    grow = 2 * (hole_extra if abs(dw - dh) < 1e-9 else slot_extra)
                    width, dx, dy = slot(dw + grow, dh + grow, angle)
                    shape_of = (lambda l: f"(circle {_q(l)} {_c(width)} {_c(px)} {_c(py)})") if abs(dw - dh) < 1e-9 else \
                        (lambda l: f"(path {_q(l)} {_c(width)} {_c(px - dx)} {_c(py - dy)} {_c(px + dx)} {_c(py + dy)})")
                    keepouts += [f"(keepout \"\" {shape_of(l)})" for l in copper]
                continue
            if not layers:
                continue
            if shape in ("custom", "trapezoid"):
                sh = envelope_shape(pad_envelope(pad, w, h), angle)
            else:
                sh = pad_shape(shape, w, h, angle, float(_f(pad, "roundrect_rratio", default=0)))
            body = " ".join(f"(shape {_shape_dsn(l, sh)})" for l in layers)
            ps = padstack_of.get(f"{body} {kind}")
            if ps is None:
                ps = padstack_of[f"{body} {kind}"] = f"Pad_{len(padstacks)}_{shape}_{'T' if kind == 'thru_hole' else 'S'}"
                padstacks[ps] = body
            # Unnumbered copper pads stay in as netless pins (obstacles); stacked pads with the
            # same number each get their own identifier (`Names` never repeats one).
            pin = pin_id(num if num and num not in pin_id.to_dsn else f"{num}\x00{len(pin_id.to_dsn)}")
            pins.append(f"      (pin {_q(ps)} {_q(pin)} {_c(px - fx)} {_c(py - fy)})")
            net = _net(pad)
            if net and num:
                pins_of.setdefault(net, []).append(f"{_q(ref)}-{_q(pin)}")  # halves quoted, not the whole
        if not pins:  # mounting holes etc.: their holes are keepouts already
            continue
        image = f"{ref}__img" if Names.safe(f"{ref}__img") else ref
        images.append(f"    (image {_q(image)}\n" + "\n".join(pins) + "\n    )")
        places.append(f"    (component {_q(image)} (place {_q(ref)} {_c(fx)} {_c(fy)} front 0))")

    # zones: rule areas (board and footprint) -> keepouts with windows, pours -> planes
    planes = []
    for z in zones:
        layers, polys = _area(z, copper)
        if not layers or not polys:
            continue
        ko = sexpr.child(z, "keepout")
        if ko is not None:
            no = lambda k: _f(ko, k) == "not_allowed"
            kind = "keepout" if no("tracks") and no("vias") else "wire_keepout" if no("tracks") else \
                   "via_keepout" if no("vias") else None
            if kind:
                keepouts += [f"({kind} \"\" {_area_dsn(l, polys)})" for l in layers]
            continue
        net = _f(z, "net_name") or _net(z)
        if net:
            planes += [f"    (plane {_q(net_id(net))} {_area_dsn(l, polys)})" for l in layers]

    # rules, via padstacks, classes
    nets = sorted(pins_of)
    classes, net_class = netclasses(project, nets)
    n = len(copper)
    vias = {}
    for c in classes.values():
        vias.setdefault(via_name(c["via_diameter"], c["via_drill"], n), c["via_diameter"])
    wiring = []
    netref = lambda el: f"(net {_q(net_id(nm))}) " if (nm := _net(el)) else ""
    for v in sexpr.children(root, "via"):
        at, size, drill = sexpr.child(v, "at"), _f(v, "size"), _f(v, "drill")
        if at is None or size is None or drill is None:
            continue
        vn = via_name(float(size), float(drill), n)
        vias.setdefault(vn, float(size))
        x, y = to_dsn(float(at[1]), float(at[2]))
        wiring.append(f"    (via {_q(vn)} {_c(x)} {_c(y)} {netref(v)}(type protect))")
    for seg in list(sexpr.children(root, "segment")) + list(sexpr.children(root, "arc")):
        layer = _f(seg, "layer")
        if layer not in copper:
            continue
        p = [_xy(seg, "start"), _xy(seg, "end")]
        if seg[0] == "arc":
            p = _arc(p[0], _xy(seg, "mid"), p[1], 8)
        coords = " ".join(f"{_c(x)} {_c(y)}" for x, y in (to_dsn(*q) for q in p))
        wiring.append(f"    (wire (path {_q(layer)} {_c(float(_f(seg, 'width', default=0)))} {coords}) "
                      f"{netref(seg)}(type protect))")
    for vn, size in vias.items():
        padstacks[vn] = " ".join(f"(shape (circle {_q(l)} {_c(size)}))" for l in copper)

    default = classes["Default"]
    edge = max(float(rules.get("min_copper_edge_clearance", 0) or 0) - default["clearance"], 0)
    boundary = " ".join(f"{_c(x)} {_c(y)}" for x, y in (to_dsn(*p) for p in loops[0]))
    lines = [f"(pcb {_q(name + '.dsn') if Names.safe(name) else _q('board.dsn')}",
             "  (parser", "    (string_quote \")", "    (space_in_quoted_tokens on)",
             "    (host_cad \"KiCad's Pcbnew\")", "    (host_version \"10.0 boardtools\")", "  )",
             f"  (resolution um {RES})", "  (unit um)", "  (structure"]
    for i, l in enumerate(copper):
        kind = "power" if types.get(l) == "power" else "signal"
        lines.append(f"    (layer {_q(l)} (type {kind}) (property (index {i})))")
    lines.append(f"    (boundary (path pcb 0 {boundary}))")
    for loop in loops[1:]:  # inner Edge.Cuts loops are cut-outs
        coords = " ".join(f"{_c(x)} {_c(y)}" for x, y in (to_dsn(*p) for p in loop))
        keepouts += [f"(keepout \"\" (polygon {_q(l)} 0 {coords}))" for l in copper]
    if edge > 0:  # Freerouting keeps `clearance` from the outline; widen it to the edge rule
        for a, b in zip(loops[0], loops[0][1:]):
            (x1, y1), (x2, y2) = to_dsn(*a), to_dsn(*b)
            keepouts += [f"(keepout \"\" (path {_q(l)} {_c(2 * edge)} {_c(x1)} {_c(y1)} {_c(x2)} {_c(y2)}))"
                         for l in copper]
    lines += [f"    {k}" for k in keepouts] + planes
    lines.append("    (via " + " ".join(_q(v) for v in vias) + ")")
    lines.append(f"    (rule (width {_c(default['track_width'])}) (clearance {_c(default['clearance'])}))")
    lines += ["  )", "  (placement"] + places + ["  )", "  (library"] + images
    for ps, body in padstacks.items():
        lines.append(f"    (padstack {_q(ps)} {body} (attach off))")
    lines += ["  )", "  (network"]
    for net in nets:
        lines.append(f"    (net {_q(net_id(net))} (pins {' '.join(pins_of[net])}))")
    for cname, c in classes.items():
        members = [net for net in nets if net_class[net] == cname]
        if not members:
            continue
        lines.append(f"    (class {_q(cls_id(cname))} {' '.join(_q(net_id(m)) for m in members)}"
                     f" (circuit (use_via {_q(via_name(c['via_diameter'], c['via_drill'], n))}))"
                     f" (rule (width {_c(c['track_width'])}) (clearance {_c(c['clearance'])})))")
    lines += ["  )", "  (wiring"] + wiring + ["  )", ")"]
    return "\n".join(lines) + "\n", dict(net_id.to_kicad)


# ---- SES --------------------------------------------------------------------------------
def read_ses(text: str, nets: dict[str, str] | None = None) -> tuple[list[dict], list[dict]]:
    """Wires and vias from a Freerouting .ses, in KiCad board mm (y down).

    `nets` is the DSN-identifier -> KiCad-name map `dsn()` returned; with it, every net is
    translated back and an unknown one is an error.

    Returns (wires, vias): wire = {net, layer, width, points: [(x, y), ...]},
    via = {net, padstack, x, y, protected}. `(type protect)` items are the fixed wiring the
    DSN carried in; callers normally skip them.
    """
    root = sexpr.parse(text)
    routes = sexpr.child(root, "routes")
    if routes is None:
        raise ValueError("no (routes ...) in session file")
    res = sexpr.child(routes, "resolution")
    scale = float(res[2]) * UNITS_PER_MM[res[1]] if res is not None else RES * 1000.0
    k = lambda v: float(v) / scale
    wires, vias = [], []
    out = sexpr.child(routes, "network_out")
    for net in (sexpr.children(out, "net") if out is not None else []):
        name = net[1]
        if nets is not None:
            if name not in nets:
                raise ValueError(f"session net {name!r} is not in the DSN")
            name = nets[name]
        for w in sexpr.children(net, "wire"):
            path = sexpr.child(w, "path") or sexpr.child(w, "polyline_path")
            if path is None:
                continue
            nums = path[3:]
            pts = [(k(nums[i]), -k(nums[i + 1])) for i in range(0, len(nums) - 1, 2)]
            wires.append(dict(net=name, layer=path[1], width=k(path[2]), points=pts,
                              protected=_f(w, "type") in ("protect", "fix")))
        for v in sexpr.children(net, "via"):
            vias.append(dict(net=name, padstack=v[1], x=k(v[2]), y=-k(v[3]),
                             protected=_f(v, "type") in ("protect", "fix")))
    return wires, vias
