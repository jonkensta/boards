#!/usr/bin/env python3
"""Write node.kicad_pcb: 48 x 48 mm, 4 layers (F.Cu signals, In1 GND, In2 +3V3, B.Cu GND pour +
5 V ring + long signal runs). One side-entry JST-XH link connector per edge (mouth 1.1 mm past
the edge). Floorplan rule: the RP2040 and its immediate support (decoupling, crystal, flash, LDO,
USB series R) fill the centre square between the connectors; the peripherals take the corners:
piezo NE (driven from U1's west edge, away from the crystal),
ToF sensor SE, pogo pads SW, vibration switch NW. M2 holes in the corners with nothing
but tracks within 3.7 mm of their centres (washer). See README.md (PCB section) for the plan.

Coordinates are board-local mm (origin top-left, y down). Escape rules that shaped this file
(0.2 mm track / 0.2 mm clearance / 0.6 mm via at 0.4 mm pitch): neighbouring pins that leave
in the same 45 deg direction must bend at points offset by >= 0.17 mm along the pin row
(the pin nearer the bend direction bends first) or >= 0.97 mm the other way; a via needs 0.6 mm
from any other track centre, so IOVDD pins only get a via when both neighbours are unrouted.
"""
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, 'boardtools')):
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from boardtools.pcbgen import Board, Netlist

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, '..', 'node.kicad_pcb')
W, H = 48.0, 48.0
b = Board(PCB, Netlist(os.path.join(HERE, 'node.net')), 'node.kicad_sch', W, H, copper_layers=4)
N = lambda ref, pin: b.net.node_net[(ref, pin)]     # net of a pin, from the schematic
B = 'B.Cu'
S, P = 0.2, 0.4                                       # signal / power track widths


def T(net, *pts, w=S, layer='F.Cu'):
    b.seg(net, w, *pts, layer=layer)


def V(net, x, y):
    b.via(net, x, y)


def pad_via(net, x, y, vx, vy, w=S):
    """Short stub from a pad centre to a via (the via may touch its own pad)."""
    T(net, (x, y), (vx, vy), w=w); V(net, vx, vy)




# ---- mounting holes -------------------------------------------------------------------------------
# M2 holes 3.5 mm in from each corner. Two rule areas each: the old 3.2 mm disc (no tracks, vias or
# pour) and a washer annulus 2.6..3.7 mm (no pads, vias or footprint courtyards; a 5 mm washer then
# keeps > 1.2 mm from any copper pad or part). The annulus leaves the hole's own footprint (courtyard
# r 2.45) outside the rule area, so the NPTH does not trip it.
HOLES = [(3.5, 3.5), (W - 3.5, 3.5), (3.5, H - 3.5), (W - 3.5, H - 3.5)]
WASHER = 3.7
for i, (hx, hy) in enumerate(HOLES):
    b.footprint(f'H{i+1}', hx, hy, ref_fab=True); b.keepout(hx, hy)
    b.keepout(hx, hy, WASHER, 32, 'washer clearance', r_in=2.6, pads=False, footprints=False, tracks=True)


def check_hole_clearance():
    """Fail generation if any pad or courtyard of a non-hole footprint comes within WASHER of a hole centre."""
    import math
    from boardtools import sexpr
    worst = (99, None)
    for fp in (it for it in b.items if it[0] == 'footprint'):
        at = sexpr.child(fp, 'at'); fx, fy = float(at[1]) - b.OX, float(at[2]) - b.OY
        r = math.radians(float(at[3]) if len(at) > 3 else 0)
        ref = next(p[2] for p in fp if isinstance(p, list) and p[0] == 'property' and p[1] == 'Reference').strip('"')
        if ref.startswith('H'):
            continue
        tf = lambda px, py: (fx + px * math.cos(r) + py * math.sin(r), fy - px * math.sin(r) + py * math.cos(r))
        shapes = []                       # (points, extra radius): pads as corner sets, courtyard outlines as segments
        for el in fp:
            if not isinstance(el, list):
                continue
            if el[0] == 'pad':
                pa, sz = sexpr.child(el, 'at'), sexpr.child(el, 'size')
                a = math.radians(float(pa[3]) if len(pa) > 3 else 0) - r
                hw, hh = float(sz[1]) / 2, float(sz[2]) / 2
                cx, cy = float(pa[1]), float(pa[2])
                pts = [tf(cx + dx * math.cos(a) + dy * math.sin(a), cy - dx * math.sin(a) + dy * math.cos(a))
                       for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
                shapes.append((f'{ref}.{el[1]}', pts + pts[:1]))
            elif el[0] in ('fp_line', 'fp_rect', 'fp_poly', 'fp_circle') and sexpr.child(el, 'layer')[1].strip('"') == 'F.CrtYd':
                if el[0] == 'fp_circle':
                    c, e = sexpr.child(el, 'center'), sexpr.child(el, 'end')
                    cr = math.dist((float(c[1]), float(c[2])), (float(e[1]), float(e[2])))
                    shapes.append((f'{ref} courtyard', [tf(float(c[1]) + cr * math.cos(t / 16 * math.pi), float(c[2]) + cr * math.sin(t / 16 * math.pi)) for t in range(33)]))
                elif el[0] == 'fp_rect':
                    s_, e = sexpr.child(el, 'start'), sexpr.child(el, 'end')
                    x0, y0, x1, y1 = float(s_[1]), float(s_[2]), float(e[1]), float(e[2])
                    shapes.append((f'{ref} courtyard', [tf(*p) for p in ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))]))
                elif el[0] == 'fp_line':
                    s_, e = sexpr.child(el, 'start'), sexpr.child(el, 'end')
                    shapes.append((f'{ref} courtyard', [tf(float(s_[1]), float(s_[2])), tf(float(e[1]), float(e[2]))]))
                else:
                    pts = [tf(float(p[1]), float(p[2])) for p in sexpr.child(el, 'pts')[1:] if p[0] == 'xy']
                    shapes.append((f'{ref} courtyard', pts + pts[:1]))
        for name, pts in shapes:
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                for hx, hy in HOLES:
                    dx, dy = x1 - x0, y1 - y0
                    t = max(0, min(1, ((hx - x0) * dx + (hy - y0) * dy) / (dx * dx + dy * dy or 1)))
                    d = math.dist((hx, hy), (x0 + t * dx, y0 + t * dy))
                    worst = min(worst, (d, name))
    assert worst[0] >= WASHER, f'{worst[1]} is {worst[0]:.2f} mm from a mounting-hole centre (< {WASHER})'
    return worst


J6_AT = (12.4, 35.9)          # pogo pads: courtyard margins to J3 / J4 courtyards and H3's 3.7 mm ring equalised (~0.57 mm)

# ---- placement ------------------------------------------------------------------------------
# side-entry JST XH (S3B): pins on a row DJ in from the edge, housing mouth facing out; pin 1 is the
# counter-clockwise-first pin (the footprint cannot be mirrored), see README
# Tiling rule: nodes are tiled by translation, so W (J4) must line up with a western neighbour's E (J2)
# and S (J3) with a southern neighbour's N (J1): one shared pin-row centre per axis, and both are the
# board centre lines.
DJ = 8.1                                                          # housing mouth 1.1 mm beyond the edge
LINK_EW_Y, LINK_NS_X, JP = H / 2, W / 2, 2.5                      # shared pin-row centres (board centre), XH pitch
J1 = b.footprint('J1', LINK_NS_X + JP, DJ, 180, ref_pos=(2.5, 5.5))       # N: mouth up, pins x 26.5 / 24 / 21.5
J2 = b.footprint('J2', W - DJ, LINK_EW_Y + JP, 90, ref_pos=(2.5, 5.5))    # E: mouth right, pins y 26.5 / 24 / 21.5
J3 = b.footprint('J3', LINK_NS_X - JP, H - DJ, 0, ref_pos=(2.5, 5.5))     # S: mouth down, pins x 21.5 / 24 / 26.5
J4 = b.footprint('J4', DJ, LINK_EW_Y - JP, 270, ref_pos=(2.5, 5.5))       # W: mouth left, pins y 21.5 / 24 / 26.5
# fail generation if the tiling alignment regresses: pin 2 of every link on its edge's centre line (1 um),
# and facing pin rows coincide as sets
assert abs(J4['2'][1] - J2['2'][1]) < 1e-3 and abs(J3['2'][0] - J1['2'][0]) < 1e-3, 'link connectors misaligned'
assert all(abs(v - c) < 1e-3 for v, c in ((J1['2'][0], W / 2), (J3['2'][0], W / 2), (J2['2'][1], H / 2), (J4['2'][1], H / 2))), 'link connectors not centred'
assert all(abs(a - b) < 1e-3 for a, b in zip(sorted(p[1] for p in J2.values()), sorted(p[1] for p in J4.values())))
assert all(abs(a - b) < 1e-3 for a, b in zip(sorted(p[0] for p in J1.values()), sorted(p[0] for p in J3.values())))

# U1 rot 180 in the board centre. Pads (centre / tip): north edge pins 15..28 at y 20.562 / 20.125, x 26.6 .. 21.4;
# east edge 1..14 at x 27.438 / 27.875, y 26.6 .. 21.4; west edge 29..42 at x 20.562 / 20.125, y 21.4 .. 26.6;
# south edge 43..56 at y 27.438 / 27.875, x 21.4 .. 26.6.
UX, UY = W / 2, H / 2
U1 = b.footprint('U1', UX, UY, 180, ref_fab=True)
NX = lambda pin: UX + 2.6 - 0.4 * (pin - 15)       # north edge pin x
EY = lambda pin: UY + 2.6 - 0.4 * (pin - 1)        # east edge pin y
WY = lambda pin: UY - 2.6 + 0.4 * (pin - 29)       # west edge pin y
SX = lambda pin: UX - 2.6 + 0.4 * (pin - 43)       # south edge pin x
TN, TE, TW, TS = UY - 3.875, UX + 3.875, UX - 3.875, UY + 3.875    # pad tips

# north: NW fan (26 RUN, 25 SWDIO, 24 SWCLK) with pin 23 (DVDD) and 22 (IOVDD) turning north into C14 / C5;
# crystal NE: XIN (20) up-right under Y1 into Y1.1, XOUT (21) up-right then north into R1 (>= 1 mm from 22 / 23 / C5)
C5 = b.footprint('C5', 23.3, 16.825, 90, ref_fab=True)          # IOVDD 22: 1 3V3 (23.3,17.6) 2 GND (23.3,16.05)
C14 = b.footprint('C14', 20.65, 17.6, 180, ref_fab=True)        # DVDD 23: 1 DVDD (21.425,17.6) 2 GND (19.875,17.6)
Y1 = b.footprint('Y1', 26.75, 16.0, 90, ref_fab=True)           # 1 XIN SE, 2 GND NE, 3 node NW, 4 GND SW
R1 = b.footprint('R1', 25.8, 13.0, 180, ref_fab=True)         # 2 XOUT west on the XOUT column, 1 node east
C1 = b.footprint('C1', 30.0, 18.0, 180, ref_fab=True)           # 2 XIN west, 1 GND east (low: >= 2 mm from D4)
C2 = b.footprint('C2', 28.05, 12.4, 90, ref_fab=True)           # vertical NE of R1: 2 node north, 1 GND south
R2 = b.footprint('R2', 18.5, 20.775, 90, ref_fab=True)          # RUN pull-up: 2 RUN (18.5,19.95) hanging below the RUN row, 1 3V3 (18.5,21.6)
# west edge: IOVDD 33 -> C6, IOVDD 42 -> C7
C6 = b.footprint('C6', 18.35, WY(33), 180, ref_fab=True)        # 1 3V3 (19.125) 2 GND (17.575)
C7 = b.footprint('C7', 18.35, WY(42), 180, ref_fab=True)
# south-west corner: ADC_AVDD 43 / VREG_VIN 44 -> C10 / C11, VREG_VOUT 45 -> C13 + C15 (0402)
C11 = b.footprint('C11', 18.95, 27.8, 180, ref_fab=True)
C10 = b.footprint('C10', 18.95, 28.84, 180, ref_fab=True)
C13 = b.footprint('C13', 21.3, 28.62, 180, ref_fab=True)
C15 = b.footprint('C15', 21.83, 30.0, 270, ref_fab=True)        # DVDD 100n below C13: 1 DVDD (21.83,29.52) top, 2 GND (21.83,30.48)
C9 = b.footprint('C9', 23.9, 31.7, 270, ref_fab=True)           # USB_VDD 48 + IOVDD 49 joined: 1 3V3 (23.9,30.925) top, 2 GND (23.9,32.475)
C8 = b.footprint('C8', 25.4, 32.3, 270, ref_fab=True)           # IOVDD 49, beside C9 on the same node: 1 3V3 (25.4,31.525) 2 GND (25.4,33.075)
R15 = b.footprint('R15', 20.2, 32.0, 0, ref_fab=True)           # 27R DM: 2 DM (21.025,32.0) east, 1 J6.1 (19.375,32.0)
R16 = b.footprint('R16', 20.2, 33.5, 0, ref_fab=True)           # 27R DP: 2 DP (21.025,33.5) east, 1 J6.3 (19.375,33.5)
# east edge: IOVDD 1 -> C3 below the corner, IOVDD 10 -> C4
C3 = b.footprint('C3', 29.6, 28.8, 0, ref_fab=True)             # 1 3V3 (28.825,28.8) 2 GND (30.375,28.8)
C4 = b.footprint('C4', 29.7, EY(10), 0, ref_fab=True)           # 1 3V3 (28.925,23.0) 2 GND (30.475,23.0)
# flash SE of U1, rot 180: west column (N->S) 5 SD0, 6 SCLK, 7 SD3, 8 VCC; east column 4 GND, 3 SD2, 2 SD1, 1 SS
U2 = b.footprint('U2', 34.6, 33.5, 180, ref_pos=(0, 3.8))
C16 = b.footprint('C16', 28.4, 35.5, 180, ref_fab=True)         # flash VCC: 1 3V3 (29.175,35.5) east, 2 GND (27.625,35.5)
R3 = b.footprint('R3', 33.6, 37.3, 180, ref_fab=True)          # QSPI_SS pull-up: 2 SS (32.775) west, 1 3V3 (34.425)
# NW of the centre square: LDO (5 V from J4.1, 3V3 into the plane)
U4 = b.footprint('U4', 15.5, 13.5, 0, ref_pos=(0, -2.6))        # 1 VIN (14.36,12.55) 2 GND 3 CE (14.36,14.45) 5 VOUT (16.64,12.55)
C17 = b.footprint('C17', 12.2, 13.5, 90, ref_fab=True)          # 10u in: 1 +5V (12.2,14.275) south, 2 GND north
C18 = b.footprint('C18', 18.4, 13.5, 270, ref_fab=True)         # 1 3V3 (18.4,12.725) north, 2 GND south
C12 = b.footprint('C12', 15.5, 16.2, 0, ref_fab=True)
# NE of the centre square: the LED, D4 (DNP) chained below it; D1 drops J1.1's 5 V for them from the NE corner strip
D2 = b.footprint('D2', 34.0, 14.2, 90, ref_fab=True)            # 4 VDD TL, 3 DIN TR, 2 GND BR, 1 DOUT BL
D4 = b.footprint('D4', 31.4, 14.2, 90, ref_fab=True)            # west of D2: DIN (31.35,13.285) TR, VDD (30.25,13.285) TL, GND (31.35,15.115) BR
C19 = b.footprint('C19', 34.8, 11.8, 0, ref_fab=True)           # right above D2: 1 LED_VDD west (over D2's VDD pin), 2 GND east + via
D1 = b.footprint('D1', 35.0, 5.0, 180, ref_fab=True)            # 2 A +5V (33.35,5.0) west, 1 K LED_VDD (36.65,5.0) east
# links: 100 R series + 4k7 pull-up. R7 / R8 (N) by J1, R9 / R10 (E) in the pocket east of U1 with LE going on
# to J2.2 on B.Cu, R11 / R12 (S) above J3, R13 / R14 (W) by J4
R7 = b.footprint('R7', 31.2, 11.1, 180, ref_fab=True)          # N: 1 LN (32.025,11.1) east, 2 J1 (30.375,11.1) -> west under R1/C2 -> J1.2
R8 = b.footprint('R8', 31.2, 9.05, 0, ref_fab=True)             # N pull-up: 2 LN east, 1 3V3 west
R9 = b.footprint('R9', 34.4, 26.8, 0, ref_fab=True)             # E: 1 LE (33.575,26.8) on the LE row, 2 J2 (35.225,26.8) -> via -> B.Cu
R10 = b.footprint('R10', 34.4, 28.3, 180, ref_fab=True)         # E pull-up: 2 LE (33.575,28.3) 1 3V3 (35.225,28.3)
R11 = b.footprint('R11', 23.0, 35.6, 270, ref_fab=True)         # S: 1 LINK_S (23.0,34.775) north, 2 J3 (23.0,36.425)
R12 = b.footprint('R12', 24.6, 35.6, 90, ref_fab=True)          # S pull-up: 2 LINK_S (24.6,34.775) north, 1 3V3 south
R13 = b.footprint('R13', 13.2, 24.0, 180, ref_fab=True)         # W: 1 LW (14.025,24.0) east, 2 J4 (12.375,24.0) -> J4.2
R14 = b.footprint('R14', 16.1, 26.025, 90, ref_fab=True)         # W pull-up: 2 LW (16.1,25.2) on the LW run, 1 3V3 (16.1,26.85)
# I2C pull-ups just north of U3 (SENS_INT's R6 sits by SW1)
R4 = b.footprint('R4', 43.3, 30.9, 0, ref_fab=True)             # SDA: 1 3V3 (42.475) 2 SDA (44.125)
R5 = b.footprint('R5', 46.3, 30.9, 180, ref_fab=True)           # SCL: 2 SCL (45.475) 1 3V3 (47.125)
R6 = b.footprint('R6', 17.0, 7.5, 270, ref_fab=True)            # SENS_INT: 1 3V3 north, 2 INT south
# ---- corners --------------------------------------------------------------------------------
BZ1 = b.footprint('BZ1', 42.5, 12.0, 0, ref_fab=True)              # NE: piezo, 1 west, 2 east
R17 = b.footprint('R17', 38.0, 17.65, 0, ref_fab=True)          # BUZZ_A: 1 west, 2 east -> BZ1.1 west pad
R18 = b.footprint('R18', 41.4, 17.65, 0, ref_fab=True)          # BUZZ_B: 1 west, 2 east -> BZ1.2 east pad
SW1 = b.footprint('SW1', 11.0, 7.5, 0, ref_fab=True, val_pos=(0, -3.6))   # NW: vibration switch (vib variant)
C22 = b.footprint('C22', 15.5, 7.5, 90, ref_fab=True)           # debounce, on the INT run from SW1.2 to R6
U3 = b.footprint('U3', 43.8, 33.8, 180, ref_fab=True)         # SE: ToF sensor. N row y 33.0: 7 INT 42.2, 8 NC, 9 SDA 43.8, 10 SCL 44.6, 11 3V3 45.4; W 6 GND, 5 XSHUT (42.2,34.6); S 4..2 GND, 1 3V3 (45.4,34.6); E 12 GND
C20 = b.footprint('C20', 47.0, 35.8, 270, ref_fab=True)         # 1 3V3 (47.0,35.025) north, 2 GND south
C21 = b.footprint('C21', 45.5, 36.8, 270, ref_fab=True)         # 1 3V3 (45.5,36.025) north, 2 GND south
J6 = b.footprint('J6', J6_AT[0], J6_AT[1], 90, ref_pos=(0, -7.0))   # SW: pogo pads (no paste), centred between J3, J4 and H3

if __name__ == '__main__' and '--pads' in sys.argv:
    for ref in sys.argv[2:] or ('U1', 'U2', 'Y1', 'J6', 'U3', 'U4', 'D2', 'D4', 'D1'):
        print(ref, globals()[ref])
    sys.exit()

# ---- nets -----------------------------------------------------------------------------------
G, V3, V5, DVDD = 'GND', '+3V3', '+5V', N('U1', '45')
XIN, XOUT, XNODE = N('U1', '20'), N('U1', '21'), N('Y1', '3')
RUN, SWDIO, SWCLK = N('U1', '26'), N('U1', '25'), N('U1', '24')
DM, DP = N('U1', '46'), N('U1', '47')
SD3, SCLK, SD0, SD2, SD1, SS = (N('U1', p) for p in ('51', '52', '53', '54', '55', '56'))
LN, LE, LS, LW, LDIN = (N('U1', p) for p in ('2', '3', '4', '5', '6'))
XSHUT, INT, SDA, SCL = N('U1', '7'), N('U1', '8'), N('U1', '13'), N('U1', '14')
BA, BB = N('U1', '29'), N('U1', '30')
LVDD, J6DM, J6DP, J3S, DOUT = N('D2', '4'), N('R15', '1'), N('R16', '1'), N('R11', '2'), N('D2', '1')

PLACE_ONLY = '--place' in sys.argv

def route_north():
    """U1 north edge: exposed-pad vias, TESTEN, the NW fan (RUN / SWDIO / SWCLK rows to B.Cu lanes, DVDD 23 and
    IOVDD 22 turning into C14 / C5) and the crystal NE of the pins.
    Crystal: XIN 45 deg up-right under Y1 into Y1.1, XOUT up-right then north into R1, only GND around Y1 / C1 / C2 / R1."""
    for x in (UX - 0.6, UX + 0.6):
        for y in (UY - 0.6, UY + 0.6):
            V(G, x, y)
    T(G, (NX(19), UY - 3.0), (NX(19), UY - 1.4))                                   # 19 TESTEN inward onto the exposed pad
    # NW fan: pin k bends at y 19.9 - 0.2 k (26 = 0 .. 22 = 4), then 45 deg up-left
    for k, (pin, net) in enumerate(((26, RUN), (25, SWDIO), (24, SWCLK))):
        x, by, ry = NX(pin), TN - 0.225 - 0.2 * k, (19.7, 19.05, 18.4)[k]
        T(net, (x, TN), (x, by), (x - (by - ry), ry))
    T(RUN, (NX(26) - 0.2, 19.7), (LANE_RUN_V, 19.7)); V(RUN, LANE_RUN_V, 19.7)
    T(SWDIO, (NX(25) - 0.65, 19.05), (LANE_SWDIO_V, 19.05)); V(SWDIO, LANE_SWDIO_V, 19.05)
    T(SWCLK, (NX(24) - 1.1, 18.4), (LANE_SWCLK_V, 18.4)); V(SWCLK, LANE_SWCLK_V, 18.4)
    T(V3, R2['1'], (19.125, 22.3), C6['1'])                                         # R2 pull-up onto C6's 3V3 pad
    T(DVDD, (NX(23), TN), (NX(23), TN - 0.825), (NX(23) - (TN - 0.825 - C14['1'][1]), C14['1'][1]), C14['1'])                           # 23 DVDD -> C14.1
    pad_via(DVDD, *C14['1'], C14['1'][0], 16.7); pad_via(G, *C14['2'], C14['2'][0], 16.7)
    T(V3, (NX(22), TN), (NX(22), TN - 1.025), (23.3, 18.6), C5['1'])                # 22 IOVDD -> C5.1
    pad_via(G, *C5['2'], 23.3, 15.2); T(V3, C5['1'], (22.7, 17.2), (22.4, 16.9)); V(V3, 22.4, 16.9)
    # crystal: XIN up-right under Y1 into Y1.1 (SE pad) and on to C1; XOUT up-right then north into R1.2; node R1.1 -> Y1.3 + C2
    xr = Y1['1'][1] + 1.2                                       # XIN passes below Y1's SW (GND) pad, then up into Y1.1
    T(XIN, (NX(20), TN), (NX(20), TN - 0.225), (NX(20) + TN - 0.225 - xr, xr), (Y1['1'][0], xr), Y1['1']); T(XIN, (Y1['1'][0], xr), C1['2'])
    # XOUT follows XIN 45 deg up-right before turning north, so it leaves IOVDD 22 / DVDD 23 (and C5) >= 1 mm behind
    T(XOUT, (NX(21), TN), (NX(21), TN - 0.425), (R1['2'][0], TN - 0.425 - (R1['2'][0] - NX(21))), R1['2'])
    T(XNODE, R1['1'], Y1['3']); T(XNODE, R1['1'], C2['2'])
    T(G, Y1['4'], Y1['2'])                                     # Y1's GND pads, C1 / C2 GND: into the F.Cu guard pour (route_guard)
    T(N('R18', '2'), R18['2'], (BZ1['2'][0] - 0.8, R18['2'][1]), (BZ1['2'][0], R18['2'][1] - 0.8), BZ1['2'])
    T(N('R17', '2'), R17['2'], (BZ1['1'][0] + 0.475, R17['2'][1] - 0.35), (BZ1['1'][0] + 0.475, BZ1['1'][1]))


def route_south():
    """U1 south edge: 43+44 -> C11 / C10, 45 -> C13 + C15, USB straight down to R15 / R16, 48+49 -> C9 + C8,
    50 -> DVDD via, QSPI fanned SE onto rows: SD0 / SCLK / SD3 into the flash's west column, SS / SD1 / SD2
    over its top and down the east side."""
    T(V3, (SX(43), TS + 0.025), (SX(44), TS + 0.025)); T(V3, (SX(43), TS + 0.025), (19.8, TS + 0.025), C11['1']); T(V3, C11['1'], C7['1'])
    T(V3, C11['1'], C10['1'])
    T(G, C11['2'], (17.75, 28.32), C10['2']); V(G, 17.75, 28.32)
    T(DVDD, (SX(45), TS), (SX(45), 28.3), C13['1']); T(DVDD, C13['1'], C15['1'])
    T(DVDD, C15['1'], (21.1, 29.75)); V(DVDD, 21.1, 29.75)
    pad_via(G, *C13['2'], 20.2, 30.3); T(G, C15['2'], (21.3, 30.48), (20.2, 30.3))
    T(DM, (SX(46), TS), (SX(46), 31.6), (SX(46) - 0.4, 32.0), R15['2'])
    T(DP, (SX(47), TS), (SX(47), 33.1), (SX(47) - 0.4, 33.5), R16['2'])
    T(V3, (SX(48), TS + 0.025), (SX(49), TS + 0.025)); T(V3, (23.6, TS + 0.025), (23.6, 30.625), C9['1'])
    T(V3, C9['1'], C8['1']); T(G, C9['2'], C8['2']); pad_via(G, *C9['2'], 23.9, 33.4); pad_via(V3, *C8['1'], 26.2, 31.8); pad_via(G, *C8['2'], 26.1, 33.6)
    T(DVDD, (SX(50), TS), (SX(50), 29.9)); V(DVDD, SX(50), 29.9)
    # QSPI: pin k (56 = 0 .. 51 = 5) bends at y 28.1 + 0.2 k, 45 deg down-right, then east on its row
    rows = {SS: 29.7, SD1: 30.3, SD2: 30.9, SD0: U2['5'][1], SCLK: U2['6'][1], SD3: U2['7'][1]}
    for k, (pin, net) in enumerate(((56, SS), (55, SD1), (54, SD2), (53, SD0), (52, SCLK), (51, SD3))):
        x, by = SX(pin), 28.1 + 0.2 * k
        ry = rows[net]
        T(net, (x, TS), (x, by), (x + ry - by, ry))
    T(SD0, (SX(53) + rows[SD0] - 28.7, rows[SD0]), U2['5']); T(SCLK, (SX(52) + rows[SCLK] - 28.9, rows[SCLK]), U2['6'])
    T(SD3, (SX(51) + rows[SD3] - 29.1, rows[SD3]), U2['7'])
    for net, pin, xe in ((SD2, '3', 39.6), (SD1, '2', 40.2), (SS, '1', 40.8)):
        x0 = SX({SS: 56, SD1: 55, SD2: 54}[net]) + rows[net] - (28.1 + 0.2 * {SS: 0, SD1: 1, SD2: 2}[net])
        T(net, (x0, rows[net]), (xe - 0.6, rows[net]), (xe, rows[net] + 0.6), (xe, U2[pin][1]), U2[pin])
    pad_via(G, *U2['4'], U2['4'][0] - 1.6, U2['4'][1])
    T(V3, U2['8'], (U2['8'][0] - 0.5, C16['1'][1]), C16['1']); pad_via(V3, *C16['1'], C16['1'][0], C16['1'][1] - 0.8); pad_via(G, *C16['2'], C16['2'][0], C16['2'][1] - 0.8)


def route_east():
    """U1 east edge. SCL / SDA (top) and INT / XSHUT (below IOVDD 10's cap C4) run east as a bundle and turn
    south just west of J2 into vias for the B.Cu run to U3. LED / links spread onto 0.65 mm rows with
    staggered vias: LW / LS go west under U1 on B.Cu, LN and LED_DIN north on B.Cu, LE through R9 to J2.2.
    IOVDD 1 drops into C3 below the corner."""
    # IOVDD 10 -> plane via -> C4
    T(V3, (TE, EY(10)), C4['1']); V(V3, 28.5, EY(10)); pad_via(G, *C4['2'], 31.2, 22.3)
    # the sensor bundle: rows (y) east of x 33.6, columns (x) turning south
    BROW = {SCL: 20.8, SDA: 21.45, INT: 22.1, XSHUT: 22.75}
    BCOL = {XSHUT: 36.6, INT: 37.25, SDA: 37.9, SCL: 38.55}
    BVIA = {XSHUT: 28.9, INT: 28.1, SDA: 28.9, SCL: 28.1}
    T(SCL, (TE, EY(14)), (28.3, EY(14)), (28.9, BROW[SCL]))
    T(SDA, (TE, EY(13)), (28.6, EY(13)), (28.95, BROW[SDA]))
    T(INT, (TE, EY(8)), (32.0, EY(8)), (32.0 + EY(8) - BROW[INT], BROW[INT]))
    T(XSHUT, (TE, EY(7)), (32.6, EY(7)), (32.6 + EY(7) - BROW[XSHUT], BROW[XSHUT]))
    for net, x0 in ((SCL, 28.9), (SDA, 28.95), (INT, 32.0 + EY(8) - BROW[INT]), (XSHUT, 32.6 + EY(7) - BROW[XSHUT])):
        y, cx = BROW[net], BCOL[net]
        T(net, (x0, y), (cx - 0.6, y), (cx, y + 0.6), (cx, BVIA[net])); V(net, cx, BVIA[net])
    # LED + links: SE spread onto rows 0.65 apart; vias staggered
    ROW = {LDIN: 25.1, LW: 25.75, LS: 26.4, LE: 27.05, LN: 27.7}   # spread rows; every row passing a via clears it by 0.65
    for k, (pin, net) in enumerate(((2, LN), (3, LE), (4, LS), (5, LW), (6, LDIN))):
        bx = 28.3 + 0.17 * k
        y0 = EY(pin); d = ROW[net] - y0
        T(net, (TE, y0), (bx, y0), (bx + d, ROW[net]))
    VIA_X = {LW: 30.3, LS: 31.2, LDIN: 32.9}
    VIA_LN = (31.9, ROW[LN])                                  # LINK_N goes north on B.Cu from here (route_northeast)
    for net in (LW, LS, LDIN):
        x0 = 28.3 + 0.17 * {LN: 0, LE: 1, LS: 2, LW: 3, LDIN: 4}[net] + ROW[net] - EY({LN: 2, LS: 4, LW: 5, LDIN: 6}[net])
        T(net, (x0, ROW[net]), (VIA_X[net], ROW[net])); V(net, VIA_X[net], ROW[net])
    x0 = 28.3 + 0.17 + ROW[LE] - EY(3)
    T(LE, (x0, ROW[LE]), (32.3, ROW[LE]), (32.55, R9['1'][1]), R9['1']); T(LE, R9['1'], R10['2'])
    pad_via(V3, *R10['1'], R10['1'][0] + 0.75, R10['1'][1])
    pad_via(N('R9', '2'), *R9['2'], R9['2'][0] + 0.75, R9['2'][1])
    x0 = 28.3 + ROW[LN] - EY(2)
    T(LN, (x0, ROW[LN]), (VIA_LN[0], ROW[LN])); V(LN, *VIA_LN)
    # IOVDD 1 -> C3 (below the corner, north of the QSPI rows)
    T(V3, (TE, EY(1)), (28.0, EY(1)), (28.0, 28.35), C3['1']); V(V3, 28.0, 27.6); pad_via(G, *C3['2'], 31.2, C3['2'][1])


def route_west():
    """West side: IOVDD 33 / 42 caps with plane vias, LINK_W surfacing from under U1 and running to R13 / J4.2,
    DVDD from C14's via down the west side on B.Cu to C13 / C15 and pin 50, the SWD lanes to the pogo pads."""
    T(V3, (TW, WY(33)), C6['1']); T(V3, (TW, WY(42)), C7['1'])
    pad_via(G, *C6['2'], C6['2'][0], 22.2); pad_via(G, *C7['2'], C7['2'][0], 27.45)
    V(V3, 19.45, 22.35); pad_via(V3, *C7['1'], 19.45, 27.3)
    # LINK_W: B.Cu under U1 from the east field, up at (19.55, 25.75), F.Cu west through R13 to J4.2; R14 hangs off the run
    T(LW, (30.3, 25.75), (20.1, 25.75), (19.55, 25.2), layer=B); V(LW, 19.55, 25.2)
    T(LW, (19.55, 25.2), R14['2'], (15.0, 25.2), (R13['1'][0] + 0.2, R13['1'][1] + 0.2), R13['1'])
    T(N('R13', '2'), R13['2'], J4['2']); pad_via(V3, *R14['1'], R14['1'][0], R14['1'][1] + 0.8)
    # DVDD: C14 via -> B.Cu down x 18.8 -> C13 / C15 via -> pin 50 via
    T(DVDD, (C14['1'][0], 16.7), (18.8, 19.725), (18.8, 29.6), (21.1, 29.6), (21.1, 29.75), layer=B)
    T(DVDD, (21.1, 29.75), (23.5, 29.9), (SX(50), 29.9), layer=B)
    # SWD lanes (B.Cu) down to vias inside the J6 even-row pads
    for net, lx, pad in ((SWDIO, LANE_SWDIO_V, '2'), (SWCLK, LANE_SWCLK_V, '4'), (RUN, LANE_RUN_V, '6')):
        y0 = {SWDIO: 19.05, SWCLK: 18.4, RUN: 19.7}[net]
        px = J6[pad][0]
        vy = J6[pad][1] - 0.575                                                  # via in the pad's north half
        T(net, (lx, y0), (lx, vy - 1.2 - abs(px - lx)), (px, vy - 1.2), (px, vy), layer=B); V(net, px, vy)


def route_southwest():
    """USB from R15 / R16 down past J6.8 and west between the pogo rows to the odd-row pads J6.1 / J6.3; LINK_S to
    R11 / R12 and J3.2; QSPI_SS (BOOT) from the flash to J6.8 on B.Cu."""
    # the pair runs 0.6 mm apart (0.4 mm gap): down just east of J6.8, west along the 1.9 mm gap between the rows
    xa, ra = J6['8'][0] + 1.3, J6['8'][1] + 2.225
    T(J6DM, R15['1'], (xa, R15['1'][1]), (xa, ra - 0.6), (xa - 0.6, ra), (J6['1'][0] + 0.6, ra), (J6['1'][0], ra + 0.6), J6['1'])
    T(J6DP, R16['1'], (xa + 0.6, R16['1'][1]), (xa + 0.6, ra), (xa, ra + 0.6), (J6['3'][0] + 0.6, ra + 0.6), (J6['3'][0], ra + 1.2), J6['3'])
    T(LS, (31.2, 26.4), (25.0, 26.4), (25.0, 34.3), (24.9, 34.4), layer=B); V(LS, 24.9, 34.4)
    T(LS, (24.9, 34.4), R12['2']); T(LS, R12['2'], R11['1'])
    T(J3S, R11['2'], (23.0, 38.0), (J3['2'][0], 38.9), J3['2'])
    pad_via(V3, *R12['1'], R12['1'][0] + 0.8, R12['1'][1])
    V(SS, 32.0, 29.1); T(SS, (32.0, 29.1), (32.0, 29.7))
    sv = (J6['8'][0], J6['8'][1] + 0.9)                                          # via in J6.8's south half
    T(SS, (32.0, 29.1), (32.0, 37.3), (sv[0] + 37.3 - sv[1], 37.3), sv, layer=B); V(SS, 32.0, 37.3); V(SS, *sv)
    T(SS, (32.0, 37.3), R3['2']); pad_via(V3, *R3['1'], R3['1'][0] + 0.8, R3['1'][1])
    pad_via(G, *J6['5'], J6['5'][0], J6['5'][1] + 1.175, w=P)


def route_southeast():
    """Sensor lines: from the bundle vias one short B.Cu hop east under the QSPI columns (rows y 28.6 .. 30.55), up
    into U3 beside the east edge; I2C pull-ups between U3 and J2; U3 power and ground; LINK_E to J2.2."""
    T(SCL, (38.55, 28.1), (39.05, 28.6), (44.7, 28.6), (45.3, 29.2), (45.3, 29.9), layer=B); V(SCL, 45.3, 29.9)
    T(SDA, (37.9, 28.9), (38.25, 29.25), (43.95, 29.25), (44.3, 29.6), (44.3, 29.9), layer=B); V(SDA, 44.3, 29.9)
    T(INT, (37.25, 28.1), (37.25, 29.9), (41.4, 29.9), (41.4, 32.3), layer=B); V(INT, 41.4, 32.3)
    T(XSHUT, (36.6, 28.9), (36.6, 30.55), (40.75, 30.55), (40.75, 35.9), (41.6, 35.9), layer=B); V(XSHUT, 41.6, 35.9)
    T(SCL, (45.3, 29.9), R5['2'], (44.6, 31.775), U3['10'])
    T(SDA, (44.3, 29.9), R4['2'], (43.8, 31.4), U3['9'])
    T(INT, (41.4, 32.3), (41.9, 32.3), (42.2, 32.6), U3['7']); T(XSHUT, (41.6, 35.9), U3['5'])
    pad_via(V3, *R4['1'], R4['1'][0], 30.1)
    T(V3, R5['1'], (47.1, 32.6), (45.7, 32.6), U3['11']); T(V3, U3['1'], (45.4, 35.4), C21['1'], C20['1'])
    T(V3, U3['11'], (46.05, 33.0), (46.05, 34.6), U3['1']); T(V3, (46.05, 34.6), C20['1']); pad_via(V3, *C21['1'], 44.7, 36.2)
    T(G, U3['6'], U3['12']); T(G, U3['2'], (U3['2'][0], 33.8)); T(G, U3['3'], (U3['3'][0], 33.8)); T(G, U3['4'], (U3['4'][0], 33.8))
    pad_via(G, *U3['3'], 43.8, 35.6); T(G, C21['2'], C20['2']); pad_via(G, *C21['2'], 45.5, 38.4)
    T(N('R9', '2'), (R9['2'][0] + 0.75, R9['2'][1]), (37.2, 25.6), (37.2, 24.0), J2['2'], layer=B)


def route_northeast():
    """LED cluster and its supply (D1 from J1.1), LINK_N up the west side of the LEDs to R7 / R8 and J1.2, LED_DIN up
    their east side, INT further east and then west under J1 to SW1."""
    T(LN, (31.9, 27.7), (31.9, 12.0), layer=B); V(LN, 31.9, 12.0); T(LN, (31.9, 12.0), R7['1'], (R7['1'][0], R8['2'][1]), R8['2'])
    T(N('R7', '2'), R7['2'], (R7['2'][0] - (R7['2'][1] - LINK_N_Y), LINK_N_Y), (J1['2'][0] + 0.8, LINK_N_Y), (J1['2'][0], LINK_N_Y - 0.8), J1['2'])
    pad_via(V3, *R8['1'], R8['1'][0] - 0.8, R8['1'][1])
    T(LDIN, (32.9, 25.1), (35.3, 22.7), (35.3, 13.485), layer=B); V(LDIN, 35.3, 13.485); T(LDIN, (35.3, 13.485), D2['3'])
    T(DOUT, D2['1'], D4['3'])
    T(LVDD, D1['1'], (D1['1'][0], 12.6), (D4['4'][0], 12.6), D4['4']); T(LVDD, (D2['4'][0], 12.6), D2['4'])
    T(LVDD, C19['1'], (C19['1'][0], 12.6)); pad_via(G, *C19['2'], C19['2'][0], C19['2'][1] - 0.8)     # C19 over D2's VDD pin
    pad_via(G, *D2['2'], D2['2'][0], D2['2'][1] + 0.8); pad_via(G, *D4['2'], D4['2'][0] - 0.75, D4['2'][1] + 0.85)
    T(V5, J1['1'], (27.9, 6.7), (27.9, 5.0), D1['2'], w=P)
    # INT north to SW1 (vib switch, NW corner), west under J1
    V(INT, 36.0, 22.1); T(INT, (36.0, 22.1), (36.2, 21.9), (36.2, 10.4), (SW1['2'][0], 10.4), SW1['2'], layer=B)
    T(INT, SW1['2'], (SW1['2'][0] + 0.8, R6['2'][1]), R6['2']); pad_via(V3, *R6['1'], R6['1'][0], 5.8)
    ci, cg = (C22['1'], C22['2']) if C22['1'][1] > C22['2'][1] else (C22['2'], C22['1'])
    T(INT, (ci[0], R6['2'][1]), ci); pad_via(G, *cg, cg[0], 5.8)


def route_northwest():
    """LDO: 5 V from J4.1 up the west edge on F.Cu, 3V3 into the plane; SW1 ground."""
    T(V5, J4['1'], (8.8, 20.8), (8.8, 16.0), (C17['1'][0], C17['1'][1] + 0.6), C17['1'], w=P)
    T(V5, C17['1'], (13.35, U4['3'][1]), U4['3'], w=P); T(V5, (13.35, U4['3'][1]), (13.35, U4['1'][1]), U4['1'], w=0.25)
    pad_via(G, *C17['2'], C17['2'][0] - 0.8, C17['2'][1]); pad_via(G, *U4['2'], U4['2'][0] + 0.9, U4['2'][1], w=S)
    T(V3, U4['5'], (C18['1'][0], U4['5'][1]), C18['1'], w=P); pad_via(V3, *C18['1'], C18['1'][0] + 0.8, C18['1'][1]); pad_via(G, *C18['2'], C18['2'][0] + 0.8, C18['2'][1])
    pad_via(V3, *C12['1'], C12['1'][0] - 0.8, C12['1'][1]); pad_via(G, *C12['2'], C12['2'][0] + 0.8, C12['2'][1])


def route_buzzer():
    """Piezo pair from U1's NW corner (29 BUZZ_A / 30 BUZZ_B = GPIO18/19, PWM slice 1), far from the crystal: vias just
    west of the pins, B.Cu under U1's body (rows y BUZ_ROW) and NE under the SCL / SDA rows, up east of C1 onto F.Cu
    rows (BUZZ_A north, BUZZ_B south) to R17 / R18 below BZ1."""
    ya, yb = BUZ_ROW
    va, vb = (19.65, 20.55), (19.6, 21.55)                                      # escape vias (between R2 / C6 and the pads)
    fa, fb = (30.4, 19.6), (31.2, 20.2)                                          # surfacing vias east of C1, west of LINK_N's lane
    T(BA, (UX - 3.5, WY(29)), va); V(BA, *va)
    T(BB, (TW, WY(30)), (vb[0] + 0.25, WY(30)), vb); V(BB, *vb)
    T(BA, va, (va[0] + ya - va[1], ya), (fa[0] - (ya - fa[1]), ya), fa, layer=B); V(BA, *fa)
    T(BB, vb, (vb[0] + yb - vb[1], yb), (fb[0] - (yb - fb[1]), yb), fb, layer=B); V(BB, *fb)
    T(BA, fa, (R17['1'][0] - 0.8, fa[1]), (R17['1'][0], fa[1] - 0.8), R17['1'])
    T(BB, fb, (R18['1'][0] - 1.0, fb[1]), (R18['1'][0], fb[1] - 1.0), R18['1'])


def route_guard():
    """F.Cu GND guard pour over the crystal cluster (Y1, C1, C2, R1, XIN / XOUT), stitched to In1 around its edge; C1 / C2
    GND pads get their own short vias. The outline (GUARD) is notched around R7 and D4 so that it encloses no copper but
    GND and the crystal nets (asserted, >= GUARD_CLR from the outline)."""
    import math
    from xtal_check import shapes, gap, _inside, _pp, CRYSTAL
    b.zone('GND', 'crystal guard', 0, 0, 1, 1, layer='F.Cu', priority=1)
    z = b.items[-1]
    z[z.index(['connect_pads', ['clearance', '0.3']])] = ['connect_pads', 'yes', ['clearance', '0.3']]   # solid onto GND pads
    poly = next(e for e in z if isinstance(e, list) and e[0] == 'polygon')
    poly[1] = ['pts'] + [['xy', f'{X:g}', f'{Y:g}'] for X, Y in (b.P(x, y) for x, y in GUARD)]
    pad_via(G, *C1['1'], C1['1'][0], C1['1'][1] + 0.85); pad_via(G, *C2['1'], C2['1'][0] + 0.8, C2['1'][1] + 0.1)
    pad_via(G, *Y1['2'], Y1['2'][0] + 0.9, Y1['2'][1])
    codes = {str(c): n for n, c in b.net.codes.items()}
    outline = [b.P(x, y) for x, y in GUARD]
    allsh = shapes([i for i in b.items if i is not z], codes)
    foreign = [(n, k, d, r) for n, L, k, d, r in allsh if L == 'F.Cu' and n not in ('GND',) + CRYSTAL]
    bad = [(n, r, round(gap((k, d), ('poly', outline)), 3)) for n, k, d, r in foreign if gap((k, d), ('poly', outline)) < GUARD_CLR]
    assert not bad, f'crystal guard outline encloses or touches foreign copper: {bad}'
    # stitching: stations every 0.25 mm along the outline; at each, the shallowest inward inset (0.2 .. 1.3 mm) where a
    # via fits; a via is placed when no GND via is within 1.1 mm, so the chain closes at <= STITCH mm wherever copper allows
    sh = [(n, k, d) for n, L, k, d, r in shapes([i for i in b.items if i[0] != 'zone'], codes)]   # vias are through: all layers
    vias = [(d[:2], n) for n, L, k, d, r in allsh if L == 'F.Cu' and k == 'cap' and d[:2] == d[2:4] and d[4] >= 0.3]
    edge = lambda X, Y: min(_pp(X, Y, *p, *q) for p, q in zip(outline, outline[1:] + outline[:1]))
    placed = []
    for (ax, ay), (bx, by) in zip(GUARD, GUARD[1:] + GUARD[:1]):
        L_ = math.dist((ax, ay), (bx, by)); nx, ny = -(by - ay) / L_, (bx - ax) / L_          # inward normal (clockwise, y down)
        for i in range(math.ceil(L_ / 0.25)):
            sx, sy = ax + (bx - ax) * i * 0.25 / L_, ay + (by - ay) * i * 0.25 / L_
            for ins in (0.2, 0.3, 0.4, 0.55, 0.7, 0.85, 1.0, 1.15, 1.3):
                X, Y = b.P(sx + nx * ins, sy + ny * ins)
                if not _inside(X, Y, outline) or edge(X, Y) < 0.199:
                    continue
                me = ('cap', (X, Y, X, Y, 0.3))
                if any(math.dist((X, Y), v) < 0.9 for v, _ in vias) or any(math.dist((X, Y), v) < 0.9 for v in placed):
                    continue
                if all(n == 'GND' or gap(me, (k, d)) >= 0.21 for n, k, d in sh):
                    if not any(math.dist((X, Y), v) < 1.1 for v in [v for v, n in vias if n == 'GND'] + placed):
                        x_, y_ = X - b.OX, Y - b.OY
                        V(G, x_, y_); placed.append((X, Y))
                    break
    return len(placed)


LANE_SWDIO_V, LANE_SWCLK_V, LANE_RUN_V = 10.0, 10.7, 11.4
BUZ_ROW = (21.8, 22.4)                             # BUZZ_A / BUZZ_B B.Cu rows under U1 (north of the exposed-pad vias)
GUARD = [(24.12, 10.75), (29.4, 10.75), (29.4, 11.85), (30.2, 11.85), (30.2, 15.8), (31.5, 15.8), (31.5, 19.0),
         (29.6, 19.0), (29.6, 19.45), (24.12, 19.45)]    # crystal guard pour outline (clockwise), notched around R7 and D4
GUARD_CLR, STITCH = 0.2, 2.0                      # foreign copper to the guard outline; stitching pitch
LINK_N_Y = 9.9                                     # R7 -> J1.2 row, >= 1 mm north of C2
if not PLACE_ONLY:
    route_north()
    route_south()
    route_east()
    route_west()
    route_southwest()
    route_southeast()
    route_northeast()
    route_northwest()
    route_buzzer()


def route_ring():
    '''5 V ring on B.Cu, 0.8 mm at inset 1.5 mm, square notches around the four M2 keepouts, closed; every link
    connector's pin 1 and the pogo pad J6.7 feed it.'''
    RING = [(1.5, 7.5), (1.5, 40.5), (7.5, 40.5), (7.5, 46.5), (40.5, 46.5), (40.5, 40.5), (46.5, 40.5), (46.5, 7.5),
            (40.5, 7.5), (40.5, 1.5), (7.5, 1.5), (7.5, 7.5), (1.5, 7.5)]
    T(V5, *RING, w=0.8, layer=B)
    T(V5, J1['1'], (J1['1'][0], 1.5), w=P, layer=B); T(V5, J2['1'], (46.5, J2['1'][1]), w=P, layer=B)
    T(V5, J3['1'], (J3['1'][0], 46.5), w=P, layer=B); T(V5, J4['1'], (1.5, J4['1'][1]), w=P, layer=B)
    v7 = (J6['7'][0], J6['7'][1] + 2.375)
    T(V5, J6['7'], v7, w=P); V(V5, *v7); T(V5, v7, (J6['7'][0], 46.5), w=P, layer=B)


if not PLACE_ONLY:
    route_ring()
    n_stitch = route_guard()
b.zone('GND', 'GND', 0, 0, W, H, layer='In1.Cu')
b.zone('+3V3', '3V3', 0, 0, W, H, layer='In2.Cu')
b.zone('GND', 'GND-B', 0, 0, W, H, layer='B.Cu', thermal_gap=0.3, thermal_bridge=0.4)
b.outline_rect()
d, what = check_hole_clearance()
if not PLACE_ONLY:
    # crystal isolation (see xtal_check.py): >= 1.0 mm same-layer edge gap from any non-GND net, 2.0 mm for the LED nets
    import xtal_check
    bad = xtal_check.failures(b.items, {str(c): n for n, c in b.net.codes.items()})
    assert not bad, 'crystal isolation: ' + '; '.join(f'{n} {v[0]:.2f} mm < {v[3]} near {v[4]}' for n, v in sorted(bad.items()))
b.write(PCB)
print('wrote', PCB, f'(closest to a hole centre: {what} {d:.2f} mm)')
