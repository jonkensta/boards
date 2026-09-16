#!/usr/bin/env python3
"""Write dac.kicad_pcb: 56 x 36 mm. Pi connector right edge, PCM5102A centre, LDO top, jack left edge.

Two audio lines and the XSMT line use the back layer; everything else is on the front.
"""
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, 'boardtools')):
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from boardtools.pcbgen import Board, Netlist, SIG, PWR

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, '..', 'dac.kicad_pcb')
W, H = 56.0, 36.0
b = Board(PCB, Netlist(os.path.join(HERE, 'dac.net')), 'dac.kicad_sch', W, H)
N = lambda ref, pin: b.net.node_net[(ref, pin)]     # net of a pin, from the schematic
S2 = 0.2                                              # signal width where the 0.65 mm pitch forces it
RAIL = 11.0                                           # y of the 3.3 V rail

for i, (hx, hy) in enumerate([(3.5, 3.5), (52.5, 3.5), (3.5, 32.5), (52.5, 32.5)]):
    b.footprint(f'H{i+1}', hx, hy, ref_fab=True); b.keepout(hx, hy)

# ---- placement (pad roles follow the schematic: R pin1 -> J1/OUTx side, pin2 -> U1/filter node) ----
J1 = b.footprint('J1', 51.5, 11.0, 270, ref_pos=(17.5, 0))    # x=51.5: 1 5V 11, 2 GND 13.5, 3 LRCK 16, 4 DIN 18.5, 5 BCK 21, 6 XSMT 23.5
U1 = b.footprint('U1', 37.0, 17.0, 0, ref_pos=(0, 5.0))       # left x=34.1375 pins 1-10 (14.075..19.925); right x=39.8625 pins 20..11 (14.075..19.925)
U2 = b.footprint('U2', 33.0, 6.0, 0, ref_pos=(0, -2.9))       # 1 VIN (31.8625,5.05) 2 GND 3 CE (6.95) | 4 NC 5 VOUT (34.1375,5.05)
J2 = b.footprint('J2', 9.0, 22.0, 0, ref_pos=(0, -6.5))       # T (12.825,18.75) R1 (8.825,18.75) R2 (5.825,18.75) S (13.925,25.25)
R1 = b.footprint('R1', 45.8, 16.0, 180, ref_fab=True)         # 33 R LRCK: pad1 right (46.625) -> J1, pad2 left (44.975) -> U1
R2 = b.footprint('R2', 45.8, 18.5, 180, ref_fab=True)
R3 = b.footprint('R3', 45.8, 21.0, 180, ref_fab=True)
R6 = b.footprint('R6', 37.4, 12.6, 0, ref_fab=True)           # 10k: pad1 (36.575) +3V3, pad2 (38.225) XSMT
C1 = b.footprint('C1', 29.2, 5.6, 180, ref_fab=True)          # 10u LDO in beside VIN: 1 5V (29.975) on the x=30 riser, 2 GND (28.425)
C2 = b.footprint('C2', 36.6, 7.6, 0, ref_fab=True)            # 10u LDO out: 1 3V3 (35.825) 2 GND (37.375)
C3 = b.footprint('C3', 25.4, 13.0, 180, ref_fab=True)         # 10u rail: 1 3V3 (26.175) 2 GND (24.625)
C4 = b.footprint('C4', 25.4, 15.5, 180, ref_fab=True)
C5 = b.footprint('C5', 31.1, 14.725, 180, ref_fab=True)       # 2.2u flying: 1 CAPP (31.875) 2 CAPM (30.325)
C6 = b.footprint('C6', 29.6, 17.6, 270, ref_fab=True)         # 2.2u VNEG: 1 top (29.6,16.825) 2 bottom GND (18.375)
C7 = b.footprint('C7', 42.8, 15.6, 0, ref_fab=True)           # 2.2u LDOO: 1 (42.025,15.6) 2 GND (43.575)
C8 = b.footprint('C8', 16.8, 15.0, 90, ref_fab=True)          # 2.2n L: 1 bottom (16.8,15.775) node, 2 top GND (14.225)
C9 = b.footprint('C9', 16.5, 23.8, 270, ref_fab=True)         # 2.2n R: 1 top (16.5,23.025) node, 2 bottom GND (24.575)
C10 = b.footprint('C10', 31.6, 19.6, 270, ref_fab=True)       # 100n AVDD: 1 top (31.6,18.825) 2 bottom GND (20.375)
C11 = b.footprint('C11', 42.8, 14.075, 0, ref_fab=True)       # 100n DVDD on the DVDD stub: 1 (42.025,14.075), 2 GND (43.575)
C12 = b.footprint('C12', 33.3, 11.9, 270, ref_fab=True)       # 100n CPVDD: 1 top (33.3,11.125) on the rail, 2 bottom GND (12.675)
R4 = b.footprint('R4', 17.8, 17.325, 180, ref_fab=True)       # 470 L: pad1 right (18.625) <- OUTL, pad2 left (16.975) node
R5 = b.footprint('R5', 18.8, 22.4, 180, ref_fab=True)         # 470 R: pad1 right (19.625) <- OUTR, pad2 left (17.975) node
R7 = b.footprint('R7', 23.0, 8.0, 0, ref_fab=True)            # 1k LED: 1 3V3 (22.175) 2 (23.825)
D1 = b.footprint('D1', 26.0, 8.0, 180, ref_fab=True)          # LED: 1 K (26.7875) 2 A (25.2125)
TP1 = b.footprint('TP1', 45.2, 12.4, ref_fab=True, val_pos=(0, -2.0))['1']
TP2 = b.footprint('TP2', 45.2, 24.0, ref_fab=True, val_pos=(0, 2.0))['1']
TP3 = b.footprint('TP3', 20.0, 28.0, ref_fab=True, val_pos=(0, 2.0))['1']
assert U1['1'] == (34.1375, 14.075) and U1['10'] == (34.1375, 19.925) and U1['20'] == (39.8625, 14.075) and U1['15'] == (39.8625, 17.325), U1
assert R1['2'] == (44.975, 16.0) and R4['1'] == (18.625, 17.325) and C5['1'] == (31.875, 14.725) and C6['1'] == (29.6, 16.825), (R1, R4, C5, C6)
assert C10['1'] == (31.6, 18.825) and C12['1'] == (33.3, 11.125) and C8['1'] == (16.8, 15.775) and C9['1'] == (16.5, 23.025), (C10, C12, C8, C9)
assert C11['1'] == (42.025, 14.075) and C1['1'] == (29.975, 5.6), (C11, C1)
for ref, pin, net in (('R1', '2', 'U1'), ('R4', '1', 'U1'), ('C5', '1', 'U1'), ('C7', '1', 'U1')):   # pad roles vs schematic
    assert net in N(ref, pin), (ref, pin, N(ref, pin))

# ---- 5 V in, LDO, 3.3 V rail ---------------------------------------------------------
b.seg('+5V', PWR, J1['1'], (49.5, 9.0), (46.0, 9.0), (44.0, 7.0), (44.0, 4.0), (30.0, 4.0), (30.0, 6.95), U2['3'])
b.seg('+5V', PWR, (30.0, 5.05), U2['1'])
b.seg('+5V', SIG, C1['1'], (30.0, 5.6))
b.seg('GND', SIG, C1['2'], (27.6, 5.6)); b.via('GND', 27.6, 5.6)
b.seg('GND', SIG, U2['2'], (33.0, 6.0)); b.via('GND', 33.0, 6.0)
b.seg('+3V3', PWR, U2['5'], (35.3, 5.05), (35.3, RAIL))
b.seg('+3V3', SIG, C2['1'], (35.3, 7.6)); b.seg('GND', SIG, C2['2'], (38.1, 7.6)); b.via('GND', 38.1, 7.6)
b.seg('+3V3', PWR, (22.175, RAIL), (42.025, RAIL))
b.seg('+3V3', PWR, (27.0, RAIL), (27.0, 23.5), (30.55, 23.5), (30.55, 18.825), C10['1'])  # down the left to AVDD
b.seg('+3V3', SIG, C3['1'], (27.0, 13.0)); b.seg('GND', SIG, C3['2'], (23.8, 13.0)); b.via('GND', 23.8, 13.0)
b.seg('+3V3', SIG, C4['1'], (27.0, 15.5)); b.seg('GND', SIG, C4['2'], (23.8, 15.5)); b.via('GND', 23.8, 15.5)
b.seg('+3V3', SIG, R7['1'], (22.175, RAIL)); b.seg(N('R7', '2'), SIG, R7['2'], D1['2'])
b.seg('GND', SIG, D1['1'], (27.6, 8.0)); b.via('GND', 27.6, 8.0)
# ---- U1 left side: CPVDD CAPP CPGND CAPM VNEG OUTL OUTR AVDD AGND DEMP ----------------
b.seg('+3V3', S2, U1['1'], (34.1, 14.075), (34.1, 11.45), (33.775, 11.125))              # CPVDD to C12 pad1 (on the rail)
b.seg('GND', SIG, C12['2'], (32.85, 13.15)); b.via('GND', 32.85, 13.15)
b.seg(N('U1', '2'), S2, U1['2'], C5['1'])                                               # CAPP
b.seg('GND', S2, U1['3'], (32.9, 15.375)); b.via('GND', 32.9, 15.375)                   # CPGND
b.seg(N('U1', '4'), S2, U1['4'], (30.0, 16.025), (30.0, 15.2))                          # CAPM into C5 pad2 from below
b.seg(N('U1', '5'), S2, U1['5'], (31.5, 16.675), (31.35, 16.825), (30.075, 16.825))     # VNEG into C6 pad1
b.seg('GND', SIG, C6['2'], (29.6, 19.4)); b.via('GND', 29.6, 19.4)
OL, OR_ = N('U1', '6'), N('U1', '7')
b.seg(OL, S2, U1['6'], (32.0, 17.325)); b.via(OL, 32.0, 17.325)                          # OUTL -> B.Cu
b.seg(OR_, S2, U1['7'], (32.85, 17.975)); b.via(OR_, 32.85, 17.975)                      # OUTR -> B.Cu
b.seg('+3V3', S2, U1['8'], (32.6, 18.625), (32.4, 18.825), (32.075, 18.825))            # AVDD into C10 pad1
b.seg('GND', SIG, C10['2'], (31.6, 21.3)); b.via('GND', 31.6, 21.3)
b.seg('GND', S2, U1['9'], (32.9, 19.275), (32.6, 19.5)); b.via('GND', 32.6, 19.5)       # AGND
b.seg('GND', S2, U1['10'], (33.5, 19.925), (33.4, 20.3)); b.via('GND', 33.4, 20.6)      # DEMP
# ---- U1 right side: DVDD DGND LDOO XSMT FMT LRCK DIN BCK SCK FLT ------------------------
b.seg('+3V3', S2, U1['20'], C11['1']); b.seg('+3V3', SIG, C11['1'], (42.025, RAIL))       # DVDD: pin -> C11 -> rail
b.seg('GND', SIG, C11['2'], (44.2, 14.075)); b.via('GND', 44.2, 14.075)
b.seg('GND', S2, U1['19'], (40.9, 14.725)); b.via('GND', 40.9, 14.725)                   # DGND
b.seg(N('U1', '18'), S2, U1['18'], (41.4, 15.375), (41.625, 15.6), C7['1']); b.seg('GND', SIG, C7['2'], (44.0, 15.15)); b.via('GND', 44.0, 15.15)   # LDOO
XS = N('U1', '17')
b.seg(XS, S2, U1['17'], (40.9, 16.025)); b.via(XS, 40.9, 16.025)                          # XSMT -> B.Cu
b.seg(XS, S2, (40.9, 16.025), (40.0, 15.125), (40.0, 13.4), (39.2, 12.6), layer='B.Cu'); b.via(XS, 39.2, 12.6)
b.seg(XS, SIG, (39.2, 12.6), R6['2']); b.seg('+3V3', SIG, R6['1'], (36.575, RAIL))
b.seg(XS, S2, (40.9, 16.025), (39.5, 16.025), (39.5, 25.0), (50.0, 25.0), J1['6'], layer='B.Cu')
b.seg('GND', S2, U1['16'], (40.9, 16.675), (41.6, 16.675)); b.via('GND', 41.6, 16.675)   # FMT
LR, DI, BC = N('U1', '15'), N('U1', '14'), N('U1', '13')
b.seg(LR, S2, U1['15'], (40.9, 17.325), (41.375, 17.8), (43.6, 17.8), (44.975, 16.425), R1['2'])   # LRCK
b.seg(DI, S2, U1['14'], (40.9, 17.975), (41.425, 18.5), R2['2'])                                   # DIN
b.seg(BC, S2, U1['13'], (40.9, 18.625), (43.275, 21.0), R3['2'])                                   # BCK
b.seg('GND', S2, U1['12'], (40.9, 19.275), (40.9, 21.3)); b.via('GND', 40.9, 21.3)                 # SCK
b.seg('GND', S2, U1['11'], (40.9, 19.925))                                                         # FLT joins the SCK stub
b.seg(N('J1', '3'), SIG, R1['1'], J1['3']); b.seg(N('J1', '4'), SIG, R2['1'], J1['4']); b.seg(N('J1', '5'), SIG, R3['1'], J1['5'])
b.seg(LR, SIG, (45.2, 16.0), TP1); b.seg(BC, SIG, (45.2, 21.0), TP2)
# ---- audio out on B.Cu to the filter, jack ------------------------------------------------
b.seg(OL, SIG, (32.0, 17.325), (19.9, 17.325), layer='B.Cu'); b.via(OL, 19.9, 17.325); b.seg(OL, SIG, (19.9, 17.325), R4['1'])
b.seg(OR_, SIG, (32.85, 17.975), (32.85, 18.4), (21.5, 18.4), (20.9, 19.0), (20.9, 22.4), layer='B.Cu'); b.via(OR_, 20.9, 22.4); b.seg(OR_, SIG, (20.9, 22.4), R5['1'])
LN, RN = N('J2', 'T'), N('J2', 'R1')
b.seg(LN, SIG, R4['2'], (16.8, 17.325), (15.375, 18.75), J2['T'])
b.seg(LN, SIG, (16.8, 17.325), C8['1']); b.seg('GND', SIG, C8['2'], (16.8, 13.3)); b.via('GND', 16.8, 13.3)
b.seg(RN, SIG, R5['2'], (16.5, 22.4), (16.5, 20.6), (9.8, 20.6), (9.4, 20.2), (8.825, 20.2), J2['R1'])
b.seg(RN, SIG, (16.5, 22.4), C9['1']); b.seg('GND', SIG, C9['2'], (16.5, 25.5)); b.via('GND', 16.5, 25.5)
b.seg('GND', SIG, J2['S'], (13.925, 26.6)); b.via('GND', 13.925, 26.6)
b.seg('GND', SIG, J2['R2'], (5.825, 17.2)); b.via('GND', 5.825, 17.2)
b.seg('GND', SIG, TP3, (21.2, 28.0)); b.via('GND', 21.2, 28.0)
# ---- pour, outline, silk --------------------------------------------------------------------
b.zone('GND', 'GND', 0, 0, W, H)
b.outline_rect()
b.gr_text('PI I2S', 49.0, 6.8, size=1.0); b.gr_text('LINE OUT', 7.0, 29.0, size=1.0)
for y, lab in zip((11.0, 13.5, 16.0, 18.5, 21.0, 23.5), ('5V', 'GND', 'LRCK', 'DIN', 'BCK', 'XSMT')):
    b.gr_text(lab, 48.3, y, layer='B.SilkS', justify=['left', 'mirror'])
b.gr_text('chromatone/dac rev A', 28.0, 2.2, layer='B.SilkS', justify=['mirror'])
b.write(PCB)
print('wrote', PCB)
