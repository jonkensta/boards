#!/usr/bin/env python3
"""Write hat.kicad_pcb: 65 x 56.5 mm Raspberry Pi HAT, 2 layers.

Header (back side) along the top edge at the HAT-spec position, DAC block left/centre
(geometry translated from chromatone/dac), isolator with its LED island bottom right
(from chromatone/isolator), ID EEPROM top right. Board origin: top-left corner, y down.
"""
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, 'boardtools')):
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from boardtools.pcbgen import Board, Netlist, SIG, PWR

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, '..', 'hat.kicad_pcb')
W, H = 65.0, 56.5
b = Board(PCB, Netlist(os.path.join(HERE, 'hat.net')), 'hat.kicad_sch', W, H)
N = lambda ref, pin: b.net.node_net[(ref, pin)]     # net of a pin, from the schematic

# ---- HAT mechanics: holes (58 x 49), 2x20 socket on the back, pin 1 at (8.37, 4.77) ----
for i, (hx, hy) in enumerate([(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]):
    b.footprint(f'H{i+1}', hx, hy, ref_fab=True); b.keepout(hx, hy)
J1 = b.footprint('J1', 8.37, 4.77, 270, ref_fab=True, side='B', solid_pads=('6', '9', '14'))   # pads on the pour slivers cut off by the 3V3 link
assert J1['1'] == (8.37, 4.77) and J1['2'] == (8.37, 2.23) and J1['3'] == (10.91, 4.77) and J1['40'] == (56.63, 2.23), J1
HP = lambda n: J1[str(n)]                            # header pin -> board position

# header power: 5V pins 2+4 joined on the front; 3V3 pins 1+17 joined on the back under the socket
b.seg('+5V', PWR, HP(2), HP(4))
b.seg('+3V3', PWR, HP(1), (8.37, 7.0), (28.69, 7.0), HP(17), layer='B.Cu')
# that back-side link isolates the pour slivers around pads 6/9/14; pad 9 (GND) gets a front stub to a via
b.seg('GND', SIG, HP(9), (18.53, 9.0)); b.via('GND', 18.53, 9.0)

# ======================================================================================
# DAC block: chromatone/dac rev A geometry rotated 90 deg CCW onto the right half, jack on
# the bottom edge. T() maps old board coords (56 x 36, jack left) to HAT coords; footprint
# rotations gain 90. Old refs -> new: U1 U2, U2 U3, J2 J3, R1..R7 R5..R11, C1..C12 C5..C16,
# D1 D3, TP1..TP3 TP7..TP9. The Pi connector (old J1) is gone: I2S, 5V and XSMT come from
# the header via the escapes further down.
# ======================================================================================
class Pt(tuple): pass                                 # a point already in HAT coordinates (pad centres)
def T(x, y): return (31.0 + y, 56.5 - x)
def FD(ref, x, y, rot=0, **kw): return {k: Pt(v) for k, v in b.footprint(ref, *T(x, y), (rot + 90) % 360, **kw).items()}
def SD(net, w, *pts, layer='F.Cu'): b.seg(net, w, *[p if isinstance(p, Pt) else T(*p) for p in pts], layer=layer)
def VD(net, x, y): b.via(net, *T(x, y))
S2 = 0.2
RAIL = 11.0                                           # old y of the 3.3 V rail (new x = 42)
V3D = '+3V3_DAC'

U2 = FD('U2', 37.0, 17.0, 0, ref_pos=(0, 5.0))        # PCM5102A; old left pins 1-10 -> new bottom row, 11-20 top
U3 = FD('U3', 33.0, 6.0, 0, ref_pos=(0, -2.9))        # ME6211 LDO
J3 = FD('J3', 9.0, 22.0, 0, ref_pos=(0, -6.5))        # 3.5 mm jack, opening toward the bottom edge
R5 = FD('R5', 45.8, 16.0, 180, ref_fab=True)          # 33 R LRCK: pad1 north (toward the header), pad2 south (U2)
R6 = FD('R6', 45.8, 18.5, 180, ref_fab=True)          # 33 R DIN
R7 = {k: Pt(v) for k, v in b.footprint('R7', 53.0, 10.7, 270, ref_fab=True).items()} # 33 R BCK, moved 1 mm east of its old slot for the header escape
R10 = FD('R10', 37.4, 12.6, 0, ref_fab=True)          # 10k XSMT pull-up
C5 = FD('C5', 29.2, 5.6, 180, ref_fab=True)           # 10u LDO in
C6 = FD('C6', 36.6, 7.6, 0, ref_fab=True)             # 10u LDO out
C7 = FD('C7', 25.4, 13.0, 180, ref_fab=True)          # 10u rail
C8 = FD('C8', 25.4, 15.5, 180, ref_fab=True)
C9 = FD('C9', 31.1, 14.725, 180, ref_fab=True)        # 2.2u flying
C10 = FD('C10', 29.6, 17.6, 270, ref_fab=True)        # 2.2u VNEG
C11 = FD('C11', 42.8, 15.6, 0, ref_fab=True)          # 2.2u LDOO
C12 = FD('C12', 16.8, 15.0, 90, ref_fab=True)         # 2.2n L
C13 = FD('C13', 16.5, 23.8, 270, ref_fab=True)        # 2.2n R
C14 = FD('C14', 31.6, 19.6, 270, ref_fab=True)        # 100n AVDD
C15 = FD('C15', 42.8, 14.075, 0, ref_fab=True)        # 100n DVDD
C16 = FD('C16', 33.3, 11.9, 270, ref_fab=True)        # 100n CPVDD
R8 = FD('R8', 17.8, 17.325, 180, ref_fab=True)        # 470 L
R9 = FD('R9', 18.8, 22.4, 180, ref_fab=True)          # 470 R
R11 = FD('R11', 23.0, 8.0, 0, ref_fab=True)           # 1k LED
D3 = FD('D3', 26.0, 8.0, 180, ref_fab=True)           # LED: 1 K, 2 A
TP7 = b.footprint('TP7', 43.4, 11.3, ref_fab=True, val_pos=(0, -2.0))['1']     # LRCK, west of R5
TP8 = b.footprint('TP8', 55.0, 11.3, ref_fab=True, val_pos=(0, -2.0))['1']     # BCK, east of R7
TP9 = FD('TP9', 20.0, 28.0, ref_fab=True, val_pos=(2.0, 0))['1']   # Pt               # GND
def near(a, b): return abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3
assert near(U2['1'], T(34.1375, 14.075)) and near(U2['15'], T(39.8625, 17.325)) and near(R5['2'], T(44.975, 16.0)), (U2, R5)
assert near(R7['1'], (53.0, 9.875)) and near(R7['2'], (53.0, 11.525)) and near(C9['1'], T(31.875, 14.725)), (R7, C9)
for ref, pin, net in (('R5', '2', 'U2'), ('R8', '1', 'U2'), ('C9', '1', 'U2'), ('C11', '1', 'U2')):   # pad roles vs schematic
    assert net in N(ref, pin), (ref, pin, N(ref, pin))

# LDO -> 3.3 V rail (5 V arrives at old (30, 4) = new (35, 26.5) from the header escapes)
SD('+5V', PWR, (30.0, 4.0), (30.0, 6.95), U3['3'])
SD('+5V', PWR, (30.0, 5.05), U3['1'])
SD('+5V', SIG, C5['1'], (30.0, 5.6))
SD('GND', SIG, C5['2'], (27.6, 5.6)); VD('GND', 27.6, 5.6)
SD('GND', SIG, U3['2'], (33.0, 6.0)); VD('GND', 33.0, 6.0)
SD(V3D, PWR, U3['5'], (35.3, 5.05), (35.3, RAIL))
SD(V3D, SIG, C6['1'], (35.3, 7.6)); SD('GND', SIG, C6['2'], (38.1, 7.6)); VD('GND', 38.1, 7.6)
SD(V3D, PWR, (22.175, RAIL), (42.025, RAIL))
SD(V3D, PWR, (27.0, RAIL), (27.0, 23.5), (30.55, 23.5), (30.55, 18.825), C14['1'])
SD(V3D, SIG, C7['1'], (27.0, 13.0)); SD('GND', SIG, C7['2'], (23.8, 13.0)); VD('GND', 23.8, 13.0)
SD(V3D, SIG, C8['1'], (27.0, 15.5)); SD('GND', SIG, C8['2'], (23.8, 15.5)); VD('GND', 23.8, 15.5)
SD(V3D, SIG, R11['1'], (22.175, RAIL)); SD(N('R11', '2'), SIG, R11['2'], D3['2'])
SD('GND', SIG, D3['1'], (27.6, 8.0)); VD('GND', 27.6, 8.0)
# U2 old-left side: CPVDD CAPP CPGND CAPM VNEG OUTL OUTR AVDD AGND DEMP
SD(V3D, S2, U2['1'], (34.1, 14.075), (34.1, 11.45), (33.775, 11.125))
SD('GND', SIG, C16['2'], (32.85, 13.15)); VD('GND', 32.85, 13.15)
SD(N('U2', '2'), S2, U2['2'], C9['1'])
SD('GND', S2, U2['3'], (32.9, 15.375)); VD('GND', 32.9, 15.375)
SD(N('U2', '4'), S2, U2['4'], (30.0, 16.025), (30.0, 15.2))
SD(N('U2', '5'), S2, U2['5'], (31.5, 16.675), (31.35, 16.825), (30.075, 16.825))
SD('GND', SIG, C10['2'], (29.6, 19.4)); VD('GND', 29.6, 19.4)
OL, OR_ = N('U2', '6'), N('U2', '7')
SD(OL, S2, U2['6'], (32.0, 17.325)); VD(OL, 32.0, 17.325)
SD(OR_, S2, U2['7'], (32.85, 17.975)); VD(OR_, 32.85, 17.975)
SD(V3D, S2, U2['8'], (32.6, 18.625), (32.4, 18.825), (32.075, 18.825))
SD('GND', SIG, C14['2'], (31.6, 21.3)); VD('GND', 31.6, 21.3)
SD('GND', S2, U2['9'], (32.9, 19.275), (32.6, 19.5)); VD('GND', 32.6, 19.5)
SD('GND', S2, U2['10'], (33.5, 19.925), (33.4, 20.3)); VD('GND', 33.4, 20.6)
# U2 old-right side: DVDD DGND LDOO XSMT FMT LRCK DIN BCK SCK FLT
SD(V3D, S2, U2['20'], C15['1']); SD(V3D, SIG, C15['1'], (42.025, RAIL))
SD('GND', SIG, C15['2'], (44.2, 14.075)); VD('GND', 44.2, 14.075)
SD('GND', S2, U2['19'], (40.9, 14.725)); VD('GND', 40.9, 14.725)
SD(N('U2', '18'), S2, U2['18'], (41.4, 15.375), (41.625, 15.6), C11['1']); SD('GND', SIG, C11['2'], (44.0, 15.15)); VD('GND', 44.0, 15.15)
XS = N('U2', '17')
SD(XS, S2, U2['17'], (40.9, 16.025)); VD(XS, 40.9, 16.025)
SD(XS, S2, (40.9, 16.025), (40.0, 15.125), (40.0, 13.4), (39.2, 12.6), layer='B.Cu'); VD(XS, 39.2, 12.6)
SD(XS, SIG, (39.2, 12.6), R10['2']); SD(V3D, SIG, R10['1'], (36.575, RAIL))
SD('GND', S2, U2['16'], (40.9, 16.675), (41.6, 16.675)); VD('GND', 41.6, 16.675)
LR, DI, BC = N('U2', '15'), N('U2', '14'), N('U2', '13')
SD(LR, S2, U2['15'], (40.9, 17.325), (41.375, 17.8), (43.6, 17.8), (44.975, 16.425), R5['2'])
SD(DI, S2, U2['14'], (40.9, 17.975), (41.425, 18.5), R6['2'])
b.seg(BC, S2, U2['13'], (49.625, 15.6), (53.0, 12.225), R7['2'])
SD('GND', S2, U2['12'], (40.9, 19.275), (40.9, 21.3)); VD('GND', 40.9, 21.3)
SD('GND', S2, U2['11'], (40.9, 19.925))
b.seg(LR, SIG, (47.0, 11.3), TP7); b.seg(BC, SIG, (53.0, 11.3), TP8)
# audio out on B.Cu to the filter, jack
SD(OL, SIG, (32.0, 17.325), (19.9, 17.325), layer='B.Cu'); VD(OL, 19.9, 17.325); SD(OL, SIG, (19.9, 17.325), R8['1'])
SD(OR_, SIG, (32.85, 17.975), (32.85, 18.4), (21.5, 18.4), (20.9, 19.0), (20.9, 22.4), layer='B.Cu'); VD(OR_, 20.9, 22.4); SD(OR_, SIG, (20.9, 22.4), R9['1'])
LN, RN = N('J3', 'T'), N('J3', 'R1')
SD(LN, SIG, R8['2'], (16.8, 17.325), (15.375, 18.75), J3['T'])
SD(LN, SIG, (16.8, 17.325), C12['1']); SD('GND', SIG, C12['2'], (16.8, 13.3)); VD('GND', 16.8, 13.3)
SD(RN, SIG, R9['2'], (16.5, 22.4), (16.5, 20.6), (9.8, 20.6), (9.4, 20.2), (8.825, 20.2), J3['R1'])
SD(RN, SIG, (16.5, 22.4), C13['1']); SD('GND', SIG, C13['2'], (16.5, 25.5)); VD('GND', 16.5, 25.5)
SD('GND', SIG, J3['S'], (13.925, 26.6)); VD('GND', 13.925, 26.6)
SD('GND', SIG, J3['R2'], (5.825, 17.2)); VD('GND', 5.825, 17.2)
SD('GND', SIG, TP9, (21.2, 28.0)); VD('GND', 21.2, 28.0)
b.gr_text('LINE OUT', *T(7.0, 29.0), size=1.0)

# ---- pours: Pi-domain GND everywhere except the LED island (x < 21.5, y > 31.5) ----------
b.zone('GND', 'GND_A_top', 0, 0, W, 28.5, priority=1)
b.zone('GND', 'GND_A_right', 24.5, 0, W, H)

# ---- outline, silk -------------------------------------------------------------------
b.outline_rect(radius=3.0)
b.gr_text('chromatone/hat rev A', 32.5, 9.0, layer='B.SilkS', justify=['mirror'])
b.gr_text('PI 40-PIN', 32.5, 7.2, size=1.0)
b.write(PCB)
print('wrote', PCB)
