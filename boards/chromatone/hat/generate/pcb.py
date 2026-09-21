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
J1 = b.footprint('J1', 8.37, 4.77, 270, ref_fab=True, side='B', solid_pads=('25',))   # its pour sliver is an island (BCK run)
assert J1['1'] == (8.37, 4.77) and J1['2'] == (8.37, 2.23) and J1['3'] == (10.91, 4.77) and J1['40'] == (56.63, 2.23), J1
HP = lambda n: J1[str(n)]                            # header pin -> board position

# header power: 5V pins 2+4 joined; 3V3 pins 1+17 linked on the front just under the pad row
b.seg('+5V', PWR, HP(2), HP(4))
b.seg('+3V3', PWR, HP(1), (8.37, 6.4), (28.69, 6.4), HP(17))

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
TP7 = b.footprint('TP7', 42.5, 11.3, ref_fab=True, val_pos=(0, -2.0))['1']     # LRCK, west of R5
TP8 = b.footprint('TP8', 55.0, 11.3, ref_fab=True, val_pos=(0, -2.0))['1']     # BCK, east of R7
TP9 = FD('TP9', 20.0, 28.0, ref_fab=True, val_pos=(2.0, 0))['1']   # Pt               # GND
def near(a, b): return abs(a[0] - b[0]) < 1e-3 and abs(a[1] - b[1]) < 1e-3
assert near(U2['1'], T(34.1375, 14.075)) and near(U2['15'], T(39.8625, 17.325)) and near(R5['2'], T(44.975, 16.0)), (U2, R5)
assert near(R7['1'], (53.0, 9.875)) and near(R7['2'], (53.0, 11.525)) and near(C9['1'], T(31.875, 14.725)), (R7, C9)
for ref, pin, net in (('R5', '2', 'U2'), ('R8', '1', 'U2'), ('C9', '1', 'U2'), ('C11', '1', 'U2')):   # pad roles vs schematic
    assert net in N(ref, pin), (ref, pin, N(ref, pin))

# LDO -> 3.3 V rail (5 V arrives at old (30, 4) = new (35, 26.5) from the header escapes)
SD('+5V', PWR, (30.0, 4.4), (30.0, 6.95), U3['3'])      # (30, 4.4) = the 5 V via at (35.4, 26.5)
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

# ======================================================================================
# Header escapes for the DAC. 5V and BCK leave their THT pads on the back (5V down the west
# side, BCK east along y = 6.3 under the socket); LRCK/DIN/XSMT on the front.
# ======================================================================================
b.seg('+5V', PWR, HP(4), (12.18, 3.5), (12.18, 25.23), (13.45, 26.5), (35.4, 26.5), layer='B.Cu'); b.via('+5V', 35.4, 26.5)
b.seg(BC, SIG, HP(12), (22.34, 3.5), (22.34, 6.3), (56.7, 6.3), (57.9, 7.5), layer='B.Cu'); b.via(BC, 57.9, 7.5)
b.seg(BC, SIG, (57.9, 7.5), (57.9, 9.275), (57.3, 9.875), R7['1'])
b.seg(DI, SIG, HP(40), (55.36, 3.5), (55.36, 5.9), (51.385, 9.875), R6['1'])
b.seg(LR, SIG, HP(35), (51.55, 5.9), (47.575, 9.875), R5['1'])
b.seg(XS, SIG, HP(29), (43.93, 9.5)); b.via(XS, 43.93, 9.5)                       # hop under the DAC rail to the XSMT via
b.seg(XS, SIG, (43.93, 9.5), (43.93, 16.97), (43.6, 17.3), layer='B.Cu')
b.seg('GND', SIG, HP(25), (38.85, 9.0)); b.via('GND', 38.85, 9.0)                  # pad 25's pour sliver is cut off by the BCK run

# ======================================================================================
# Isolator block: chromatone/isolator rev A geometry rotated 180 deg into the bottom left,
# R(x, y) = (46 - x, 56 - y), footprint rotations gain 180. Refs are unchanged. The LED island
# is x < 21.5, y > 31.5 with J2 on the left edge; U1 sits on the vertical 3 mm barrier at
# x = 23. The old Pi connector (J1) is replaced by feeds from header pins 17/19/23. R3/D1
# (3V3 LED) and TP2/TP5 move out of the way of those feeds.
# ======================================================================================
def R(x, y): return (46.0 - x, 56.0 - y)
def FI(ref, x, y, rot=0, **kw): return {k: Pt(v) for k, v in b.footprint(ref, *R(x, y), (rot + 180) % 360, **kw).items()}
def SI(net, w, *pts, layer='F.Cu'): b.seg(net, w, *[p if isinstance(p, Pt) else R(*p) for p in pts], layer=layer)
def VI(net, x, y): b.via(net, *R(x, y))
def FN(ref, x, y, rot=0, **kw): return {k: Pt(v) for k, v in b.footprint(ref, x, y, rot, **kw).items()}
V5L, GL = '+5V_LED', 'GND_LED'

J2 = FI('J2', 41.5, 10.5, 270, ref_pos=(11.5, 0))     # strip: 1 5V (4.5, 45.5) 2 CI 43 3 DI 40.5 4 GND 38
U1 = FI('U1', 23.0, 16.0, 0, ref_pos=(-4.0, 4.7))     # ISO7720: pins 1-4 (Pi side) at x = 25.475, 5-8 at 20.525
C1 = FI('C1', 18.5, 13.32, 90, ref_fab=True)          # 100n VCC1
C2 = FI('C2', 17.0, 9.9, 0, ref_fab=True)             # 10u 3V3
C3 = FI('C3', 27.5, 13.32, 90, ref_fab=True)          # 100n VCC2
C4 = FI('C4', 29.0, 9.9, 180, ref_fab=True)           # 10u 5V_LED
R1 = FI('R1', 31.0, 15.365, 0, ref_fab=True)          # 47 R CLK
R2 = FI('R2', 31.0, 17.8, 0, ref_fab=True)            # 47 R DATA
R4 = FI('R4', 32.5, 23.5, 180, ref_fab=True)          # 1k LED B
D2 = FI('D2', 28.5, 23.5, 0, ref_fab=True)            # blue LED
R3 = FN('R3', 32.5, 51.5, 0, ref_fab=True)            # 1k LED A (moved below C2): pad1 west 3V3, pad2 east
D1 = FN('D1', 36.5, 51.5, 180, ref_fab=True)          # green LED: pad1 K east, pad2 A west
TP = {}
for ref, x, y, dy in [('TP3', 34.0, 11.0, -2.0), ('TP4', 35.0, 21.5, -2.0), ('TP6', 31.5, 20.0, 2.0)]:
    TP[ref] = FI(ref, x, y, ref_fab=True, val_pos=(0, dy))['1']
TP['TP1'] = FN('TP1', 33.5, 46.0, ref_fab=True, val_pos=(0, 2.0))['1']    # SCLK, below the SCLK column end
TP['TP2'] = FN('TP2', 32.0, 34.0, ref_fab=True, val_pos=(0, -2.0))['1']   # MOSI, on the MOSI column
TP['TP5'] = FN('TP5', 37.5, 37.0, ref_fab=True, val_pos=(-3.0, 0))['1']   # GND_A
assert near(U1['1'], (25.475, 41.905)) and near(U1['8'], (20.525, 41.905)) and near(J2['1'], (4.5, 45.5)) and near(C1['1'], R(18.5, 14.095)), (U1, J2, C1)
assert near(R3['1'], (31.675, 51.5)) and 'D1' in N('D1', '2') and N('D1', '1') == 'GND' and N('R3', '1') == '+3V3', (R3, N('D1', '2'))
SK, MO = N('U1', '2'), N('U1', '3')
CK, DA = N('J2', '2'), N('J2', '3')
# domain A (as before, minus the connector stubs)
SI('+3V3', PWR, (16.225, 8.0), C2['1'], (16.225, 14.095), U1['1'])
SI('GND', SIG, C2['2'], (19.2, 9.9)); VI('GND', 19.2, 9.9)
SI('GND', SIG, C1['2'], (18.5, 11.3)); VI('GND', 18.5, 11.3)
SI('GND', SIG, U1['4'], (18.75, 17.905)); VI('GND', 18.75, 17.905)
SI(SK, SIG, (12.0, 13), (14.365, 15.365), U1['2'])
b.seg(SK, SIG, (34.0, 43.0), (33.5, 43.5), TP['TP1'])
b.seg('GND', SIG, TP['TP5'], (37.5, 38.5)); b.via('GND', 37.5, 38.5)
# domain B
SI(V5L, PWR, J2['1'], (41.5, 8.0), (29.775, 8.0), C4['1'], (29.775, 14.095), U1['8'])
SI(V5L, PWR, J2['1'], (43.5, 12.5), (43.5, 19.5), (39.5, 23.5), R4['1'])
SI(GL, SIG, C4['2'], (26.8, 9.9)); VI(GL, 26.8, 9.9)
SI(GL, SIG, C3['2'], (27.5, 11.3)); VI(GL, 27.5, 11.3)
SI(GL, SIG, U1['5'], (27.25, 17.905)); VI(GL, 27.25, 17.905)
SI(GL, SIG, D2['1'], (26.2, 23.5)); VI(GL, 26.2, 23.5)
SI(GL, SIG, TP['TP6'], (30.0, 20.0)); VI(GL, 30.0, 20.0)
SI(N('U1', '7'), SIG, U1['7'], R1['1'])
SI(CK, SIG, R1['2'], (38.5, 15.365), (40.865, 13.0), J2['2'])
SI(CK, SIG, (34.0, 15.365), TP['TP3'])
SI(N('U1', '6'), SIG, U1['6'], (28.5, 16.635), (29.665, 17.8), R2['1'])
SI(DA, SIG, R2['2'], (38.5, 17.8), (40.8, 15.5), J2['3'])
SI(DA, SIG, (35.0, 17.8), TP['TP4'])
SI(N('D2', '2'), SIG, D2['2'], R4['2'])
# 3V3 LED pair below C2, fed from the 3V3 column
b.seg(N('R3', '2'), SIG, R3['2'], D1['2']); b.seg('GND', SIG, D1['1'], (38.5, 51.5)); b.via('GND', 38.5, 51.5)
# feeds from the header: MOSI pin 19 (31.23) and SCLK pin 23 (36.31) as columns at x 32 / 34, 3V3 pin 17 (28.69) east of them at x 35.5
b.seg('+3V3', PWR, HP(17), (28.69, 9.0)); b.via('+3V3', 28.69, 9.0)                       # hop under the MOSI/SCLK columns
b.seg('+3V3', PWR, (28.69, 9.0), (35.5, 9.0), layer='B.Cu'); b.via('+3V3', 35.5, 9.0)
b.seg('+3V3', PWR, (35.5, 9.0), (35.5, 19.5), (34.6, 20.4), (34.6, 28.5), (35.5, 29.4), (35.5, 48.0), (29.775, 48.0))   # jog west past the LDO
b.seg('+3V3', SIG, (31.675, 48.0), (31.675, 51.5))
b.seg(MO, SIG, HP(19), (31.23, 6.5), (32.0, 7.27), (32.0, 37.5), (30.135, 39.365), U1['3'])
b.seg(SK, SIG, HP(23), (36.31, 7.0), (34.0, 9.31), (34.0, 43.0))
# island pour, barrier silk, labels
b.zone(GL, 'GND_B', 0, 31.5, 21.5, H)
for layer in ('F.SilkS', 'B.SilkS'):
    b.gr_line(23.0, 30.0, 23.0, 35.0, layer, 0.15); b.gr_line(23.0, 44.5, 23.0, 52.5, layer, 0.15)
    b.gr_line(0.5, 30.0, 23.0, 30.0, layer, 0.15)
b.gr_text('LED  5V', 13.0, 55.0, size=1.0); b.gr_text('ISOLATED', 23.0, 55.0)
for y, lab in zip((45.5, 43.0, 40.5, 38.0), ('5V', 'CI', 'DI', 'GND')):
    b.gr_text(lab, 9.0, y, justify=['left'])

# ======================================================================================
# HAT ID EEPROM (all DNP) in the left-centre. 3V3 rail at y = 12 tapped off the pin 1/17 link;
# ID_SD/ID_SC drop from pins 27/28 to vias, run west on the back under the SPI columns, come up
# beside U4 with their pull-ups on the run; WP has its pull-up and the solder jumper to GND.
# SOIC-8: left pins 1-4 top-down (A0 A1 A2 GND), right pins 8-5 top-down (VCC WP SCL SDA).
# ======================================================================================
U4 = FN('U4', 18.0, 17.0, 0, ref_pos=(0, 4.0))
C17 = FN('C17', 13.2, 13.0, 270, ref_fab=True)         # pad1 top on the rail, pad2 bottom to the GND join
R12 = FN('R12', 25.5, 18.905, 180, ref_fab=True)       # 3.9k: pad2 west = SDA, pad1 east = 3V3
R13 = FN('R13', 28.5, 17.635, 180, ref_fab=True)       # 3.9k: pad2 west = SCL, pad1 east = 3V3 (east of R12/R14)
R14 = FN('R14', 25.5, 16.365, 0, ref_fab=True)         # 10k: pad1 west = WP, pad2 east = 3V3
JP1 = FN('JP1', 23.8, 13.6, 0, ref_fab=True)
if JP1['1'][0] > JP1['2'][0]:                           # want the GND pad (A) on the west
    b.items.pop(); JP1 = FN('JP1', 23.8, 13.6, 180, ref_fab=True)
SD_, SC_, WP_ = N('U4', '5'), N('U4', '6'), N('U4', '7')
assert near(U4['8'], (20.475, 15.095)) and near(U4['5'], (20.475, 18.905)) and near(U4['4'], (15.525, 18.905)), U4
assert N('R12', '2') == SD_ and N('R13', '2') == SC_ and N('R14', '1') == WP_ and N('JP1', '2') == WP_ and N('C17', '1') == '+3V3', (SD_, SC_, WP_)
assert near(R12['1'], (26.325, 18.905)) and near(R14['1'], (24.675, 16.365)) and near(R13['2'], (27.675, 17.635)) and near(C17['1'], (13.2, 12.225)), (R12, R14, R13, C17)
jpb, jpa = JP1['2'], JP1['1']
# 3V3 rail and the pull-up column
b.seg('+3V3', SIG, (13.0, 6.4), (13.0, 12.0), (29.325, 12.0), R13['1'])
b.seg('+3V3', SIG, R14['2'], (26.325, 12.0)); b.seg('+3V3', SIG, R12['1'], (29.325, 18.905), (29.325, 17.635))
b.seg('+3V3', SIG, U4['8'], (20.475, 12.0))
# grounds: A0-A2 + GND pin joined at x = 14.6, C17 onto that join, one via
for pin in ('1', '2', '3', '4'):
    b.seg('GND', SIG, U4[pin], (14.6, U4[pin][1]))
b.seg('GND', SIG, (14.6, 15.095), (14.6, 18.905)); b.seg('GND', SIG, (14.6, 17.0), (14.0, 17.0)); b.via('GND', 14.0, 17.0)
b.seg('GND', SIG, C17['2'], (13.2, 14.4), (13.895, 15.095), (14.6, 15.095))
# WP: pin 7 east through the jumper tap to R14
b.seg(WP_, SIG, U4['7'], R14['1']); b.seg(WP_, SIG, jpb, (jpb[0], 16.365))
b.seg('GND', SIG, jpa, (jpa[0], 12.9)); b.via('GND', jpa[0], 12.9)
# ID_SD (pin 27) and ID_SC (pin 28)
b.seg(SD_, SIG, HP(27), (41.39, 7.6)); b.via(SD_, 41.39, 7.6)
b.seg(SD_, SIG, (41.39, 7.6), (41.39, 11.0), (24.4, 11.0), (24.4, 18.905), layer='B.Cu'); b.via(SD_, 24.4, 18.905)
b.seg(SD_, SIG, U4['5'], (24.4, 18.905), R12['2'])
b.seg(SC_, SIG, HP(28), (40.12, 3.5), (40.12, 7.2)); b.via(SC_, 40.12, 7.2)
b.seg(SC_, SIG, (40.12, 7.2), (40.12, 10.3), (22.3, 10.3), (22.3, 17.635), layer='B.Cu'); b.via(SC_, 22.3, 17.635)
b.seg(SC_, SIG, U4['6'], (22.3, 17.635), R13['2'])
b.gr_text('ID EEPROM (DNP)', 18.0, 23.5)

# ---- pours: Pi-domain GND everywhere except the LED island (x < 21.5, y > 31.5) ----------
b.zone('GND', 'GND_A_top', 0, 0, W, 28.5, priority=1)
b.zone('GND', 'GND_A_right', 24.5, 0, W, H)

# ---- outline, silk -------------------------------------------------------------------
b.outline_rect(radius=3.0)
b.gr_text('chromatone/hat rev A', 32.5, 9.0, layer='B.SilkS', justify=['mirror'])
b.gr_text('PI 40-PIN', 32.5, 7.2, size=1.0)
b.write(PCB)
print('wrote', PCB)
