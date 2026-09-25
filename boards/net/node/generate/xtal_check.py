#!/usr/bin/env python3
"""Crystal isolation check: minimum same-layer edge-to-edge gap between the crystal nets' copper
(tracks, vias, pads of XIN / XOUT / the R1-Y1 node) and any other non-GND copper.

pcb.py calls `gaps()` on its generated items and fails below MIN_GAP; run standalone on a board
file to audit it:  python3 xtal_check.py [board.kicad_pcb] [report-radius-mm]

Shapes: tracks (arcs as chords) and oval pads are capsules, circle pads and vias discs, rect / roundrect pads their
full rectangle (the rounded corners are ignored, so the gap is never overestimated). Zones are
measured too (filled polygons, else the outline), as are crystal-net zones if any; copper the
checker does not model (copper graphics, visible text or properties on copper, custom pads) raises
instead of passing silently. The RP2040's own pins are 0.4 mm apart, so
crystal copper inside U1's pad bounding box grown by ESCAPE is not checked (U1's XIN / XOUT pads
and the first 1.5 mm of their escape); everything else must keep the gap from what lies beyond.
"""
import math, os, sys

_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, 'boardtools')):
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from boardtools import sexpr

MIN_GAP = 1.0                                   # any other non-GND net
LED_GAP = 2.0                                   # LED switching nets (supply included) and every pad of every LED
CRYSTAL = ('Net-(U1-XIN)', 'Net-(U1-XOUT)', 'Net-(C2-Pad2)')
LED_NETS = ('+5V', '/LED_DATA', '/LED_DIN', '/LED_CH1', '/LED_CH2', '/LED_CH3')   # +5V is the LEDs' supply since D1 went
LED_REFS = ('D1', 'D2', 'D3', 'D4')             # the four corner WS2812B-2020s
EXEMPT = ('GND',)                               # plus 'unconnected-*' pins (no signal), except LED pads
OX = OY = 50.0                                  # board origin (reported positions are board-local)
MCU, ESCAPE = 'U1', 1.5                         # crystal copper within ESCAPE of U1's pad field is the pin escape:
                                                # XIN / XOUT sit between IOVDD 22 and TESTEN at 0.4 mm pitch there
CU = ('F.Cu', 'In1.Cu', 'In2.Cu', 'B.Cu')


def _s(v):
    return str(v).strip('"')


def _net(node, codes):
    n = sexpr.child(node, 'net')
    if n is None:
        return ''
    v = _s(n[-1])
    return codes.get(v, v) if len(n) == 2 else v


def _layers(node):
    ls = [_s(x) for x in (sexpr.child(node, 'layers') or sexpr.child(node, 'layer'))[1:]]
    return [c for c in CU if c in ls or '*.Cu' in ls or ('F&B.Cu' in ls and c in ('F.Cu', 'B.Cu'))]


def _cu(node):
    """Copper layers a graphic / text item sits on (empty if none)."""
    ls = sexpr.child(node, 'layers') or sexpr.child(node, 'layer')
    return [x for x in map(_s, ls[1:]) if x in CU or x.endswith('.Cu')] if ls else []


def _arc(s, m, e, n=24):
    """Points along the circular arc start -> mid -> end."""
    (ax, ay), (bx, by), (cx, cy) = s, m, e
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return [s, e]
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    t0, tm, t1 = (math.atan2(y - uy, x - ux) for x, y in (s, m, e))
    sweep = (t1 - t0) % (2 * math.pi)
    if (tm - t0) % (2 * math.pi) > sweep:                    # mid not on the ccw sweep: go the other way
        sweep -= 2 * math.pi
    return [(ux + r * math.cos(t0 + sweep * i / n), uy + r * math.sin(t0 + sweep * i / n)) for i in range(n + 1)]


def _radius(s, m, e):
    (ax, ay), (bx, by), (cx, cy) = s, m, e
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return 0.0
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    return math.hypot(ax - ux, ay - uy)


def _hidden(node):
    h = sexpr.child(node, 'hide')
    eff = sexpr.child(node, 'effects')
    return 'hide' in node or (h is not None and _s(h[1:2][0] if len(h) > 1 else 'yes') == 'yes') or \
        (eff is not None and ('hide' in eff or any(isinstance(x, list) and x[0] == 'hide' and _s(x[1:2][0] if len(x) > 1 else 'yes') == 'yes' for x in eff)))


def _pts(node):
    return [(float(p[1]), float(p[2])) for p in sexpr.child(node, 'pts')[1:] if p[0] == 'xy']


def shapes(items, codes):
    """[(net, layer, kind, data, footprint ref or '')]: kind 'cap' (x0, y0, x1, y1, r) or 'poly' ([(x, y)...], any
    simple polygon); absolute mm. Tracks (segments, arcs as 24 chords widened by their sagitta), vias, pads and zone copper (filled polygons,
    or the outline of an unfilled zone). Copper this does not model (graphics / text on copper, custom pads) raises."""
    out = []
    for it in items:
        if not isinstance(it, list):
            continue
        if it[0] == 'segment':
            s, e = sexpr.child(it, 'start'), sexpr.child(it, 'end')
            r = float(sexpr.child(it, 'width')[1]) / 2
            out.append((_net(it, codes), _layers(it)[0], 'cap', (float(s[1]), float(s[2]), float(e[1]), float(e[2]), r), ''))
        elif it[0] == 'arc':
            s, m, e = ((float(c[1]), float(c[2])) for c in (sexpr.child(it, h) for h in ('start', 'mid', 'end')))
            r = float(sexpr.child(it, 'width')[1]) / 2
            ps = _arc(s, m, e)
            # chords are inscribed: widen each by the arc's maximum sagitta so the gap is never overestimated
            R = _radius(s, m, e); n = len(ps) - 1
            sweep = sum(math.dist(p, q) for p, q in zip(ps, ps[1:])) / R if R else 0.0
            sag = R * (1 - math.cos(sweep / n / 2)) if R else 0.0
            out += [(_net(it, codes), _layers(it)[0], 'cap', (*p, *q, r + sag), '') for p, q in zip(ps, ps[1:])]
        elif it[0] == 'via':
            a = sexpr.child(it, 'at'); r = float(sexpr.child(it, 'size')[1]) / 2
            for L in CU:                                           # through vias: annulus on every layer
                out.append((_net(it, codes), L, 'cap', (float(a[1]), float(a[2]), float(a[1]), float(a[2]), r), ''))
        elif it[0] == 'zone':
            if sexpr.child(it, 'keepout') is not None:
                continue
            net = _net(it, codes) or _s((sexpr.child(it, 'net_name') or ['', ''])[1])
            fills = list(sexpr.children(it, 'filled_polygon'))
            if fills:
                for f in fills:
                    L = _s(sexpr.child(f, 'layer')[1])
                    if L in CU:
                        out.append((net, L, 'poly', _pts(f), ''))
            else:
                outline = _pts(sexpr.child(it, 'polygon'))
                for L in _layers(it):
                    out.append((net, L, 'poly', outline, ''))
        elif it[0].startswith('gr_') and _cu(it):
            raise ValueError(f'xtal_check: {it[0]} on copper is not modelled')
        elif it[0] == 'footprint':
            at = sexpr.child(it, 'at'); fx, fy = float(at[1]), float(at[2])
            fr = math.radians(float(at[3]) if len(at) > 3 else 0)
            ref = next((_s(q[2]) for q in it if isinstance(q, list) and q[0] == 'property' and _s(q[1]) == 'Reference'), '')
            for g in it:
                if isinstance(g, list) and g[0].startswith('fp_') and _cu(g):
                    raise ValueError(f'xtal_check: {ref} {g[0]} on copper is not modelled')
                if isinstance(g, list) and g[0] == 'property' and _cu(g) and not _hidden(g):
                    raise ValueError(f'xtal_check: {ref} visible property {_s(g[1])} on copper is not modelled')
            for p in sexpr.children(it, 'pad'):
                if _s(p[2]) == 'np_thru_hole':
                    continue
                pa, sz = sexpr.child(p, 'at'), sexpr.child(p, 'size')
                px, py = float(pa[1]), float(pa[2])
                cx, cy = fx + px * math.cos(fr) + py * math.sin(fr), fy - px * math.sin(fr) + py * math.cos(fr)
                a = math.radians(float(pa[3]) if len(pa) > 3 else 0)      # absolute pad angle
                hw, hh = float(sz[1]) / 2, float(sz[2]) / 2
                rot = lambda dx, dy: (cx + dx * math.cos(a) + dy * math.sin(a), cy - dx * math.sin(a) + dy * math.cos(a))
                shape = _s(p[3])
                if shape == 'circle':
                    geo = ('cap', (cx, cy, cx, cy, hw))
                elif shape == 'oval':
                    d = abs(hw - hh)
                    (x0, y0), (x1, y1) = (rot(-d, 0), rot(d, 0)) if hw > hh else (rot(0, -d), rot(0, d))
                    geo = ('cap', (x0, y0, x1, y1, min(hw, hh)))
                elif shape in ('rect', 'roundrect'):
                    geo = ('poly', [rot(-hw, -hh), rot(hw, -hh), rot(hw, hh), rot(-hw, hh)])
                else:
                    raise ValueError(f'xtal_check: {ref} pad {p[1]} shape {shape} is not modelled')
                for L in _layers(p):
                    out.append((_net(p, codes), L, *geo, ref))
    return out


def _pp(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy or 1)))
    return math.hypot(px - x0 - t * dx, py - y0 - t * dy)


def _ss(a, b):
    """Distance between segments a and b (0 if they cross)."""
    (ax0, ay0, ax1, ay1), (bx0, by0, bx1, by1) = a, b
    cr = lambda ox, oy, px, py, qx, qy: (px - ox) * (qy - oy) - (py - oy) * (qx - ox)
    d1, d2 = cr(bx0, by0, bx1, by1, ax0, ay0), cr(bx0, by0, bx1, by1, ax1, ay1)
    d3, d4 = cr(ax0, ay0, ax1, ay1, bx0, by0), cr(ax0, ay0, ax1, ay1, bx1, by1)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return 0.0
    return min(_pp(ax0, ay0, *b), _pp(ax1, ay1, *b), _pp(bx0, by0, *a), _pp(bx1, by1, *a))


def _inside(x, y, poly):
    """Even-odd point in polygon (any simple polygon)."""
    c = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            c = not c
    return c


def _edges(kind, data):
    """(segments, radius) of a shape's skeleton."""
    if kind == 'cap':
        return [data[:4]], data[4]
    return [(*p, *q) for p, q in zip(data, data[1:] + data[:1])], 0.0


def gap(a, b):
    (ka, da), (kb, db) = a, b
    ea, ra = _edges(ka, da); eb, rb = _edges(kb, db)
    for k, d, e in ((ka, da, eb), (kb, db, ea)):                 # a skeleton point inside the other polygon
        if k == 'poly' and any(_inside(s[0], s[1], d) for s in e):
            return 0.0
    return max(0.0, min(_ss(s, t) for s in ea for t in eb) - ra - rb)


def limit(net, ref=''):
    """Required gap to crystal copper for a shape of `net` (on footprint `ref`)."""
    return LED_GAP if net in LED_NETS or ref in LED_REFS else MIN_GAP


def _clip_out(seg, box):
    """Pieces of segment (x0, y0, x1, y1) outside the axis-aligned box (bx0, by0, bx1, by1)."""
    x0, y0, x1, y1 = seg
    t0, t1 = 0.0, 1.0
    for p, q in ((-(x1 - x0), x0 - box[0]), (x1 - x0, box[2] - x0), (-(y1 - y0), y0 - box[1]), (y1 - y0, box[3] - y0)):
        if p == 0:
            if q < 0:
                return [seg]
        elif p < 0:
            t0 = max(t0, q / p)
        else:
            t1 = min(t1, q / p)
    if t0 >= t1:
        return [seg]
    at = lambda t: (x0 + t * (x1 - x0), y0 + t * (y1 - y0))
    return [(x0, y0, *at(t0))] * (t0 > 1e-9) + [(*at(t1), x1, y1)] * (t1 < 1 - 1e-9)


def _at(k, d):
    x, y = ((d[0] + d[2]) / 2, (d[1] + d[3]) / 2) if k == 'cap' else (sum(p[0] for p in d) / len(d), sum(p[1] for p in d) / len(d))
    return round(x - OX, 2), round(y - OY, 2)


def gaps(items, codes=None):
    """{name: (gap mm, layer, nearest crystal net, required mm)} per non-crystal, non-exempt net; LED pads
    are reported as '<ref> <net>' whatever their net (they get LED_GAP, GND and unconnected pins included)."""
    sh = shapes(items, codes or {})
    pts = [p for n, L, k, d, r in sh if r == MCU and k == 'poly' for p in d]
    box = (min(x for x, _ in pts) - ESCAPE, min(y for _, y in pts) - ESCAPE,
           max(x for x, _ in pts) + ESCAPE, max(y for _, y in pts) + ESCAPE) if pts else (0, 0, 0, 0)
    xt = []
    for n, L, k, d, r in sh:
        if n not in CRYSTAL or r == MCU:
            continue
        xt += [(n, L, k, d, r)] if k == 'poly' else [(n, L, 'cap', (*piece, d[4]), r) for piece in _clip_out(d[:4], box)]
    best = {}
    for net, L, k, d, ref in sh:
        led = ref in LED_REFS                                  # every LED pad, whatever its net (GND included)
        if not led and (net in CRYSTAL or net in EXEMPT or not net or net.startswith('unconnected-') and 'unconnected-' not in EXEMPT):
            continue
        name = f'{ref} {net}' if led else net
        for xn, xl, xk, xd, _ in xt:
            if xl != L:
                continue
            g = gap((k, d), (xk, xd))
            if g < best.get(name, (99,))[0]:
                best[name] = (g, L, xn, limit(net, ref), (ref, _at(k, d)))
    return best


def failures(items, codes=None):
    return {n: v for n, v in gaps(items, codes).items() if v[0] < v[3]}


def lengths(items, codes=None):
    """Routed track length per crystal net (mm)."""
    out = dict.fromkeys(CRYSTAL, 0.0)
    for net, L, k, d, _ in shapes([i for i in items if isinstance(i, list) and i[0] == 'segment'], codes or {}):
        if net in out:
            out[net] += math.hypot(d[2] - d[0], d[3] - d[1])
    return out


def load(path):
    root = sexpr.parse(open(path, encoding='utf-8').read())
    codes = {_s(n[1]): _s(n[2]) for n in root if isinstance(n, list) and n[0] == 'net' and len(n) == 3}
    return [i for i in root if isinstance(i, list)], codes


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'node.kicad_pcb')
    radius = float(sys.argv[2]) if len(sys.argv) > 2 else 1.5
    if '--raw' in sys.argv:                          # audit view: no escape zone, unconnected pins included
        ESCAPE = -1e3; EXEMPT = ('GND', 'unconnected-')
    items, codes = load(path)
    res = sorted(gaps(items, codes).items(), key=lambda kv: kv[1][0])
    for net, (g, L, xn, need, (ref, at)) in res:
        if g < radius:
            print(f'{g:6.3f} mm  {L:6s}  {net:32s} need {need:.1f}  (nearest {xn}; {ref or "track/via"} centre {at}){"  FAIL" if g < need else ""}')
    ln = lengths(items, codes)
    print('crystal track lengths:', ', '.join(f'{n} {v:.2f}' for n, v in ln.items()), f'total {sum(ln.values()):.2f} mm')
    sys.exit(1 if failures(items, codes) else 0)
