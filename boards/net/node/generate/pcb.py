#!/usr/bin/env python3
"""Write node.kicad_pcb: 48 x 48 mm, 4 layers (F.Cu signals, In1 GND, In2 +3V3, B.Cu GND pour +
5 V ring + long signal runs). One JST-XH link connector centred on each edge, RP2040 top-left
with its flash below, LEDs right of centre, pogo pads bottom-left, ToF sensor and header along
the bottom, LDO top-right, M2 holes in the corners. See README.md (PCB section) for the plan.

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


for i, (hx, hy) in enumerate([(3.5, 3.5), (44.5, 3.5), (3.5, 44.5), (44.5, 44.5)]):
    b.footprint(f'H{i+1}', hx, hy, ref_fab=True); b.keepout(hx, hy)

# ---- placement ------------------------------------------------------------------------------
J1 = b.footprint('J1', 21.5, 3.5, 0, ref_pos=(2.5, 1.8))          # refs inside the housings (offsets rotate with the part)        # N: pins x 21.5 / 24 / 26.5 at y 3.5
J2 = b.footprint('J2', 44.5, 21.5, 270, ref_pos=(0, 1.8))    # E: pins y 21.5 / 24 / 26.5 at x 44.5
J3 = b.footprint('J3', 26.5, 44.5, 180, ref_pos=(2.5, 1.8))   # S: pins x 26.5 / 24 / 21.5 at y 44.5
J4 = b.footprint('J4', 3.5, 26.5, 90, ref_pos=(0, 1.8), solid_pads=('3',))   # pin 3 (GND) sits between the ring and the SENS_AIN lane: no room for two thermal spokes      # W: pins y 26.5 / 24 / 21.5 at x 3.5
# U1 rot 180: right edge pins 1..14 at x 17.438 (y 15.6 .. 10.4), top edge 15..28 at y 9.562
# (x 16.6 .. 11.4), left edge 29..42 at x 10.562 (y 10.4 .. 15.6), bottom edge 43..56 at
# y 16.438 (x 11.4 .. 16.6). Pad tips: right 17.875, top 9.125, left 10.125, bottom 16.875.
UX = 14.0
U1 = b.footprint('U1', UX, 13.0, 180, ref_pos=(0, 5.6))
U2 = b.footprint('U2', 15.6, 27.4, 90, ref_pos=(-5.4, 0))       # W25Q16: near row y 23.81 (8 VCC 13.7, 7 SD3 14.97, 6 SCLK 16.24, 5 SD0 17.5), far row y 30.99 (1 SS, 2 SD1, 3 SD2, 4 GND)
# crystal above the top edge; XIN straight up, XOUT via the up-left fan to R1, node back over the top
Y1 = b.footprint('Y1', 13.8, 3.3, 90, ref_fab=True)             # 1 XIN (14.65,4.4) 2 GND (14.65,2.2) 3 node (12.95,2.2) 4 GND (12.95,4.4)
R1 = b.footprint('R1', 9.0, 1.7, 270, ref_fab=True)             # vertical on the row end: 2 XOUT (9.0,2.525) bottom, 1 node (9.0,0.875) top
C1 = b.footprint('C1', 16.4, 4.4, 270, ref_fab=True)            # 27p XIN: 1 GND (16.4,3.625) 2 XIN (16.4,5.175)
C2 = b.footprint('C2', 7.05, 2.85, 90, ref_fab=True)            # 27p node: 2 node (7.05,2.075) 1 GND (7.05,3.625), west of R1
# up-left fan from pins 26..21 turns west onto rows y 8.7 / 7.5 / 6.3 / 5.1 / 3.9 / 2.7 (1.2 pitch: vias fit between)
C14 = b.footprint('C14', 8.6, 5.1, 180, ref_fab=True)           # DVDD 23: 1 DVDD (9.375,5.1) 2 GND (7.825,5.1)
R2 = b.footprint('R2', 7.6, 9.7, 90, ref_fab=True)              # RUN pull-up: 2 RUN (7.6,8.925) on the RUN row, 1 3V3 (7.6,10.475)
# left edge
C6 = b.footprint('C6', 8.35, 12.0, 180, ref_fab=True)           # IOVDD 33: 1 3V3 (9.125) 2 GND (7.575)
C7 = b.footprint('C7', 8.35, 15.6, 180, ref_fab=True)           # IOVDD 42
# bottom-left column: ADC_AVDD 43 + VREG_VIN 44 (joined) -> C10; DVDD 45 -> C13, C15
C10 = b.footprint('C10', 8.9, 17.9, 180, ref_fab=True)          # 1 3V3 (9.675,17.9) 2 GND (8.125,17.9)
C11 = b.footprint('C11', 8.9, 19.5, 180, ref_fab=True)          # VREG_VIN 1u under C10 (pin 44 joins 43): 1 3V3 (9.675,19.5) 2 GND (8.125)
C13 = b.footprint('C13', 8.9, 21.1, 180, ref_fab=True)          # DVDD 1u: 1 DVDD (9.675,21.1) 2 GND (8.125)
C15 = b.footprint('C15', 8.9, 22.7, 180, ref_fab=True)          # DVDD 100n
C16 = b.footprint('C16', 10.0, 25.9, 90, ref_fab=True)          # 100n on the planes next to the flash: 1 3V3 (10.0,26.675) 2 GND (10.0,25.125)
R13 = b.footprint('R13', 8.2, 25.0, 90, ref_fab=True)           # W: 2 J4 (8.2,24.175) 1 LINK_W (8.2,25.825)  -- J4.2 at (3.5,24)
R14 = b.footprint('R14', 8.2, 28.2, 90, ref_fab=True)           # W pull-up: 2 LINK_W (8.2,27.375) 1 3V3 (8.2,29.025)
# bottom edge: USB_VDD 48 + IOVDD 49 joined -> C9 (its 3V3 pad also feeds the flash through a via)
C9 = b.footprint('C9', 13.4, 20.7, 270, ref_fab=True)           # 1 3V3 (13.4,19.925) 2 GND (13.4,21.475)
R3 = b.footprint('R3', 20.975, 26.0, 180, ref_fab=True)         # QSPI_SS pull-up: 2 SS (20.2,26) on the SS run, 1 3V3 (21.75,26)
# right edge: IOVDD 10 -> C4; C3 on the plane beside it; IOVDD 1 via only
C4 = b.footprint('C4', 19.7, 12.0, 0, ref_fab=True)             # 1 3V3 (18.925) 2 GND (20.475)
C3 = b.footprint('C3', 23.2, 12.0, 0, ref_fab=True)             # 1 3V3 (22.425) 2 GND (23.975)
# USB series resistors on the way down to J6
R15 = b.footprint('R15', 11.7, 21.4, 90, ref_fab=True)          # 27R DM: 2 DM (11.7,20.575) 1 J6.1 (11.7,22.225)
R16 = b.footprint('R16', 11.7, 24.8, 90, ref_fab=True)          # 27R DP: 2 DP (11.7,23.975) 1 J6.3 (11.7,25.625); only one 0603 column fits between the DVDD track and U2
J6 = b.footprint('J6', 12.5, 38.0, 90, ref_pos=(0, -7.0))       # boards:PogoPads (no paste layer)       # even row y 35.475: 2 SWDIO 8.69, 4 SWCLK 11.23, 6 RUN 13.77, 8 BOOT 16.31; odd row y 40.525: 1 DM, 3 DP, 5 GND, 7 +5V
# LEDs right of centre (rot 90: 3 DIN top-right, 2 GND bottom-right, 1 DOUT bottom-left, 4 VDD top-left)
D2 = b.footprint('D2', 29.0, 24.0, 90, ref_fab=True)
D4 = b.footprint('D4', 29.0, 27.6, 90, ref_fab=True)            # chained below D2 (DNP)
C19 = b.footprint('C19', 31.6, 23.6, 270, ref_fab=True)         # LED_VDD cap: 1 LED_VDD (31.6,22.825) 2 GND (31.6,24.375)
D1 = b.footprint('D1', 34.8, 22.0, 0, ref_fab=True)             # 1N4148W: 1 K LED_VDD (33.15,22) 2 A +5V (36.45,22)
# LDO top-right; C5/C11 moved here as plane caps (no room at their pins; C10/C14 sit at the pins)
U4 = b.footprint('U4', 34.2, 4.2, 0, ref_pos=(0, -3.0))         # 1 VIN (33.06,3.25) 2 GND (33.06,4.2) 3 CE (33.06,5.15) 5 VOUT (35.34,3.25)
C17 = b.footprint('C17', 30.6, 4.2, 90, ref_fab=True)           # 10u in: 1 +5V (30.6,4.975) 2 GND (30.6,3.425)
C18 = b.footprint('C18', 38.0, 4.2, 90, ref_fab=True)           # 10u out: 1 3V3 (38.0,4.975) 2 GND (38.0,3.425)
C12 = b.footprint('C12', 39.6, 4.2, 90, ref_fab=True)           # 10u bulk
C8 = b.footprint('C8', 39.6, 8.4, 90, ref_fab=True)             # 100n
C5 = b.footprint('C5', 41.2, 9.6, 90, ref_fab=True)             # 100n
# piezo element right of centre, series resistors between it and U4; GPIO12/13 (pins 15/16) arrive on rows y 6.2 / 7.0
BZ1 = b.footprint('BZ1', 34.0, 14.4, 90, ref_fab=True)          # pads 2 (34.0,10.05) top, 1 (34.0,18.75) bottom, 3.4 x 1.3
R18 = b.footprint('R18', 31.0, 6.7, 0, ref_fab=True)            # BUZZ_B: 1 (30.175,6.7) 2 (31.825,6.7)
R17 = b.footprint('R17', 31.0, 8.3, 0, ref_fab=True)            # BUZZ_A: 1 (30.175,8.3) 2 (31.825,8.3)
# links: 100 R series near the connector, 4k7 pull-up beside it
R7 = b.footprint('R7', 24.0, 8.4, 0, ref_fab=True)              # N: 1 LINK_N (23.175,8.4) 2 J1 (24.825,8.4)   (R_0603 pads at +-0.825, C_0603 at +-0.775)
R8 = b.footprint('R8', 21.0, 8.4, 0, ref_fab=True)              # N pull-up: 1 3V3 (20.175,8.4) 2 LINK_N (21.825,8.4)
R9 = b.footprint('R9', 39.0, 24.0, 0, ref_fab=True)             # E: 1 LINK_E (38.225,24) 2 J2 (39.775,24)
R10 = b.footprint('R10', 39.0, 25.6, 180, ref_fab=True)         # E pull-up: 2 LINK_E (38.225,25.6) 1 3V3 (39.775,25.6)
R11 = b.footprint('R11', 22.9, 34.9, 270, ref_fab=True)         # S: 1 LINK_S (22.9,34.125) 2 J3 (22.9,35.675)
R12 = b.footprint('R12', 21.7, 32.6, 0, ref_fab=True)           # S pull-up: 1 3V3 (20.925,32.6) 2 LINK_S (22.475,32.6) on the LINK_S run
# sensor block: U3 rot 180 puts SDA/SCL on top (30.0/30.8, y 33.8), XSHUT/INT on the left (28.4)
U3 = b.footprint('U3', 30.0, 34.6, 180, ref_pos=(0, 2.9))       # 1 3V3 (31.6,35.4) 11 3V3 (31.6,33.8) 12 GND (31.6,34.6) 9 SDA (30.0,33.8) 10 SCL (30.8,33.8) 5 XSHUT (28.4,35.4) 7 INT (28.4,33.8) 6 GND (28.4,34.6)
C20 = b.footprint('C20', 34.1, 33.8, 0, ref_fab=True)           # 1 3V3 (33.325) 2 GND (34.875)
C21 = b.footprint('C21', 34.1, 35.4, 0, ref_fab=True)
R4 = b.footprint('R4', 25.6, 12.075, 90, ref_fab=True)          # SDA pull-up: 2 SDA (25.6,11.3) on the SDA run (y 10.9), 1 3V3 (25.6,12.85)
R5 = b.footprint('R5', 28.4, 31.3, 270, ref_fab=True)           # SCL pull-up: 1 3V3 (28.4,30.475) 2 SCL (28.4,32.125) on the SCL run
R6 = b.footprint('R6', 24.925, 22.0, 0, ref_fab=True)           # INT pull-up: 1 3V3 (24.15,22) 2 INT (25.7,22) on the INT run; XSHUT passes under the body
J5 = b.footprint('J5', 20.73, 38.6, 90, ref_pos=(7.6, 2.6))     # pins x 20.73 + 2.54 k: 1 +5V, 2 3V3, 3 INT 25.81, 4 SDA 28.35, 5 SCL 30.89, 6 AIN 33.43, 7 GND 35.97
SW1 = b.footprint('SW1', 42.0, 33.5, 0, ref_fab=True, val_pos=(0, -3.6))   # vib variant, DNP: 1 GND (40.73) 2 SENS_INT (43.27)
C22 = b.footprint('C22', 38.4, 33.5, 270, ref_fab=True)         # debounce: 1 SENS_INT (38.4,32.725) 2 GND (38.4,34.275)

if __name__ == '__main__' and '--pads' in sys.argv:
    for ref in sys.argv[2:] or ('U1', 'U2', 'Y1', 'J6', 'U3', 'J5', 'U4', 'D2', 'D4', 'D1'):
        print(ref, globals()[ref])
    sys.exit()

# ---- nets -----------------------------------------------------------------------------------
G, V3, V5, DVDD = 'GND', '+3V3', '+5V', N('U1', '45')
XIN, XOUT, XNODE = N('U1', '20'), N('U1', '21'), N('Y1', '3')
RUN, SWDIO, SWCLK = N('U1', '26'), N('U1', '25'), N('U1', '24')
DM, DP = N('U1', '46'), N('U1', '47')
SD3, SCLK, SD0, SD2, SD1, SS = (N('U1', p) for p in ('51', '52', '53', '54', '55', '56'))
LN, LE, LS, LW, LDIN = (N('U1', p) for p in ('2', '3', '4', '5', '6'))
XSHUT, INT, SDA, SCL, AIN = N('U1', '7'), N('U1', '8'), N('U1', '13'), N('U1', '14'), N('U1', '38')
LVDD, J6DM, J6DP, J3S, DOUT = N('D2', '4'), N('R15', '1'), N('R16', '1'), N('R11', '2'), N('D2', '1')

# ---- U1 ground pad ---------------------------------------------------------------------------
for x in (UX - 0.6, UX + 0.6):
    for y in (12.4, 13.6):
        V(G, x, y)

# ---- U1 top edge: pins 15..28 at x = UX + 2.6 - 0.4 (pin - 15): 19 GND 15.0, 20 XIN 14.6, 21 XOUT 14.2,
# 22 3V3 13.8, 23 DVDD 13.4, 24 SWCLK 13.0, 25 SWDIO 12.6, 26 RUN 12.2 --------------------------
T(G, (15.0, 9.125), (15.0, 8.7), (15.5, 8.2)); V(G, 15.5, 8.2)                                 # 19
# 15 BUZZ_A (16.6) and 16 BUZZ_B (16.2) up-right onto rows y 6.2 / 7.0, east to R17/R18, then BZ1
BA, BB = N('U1', '15'), N('U1', '16')
T(BB, (16.2, 9.125), (16.2, 8.9), (18.9, 6.2), (29.7, 6.2), (30.175, 6.675))   # right pin (15) bends first; its line is the lower one east of x 18.7
T(BA, (16.6, 9.125), (16.6, 9.1), (18.7, 7.0), (28.9, 7.0), (30.0, 8.1), (30.175, 8.3))
T(N('R18', '2'), (31.825, 6.7), (33.0, 7.875), (33.0, 9.5), BZ1['2'])
T(N('R17', '2'), (31.825, 8.3), (31.825, 8.9), (28.9, 11.825), (28.7, 12.025), (28.7, 18.75), BZ1['1'])
T(XIN, (14.6, 9.125), (14.6, 4.4))                                                             # 20 straight up into Y1.1
# up-left fan: pin k (26 = 0 .. 21 = 5) goes straight to y 8.9 - 0.2k, then 45 deg up-left, then west along its row
ROWS = [8.7, 7.5, 6.3, 5.1, 3.9, 2.7]
ROWX = []
for k, net in enumerate((RUN, SWDIO, SWCLK, DVDD, V3, XOUT)):
    x, by = 12.2 + 0.4 * k, 8.9 - 0.2 * k
    rx = x - (by - ROWS[k])
    ROWX.append(rx)
    T(net, (x, 9.125), (x, by), (rx, ROWS[k]))
T(RUN, (ROWX[0], 8.7), (6.9, 8.7)); V(RUN, 6.9, 8.7)                                           # row 0 (through R2.2)
T(SWDIO, (ROWX[1], 7.5), (5.7, 7.5)); V(SWDIO, 5.7, 7.5)                                       # row 1
T(SWCLK, (ROWX[2], 6.3), (6.3, 6.3)); V(SWCLK, 6.3, 6.3)                                       # row 2
T(DVDD, (ROWX[3], 5.1), (9.375, 5.1)); T(DVDD, (10.1, 5.1), (10.4, 5.4), (10.4, 5.7)); V(DVDD, 10.4, 5.7)   # row 3 -> C14.1, via between rows
T(V3, (ROWX[4], 3.9), (8.4, 3.9)); V(V3, 8.4, 3.9)                                             # row 4 -> via (IOVDD 22)
T(XOUT, (ROWX[5], 2.7), (9.0, 2.525))                                                          # row 5 ends in R1.2
pad_via(V3, 7.6, 10.475, 8.5, 10.475)                                                          # R2.1
pad_via(G, 7.825, 5.1, 7.0, 5.1)                                                               # C14.2
# crystal: R1.1 -> over the top -> Y1.3 (through C2.2); C1 on XIN; GND vias
T(XNODE, (9.0, 0.875), (12.35, 0.875), (12.95, 1.475), (12.95, 2.2))                          # R1.1 -> Y1.3 along the top
T(XNODE, (9.0, 0.875), (7.5, 0.875), (7.05, 1.325), (7.05, 2.075))                           # -> C2.2
pad_via(G, 7.05, 3.625, 7.05, 4.5); T(G, (12.95, 4.4), (12.95, 5.55), (13.3, 5.9)); V(G, 13.3, 5.9)   # C2.1, Y1.4 (via below the pad, clear of the diagonals)
T(XIN, (14.65, 4.4), (15.1, 4.85), (15.6, 5.175), (16.4, 5.175))                                # Y1.1 -> C1.2
T(G, (14.65, 2.2), (15.5, 2.6)); T(G, (16.4, 3.625), (15.9, 3.1), (15.5, 2.6)); V(G, 15.5, 2.6)   # Y1.2 + C1.1

# ---- U1 left edge: 33 -> C6, 42 -> C7, 38 SENS_AIN west on F.Cu to the west B.Cu lane -------
T(V3, (10.125, 12.0), (9.125, 12.0)); pad_via(V3, 9.125, 12.0, 9.125, 13.2); pad_via(G, 7.575, 12.0, 7.575, 13.4)
T(V3, (10.125, 15.6), (9.125, 15.6)); pad_via(V3, 9.125, 15.6, 9.125, 14.7); pad_via(G, 7.575, 15.6, 7.575, 14.8)
T(AIN, (10.125, 14.0), (4.6, 14.0)); V(AIN, 4.6, 14.0)

# ---- west B.Cu lanes: SENS_AIN 5.2, SWDIO 5.7, SWCLK 6.3, RUN 6.9; vias sit inside the pogo pads
T(SWDIO, (5.7, 7.5), (5.7, 34.9), (8.69, 34.9), layer=B); V(SWDIO, 8.69, 34.9)
T(SWCLK, (6.3, 6.3), (6.3, 34.1), (11.23, 34.1), (11.23, 34.9), layer=B); V(SWCLK, 11.23, 34.9)
T(RUN, (6.9, 8.7), (6.9, 33.3), (13.77, 33.3), (13.77, 34.9), layer=B); V(RUN, 13.77, 34.9)
T(AIN, (4.6, 14.0), (4.6, 14.4), (5.2, 15.0), (5.2, 39.75), (33.43, 39.75), (33.43, 38.6), layer=B)   # -> J5.6 (THT), above the ring notch

# ---- U1 bottom edge -------------------------------------------------------------------------
T(V3, (UX - 2.6, 16.9), (UX - 2.2, 16.9)); T(V3, (UX - 2.6, 16.9), (UX - 3.6, 17.9), (10.125, 17.9))   # 43+44 -> C10.1
pad_via(V3, 9.675, 17.9, 9.675, 16.7); pad_via(G, 8.125, 17.9, 7.7, 17.9)                       # C10 vias
T(DVDD, (UX - 1.8, 16.875), (UX - 1.8, 17.3), (10.9, 18.6), (10.9, 22.7), (10.125, 22.7))        # 45 -> down x 10.9 -> C15.1
T(DVDD, (10.9, 21.1), (10.125, 21.1)); T(DVDD, (10.9, 21.9), (10.2, 21.9)); V(DVDD, 10.2, 21.9)   # C13.1, DVDD via between C13/C15
T(V3, (9.675, 17.9), (9.675, 19.5)); pad_via(G, 8.125, 19.5, 7.7, 19.5)                          # C11 on C10's 3V3 pad
pad_via(G, 8.125, 21.1, 7.7, 21.1); pad_via(G, 8.125, 22.7, 7.7, 22.7)
T(DM, (UX - 1.4, 16.875), (UX - 1.4, 18.8), (11.7, 19.7), (11.7, 20.575))                      # 46 -> R15.2
T(DP, (UX - 1.0, 16.875), (UX - 1.0, 19.0), (12.6, 19.4), (12.6, 23.2), (11.9, 23.9), (11.7, 23.975))   # 47 -> past R15 -> R16.2
T(V3, (UX - 0.6, 16.9), (UX - 0.2, 16.9)); T(V3, (13.6, 16.9), (13.6, 19.925))                 # 48+49 -> C9.1
T(V3, (13.875, 19.925), (14.35, 20.0)); V(V3, 14.35, 20.0)                                     # C9.1 via
V(V3, 13.695, 22.5); T(V3, (13.695, 22.5), (13.695, 23.8125))                                  # U2.8 VCC from the plane
pad_via(G, 13.4, 21.475, 14.3, 21.9)                                                           # C9.2
T(DVDD, (UX + 0.2, 16.875), (UX + 0.2, 18.9)); V(DVDD, UX + 0.2, 18.9)                          # 50 via
# DVDD on B.Cu: C14 via (10.4, 5.7) -> C13/C15 via (10.2, 21.9) -> pin 50 via (14.2, 18.9)
T(DVDD, (10.4, 5.7), (10.4, 21.7), (10.2, 21.9), (12.0, 21.9), (12.0, 20.3), (13.0, 20.3), (14.2, 19.1), (14.2, 18.9), layer=B)
pad_via(V3, 10.0, 26.675, 10.0, 28.4); pad_via(G, 10.0, 25.125, 10.0, 24.2)                    # C16
# QSPI: 51..53 to the near row, 54..56 around the right side to the far row (bend order 56 first)
T(SD3, (UX + 0.6, 16.875), (UX + 0.6, 18.4), (14.965, 18.765), (14.965, 23.8125))              # 51 -> U2.7
T(SCLK, (UX + 1.0, 16.875), (UX + 1.0, 18.1), (16.235, 19.335), (16.235, 23.8125))             # 52 -> U2.6
T(SD0, (UX + 1.4, 16.875), (UX + 1.4, 17.8), (17.505, 19.905), (17.505, 23.8125))              # 53 -> U2.5
T(SD2, (UX + 1.8, 16.875), (UX + 1.8, 17.5), (18.7, 20.4), (18.7, 32.1), (16.235, 32.1), (16.235, 30.9875))   # 54 -> U2.3
T(SD1, (UX + 2.2, 16.875), (UX + 2.2, 17.2), (19.4, 20.4), (19.4, 32.55), (14.965, 32.55), (14.965, 30.9875))  # 55 -> U2.2
T(SS, (UX + 2.6, 16.875), (UX + 2.6, 16.9), (20.1, 20.4), (20.1, 33.0), (13.695, 33.0), (13.695, 30.9875))    # 56 -> U2.1
T(SS, (16.31, 33.0), (16.31, 35.475))                                                          # -> J6.8 BOOT
pad_via(V3, 21.75, 26.0, 21.75, 27.4)                                                          # R3.1 (R3.2 sits on the SS run)
pad_via(G, 17.505, 30.9875, 17.505, 29.9)                                                      # U2.4 GND
# USB: R15 -> J6.1 (8.69, 40.025) between the even-row pads; R16 -> J6.3 (11.23, 40.025)
T(J6DM, (11.7, 22.225), (11.7, 22.55), (11.15, 23.1), (10.9, 23.5), (10.9, 30.5), (10.0, 31.4), (10.0, 37.5), (9.2, 38.3), (8.69, 38.8), (8.69, 40.525))
T(J6DP, (11.7, 25.625), (11.7, 29.2), (12.1, 29.6), (12.1, 38.1), (11.4, 38.8), (11.23, 39.0), (11.23, 40.525))

# ---- U1 right edge: 1 via; 2..8 fan down-right, turn south at y 18.1 on x 21.5 + 0.7k --------
T(V3, (17.6, 15.6), (18.3, 16.3)); V(V3, 18.5, 16.5)                                            # pin 1
XK = [21.5 + 0.7 * k for k in range(7)]
for k, net in enumerate((LN, LE, LS, LW, LDIN, XSHUT, INT)):
    y = 15.2 - 0.4 * k
    bx = 18.6 + 0.3 * k
    T(net, (17.875, y), (bx, y), (XK[k], 18.1))
T(LN, (XK[0], 18.1), (XK[0], 19.6)); V(LN, XK[0], 19.6)
T(LE, (XK[1], 18.1), (XK[1], 20.1)); V(LE, XK[1], 20.1)
T(LW, (XK[3], 18.1), (XK[3], 19.1)); V(LW, XK[3], 19.1)
T(LDIN, (XK[4], 18.1), (XK[4], 20.3)); V(LDIN, XK[4], 20.3)
# pin 10 -> via -> C4; C3 on the plane beside it
T(V3, (17.875, 12.0), (18.925, 12.0)); V(V3, 18.5, 12.0); pad_via(G, 20.475, 12.0, 21.3, 12.0)
pad_via(V3, 22.425, 12.0, 22.425, 13.0); pad_via(G, 23.975, 12.0, 23.975, 13.0)
# pin 13 SDA (y 10.8) straight east, pin 14 SCL (y 10.4) up-right to y 10.1; both south on F.Cu at x 26.6 / 27.3
T(SDA, (17.875, 10.8), (18.2, 10.8), (18.3, 10.9), (26.6, 10.9), (26.6, 32.9), (30.0, 32.9), (30.0, 33.8))   # -> U3.9
T(SCL, (17.875, 10.4), (27.3, 10.4), (27.3, 31.9), (30.8, 31.9), (30.8, 33.8))                 # -> U3.10
pad_via(V3, 25.6, 12.85, 25.6, 13.9)                                                           # R4.1 (R4.2 on the SDA run)
pad_via(V3, 28.4, 30.475, 28.4, 29.6)                                                          # R5.1 (R5.2 on the SCL run)
T(SDA, (26.6, 32.9), (26.6, 33.4)); V(SDA, 26.6, 33.4); T(SDA, (26.6, 33.4), (26.6, 36.6), (28.35, 38.35), (28.35, 38.6), layer=B)   # -> J5.4
V(SCL, 27.3, 31.2); T(SCL, (27.3, 31.2), (27.3, 35.0), (30.89, 38.59), (30.89, 38.6), layer=B)   # -> J5.5
# XSHUT (x 25.0) and INT (x 25.7) south, then east to U3's left column
T(XSHUT, (XK[5], 18.1), (XK[5], 37.2), (27.6, 37.2), (28.4, 36.4), (28.4, 35.4))               # -> U3.5
T(INT, (XK[6], 18.1), (XK[6], 35.05), (27.6, 35.05), (27.6, 33.8), (28.4, 33.8))              # -> U3.7
pad_via(V3, 24.15, 22.0, 24.3, 23.5)                                                           # R6.1 (R6.2 on the INT run)
T(INT, (XK[6], 35.05), (XK[6], 36.0)); V(INT, XK[6], 36.0); T(INT, (XK[6], 36.0), (25.81, 38.6), layer=B)   # -> J5.3
V(INT, XK[6], 30.5); T(INT, (XK[6], 30.5), (37.0, 30.5), (38.4, 31.9), layer=B); V(INT, 38.4, 31.9)   # -> C22 / SW1 (vib)
T(INT, (38.4, 31.9), (38.4, 32.725)); T(N('SW1', '2'), (43.27, 33.5), (43.27, 32.0), (39.0, 32.0), (38.4, 32.6))
pad_via(G, 38.4, 34.275, 38.4, 35.3); pad_via(G, 40.73, 33.5, 40.73, 35.5, w=P)                # C22.2, SW1.1
# LINK_S: F.Cu south at x 22.9 -> R11 -> J3.2 (24, 44.5) between J5 pins 1 and 2; R12 pull-up sits on the run
T(LS, (XK[2], 18.1), (XK[2], 34.125)); pad_via(V3, 20.925, 32.6, 20.925, 31.6)
T(J3S, (22.9, 35.675), (22.0, 36.575), (22.0, 43.2), (24.0, 43.2), (24.0, 44.5))
# LINK_N: B.Cu north on x 20.5, east on y 9.4 to R7 (24, 9.375); R8 pull-up beside it
T(LN, (XK[0], 19.6), (20.5, 18.6), (20.5, 9.4), (23.1, 9.4), layer=B); V(LN, 23.1, 9.4)
T(LN, (23.1, 9.4), (23.1, 8.4), (21.825, 8.4)); T(N('R7', '2'), (24.825, 8.4), (24.825, 9.4)); V(N('R7', '2'), 24.825, 9.4); T(N('R7', '2'), (24.825, 9.4), (24.825, 4.3), (24.0, 3.5), layer=B)   # under the BUZZ rows
pad_via(V3, 20.175, 8.4, 19.4, 8.4)                                                            # R8.1
# LINK_E: B.Cu north on x 22.2, east on y 15.4, south on x 36.4 to R9/R10
T(LE, (XK[1], 20.1), (XK[1], 15.4), (36.4, 15.4), (36.4, 24.0), layer=B); V(LE, 36.4, 24.0)
T(LE, (36.4, 24.0), (38.225, 24.0), (38.225, 25.6)); T(N('R9', '2'), (39.775, 24.0), (44.5, 24.0)); pad_via(V3, 39.775, 25.6, 40.7, 26.6)
# LINK_W: B.Cu south on x 23.6, west on y 25.6 to the via between R13.1 and R14.2; R13.2 -> J4.2
T(LW, (XK[3], 19.1), (XK[3], 26.6), (8.2, 26.6), layer=B); V(LW, 8.2, 26.6)
T(LW, (8.2, 25.825), (8.2, 27.375)); T(N('R13', '2'), (8.2, 24.175), (8.0, 24.0), (3.5, 24.0)); pad_via(V3, 8.2, 29.025, 8.2, 30.0)
# LED_DIN: B.Cu east on y 20.3, via above D2.3 (top-right pad)
T(LDIN, (XK[4], 20.3), (29.6, 20.3), (30.4, 21.1), (30.4, 22.1), layer=B); V(LDIN, 30.4, 22.1); T(LDIN, (30.4, 22.1), (29.75, 22.75), D2['3'])
# LEDs: D2 DOUT (bottom-left) -> D4 DIN (top-right) around D2's GND pad; LED_VDD from D1 through C19 to both VDD pads (top-left)
T(DOUT, D2['1'], (28.45, 25.4), (28.65, 25.6), (29.35, 25.6), (29.55, 25.8), D4['3'])   # between D2.2 (GND) and D4.4 (VDD)
T(LVDD, D2['4'], (27.75, 23.085), (27.75, 21.2), (31.0, 21.2), (31.6, 21.8), (31.6, 22.825)); T(LVDD, (31.0, 21.2), (32.4, 21.2), (33.15, 21.95), (33.15, 22.0))
T(LVDD, (27.75, 23.085), (27.75, 26.285), D4['4'])
T(G, D2['2'], (30.2, 25.4)); T(G, (31.6, 24.375), (31.0, 24.975), (30.2, 25.4)); V(G, 30.2, 25.4); pad_via(G, *D4['2'], 29.55, 29.4)
T(V5, (36.45, 22.0), (36.9, 21.6), (43.6, 21.6), (44.5, 21.5), w=P)                            # D1.2 -> J2.1 (+5V)

# ---- LDO ------------------------------------------------------------------------------------
T(V5, (33.06, 3.25), (32.3, 3.25), (31.6, 3.95), (31.6, 5.15), (32.3, 5.15), (33.06, 5.15), w=P)   # VIN + CE
T(V5, (31.6, 4.975), (31.075, 4.975), w=P); T(V5, (31.6, 3.95), (31.6, 2.4), w=P); V(V5, 31.6, 2.4)   # C17.1, via to the ring
T(V5, (31.6, 2.4), (31.6, 1.5), w=P, layer=B)
pad_via(G, 33.06, 4.2, 33.9, 4.2); pad_via(G, 30.6, 3.425, 29.7, 3.425)                        # U4.2, C17.2
T(V3, (35.34, 3.25), (36.2, 3.25), (37.0, 4.05), (37.0, 4.975), (37.525, 4.975), w=P)           # VOUT -> C18.1
T(V3, (37.0, 4.975), (36.6, 5.375), (36.6, 5.8), w=P); V(V3, 36.6, 5.8)
pad_via(G, 38.0, 3.425, 38.0, 2.5); pad_via(V3, 39.6, 4.975, 39.6, 6.0); pad_via(G, 39.6, 3.425, 39.6, 2.5)   # C18.2, C12
pad_via(V3, 39.6, 9.175, 39.6, 10.2); pad_via(G, 39.6, 7.625, 38.7, 7.625)                     # C8
pad_via(V3, 41.2, 10.375, 42.1, 10.375); pad_via(G, 41.2, 8.825, 42.1, 8.825)                  # C5

# ---- sensor block power, J5 ------------------------------------------------------------------
T(V3, (31.6, 33.8), (33.325, 33.8)); T(V3, (31.6, 35.4), (33.325, 35.4))
pad_via(V3, 33.325, 33.8, 33.325, 32.7); pad_via(V3, 33.325, 35.4, 33.325, 36.5)
pad_via(G, 34.875, 33.8, 35.8, 33.8); pad_via(G, 34.875, 35.4, 35.8, 35.4)
T(G, (28.4, 34.6), (31.6, 34.6)); T(G, (29.2, 35.4), (30.8, 35.4)); T(G, (30.0, 35.4), (30.0, 34.6)); V(G, 30.0, 34.6)   # U3 GND pads 12, 6, 2, 3, 4
T(V3, (23.27, 38.6), (23.27, 41.0)); V(V3, 23.27, 41.0)                                        # J5.2
T(V5, (20.73, 38.6), (20.0, 39.3), (16.6, 39.3), w=P)                                          # J5.1 -> J6.7 (+5V pad)

# ---- 5 V ring on B.Cu: 0.8 mm at inset 1.5, notched around three M2 keepouts, open at the top-left
# corner (the crystal/SWD vias live there); feeds from every connector's pin 1 and from J6.7
RING = [(1.5, 7.5), (1.5, 40.5), (7.5, 40.5), (7.5, 46.5), (40.5, 46.5), (40.5, 40.5), (46.5, 40.5), (46.5, 7.5), (40.5, 7.5), (40.5, 1.5), (7.5, 1.5)]
T(V5, *RING, w=0.8, layer=B)
T(V5, (21.5, 3.5), (21.5, 1.5), w=P, layer=B); T(V5, (44.5, 21.5), (46.5, 21.5), w=P, layer=B)   # J1.1, J2.1
T(V5, (26.5, 44.5), (26.5, 46.5), w=P, layer=B); T(V5, (3.5, 26.5), (1.5, 26.5), w=P, layer=B)   # J3.1, J4.1
T(V5, (16.31, 40.525), (16.31, 43.3), w=P); V(V5, 16.31, 43.3); T(V5, (16.31, 43.3), (16.31, 46.5), w=P, layer=B)   # J6.7
pad_via(G, 13.77, 40.525, 13.77, 42.7, w=P)                                                     # J6.5 GND

b.zone('GND', 'GND', 0, 0, W, H, layer='In1.Cu')
b.zone('+3V3', '3V3', 0, 0, W, H, layer='In2.Cu')
b.zone('GND', 'GND-B', 0, 0, W, H, layer='B.Cu', thermal_gap=0.3, thermal_bridge=0.4)   # narrower reliefs: J4.3 sits between the ring and the SENS_AIN lane
b.outline_rect()
b.write(PCB)
print('wrote', PCB)
