#!/usr/bin/env python3
"""Write isolator.kicad_pcb: 46 x 30 mm, connectors on the short edges, 3 mm barrier under U1."""
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, 'boardtools')):
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from boardtools.pcbgen import Board, Netlist, SIG, PWR

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, '..', 'isolator.kicad_pcb')
W, H = 46.0, 30.0
b = Board(PCB, Netlist(os.path.join(HERE, 'isolator.net')), 'isolator.kicad_sch', W, H)

for i, (hx, hy) in enumerate([(3.5, 3.5), (42.5, 3.5), (3.5, 26.5), (42.5, 26.5)]):
    b.footprint(f'H{i+1}', hx, hy, ref_fab=True); b.keepout(hx, hy)
J1 = b.footprint('J1', 4.5, 10.5, 270, ref_pos=(11.5, 0))     # 1 3V3 (4.5,10.5) 2 SCLK 13 3 MOSI 15.5 4 GND 18
J2 = b.footprint('J2', 41.5, 10.5, 270, ref_pos=(11.5, 0))    # 1 5V 2 CLK 3 DATA 4 GND
U1 = b.footprint('U1', 23.0, 16.0, 0, ref_pos=(-4.0, 4.7))    # 1-4 x=20.525 (y 14.095..17.905), 5-8 x=25.475 reversed
C1 = b.footprint('C1', 18.5, 13.32, 90, ref_fab=True)         # 1 +3V3 beside U1.1, 2 GND
C2 = b.footprint('C2', 17.0, 9.9, 0, ref_fab=True)            # 1 +3V3, 2 GND
C3 = b.footprint('C3', 27.5, 13.32, 90, ref_fab=True)         # 1 +5V_LED beside U1.8, 2 GND_LED
C4 = b.footprint('C4', 29.0, 9.9, 180, ref_fab=True)          # 1 +5V_LED, 2 GND_LED
R1 = b.footprint('R1', 31.0, 15.365, 0, ref_fab=True)
R2 = b.footprint('R2', 31.0, 17.8, 0, ref_fab=True)
R3 = b.footprint('R3', 13.5, 23.5, 0, ref_fab=True)
D1 = b.footprint('D1', 17.5, 23.5, 180, ref_fab=True)         # 1 K, 2 A
R4 = b.footprint('R4', 32.5, 23.5, 180, ref_fab=True)
D2 = b.footprint('D2', 28.5, 23.5, 0, ref_fab=True)
TP = {}
for ref, x, y, dy in [('TP1', 11.5, 10.0, -2.0), ('TP2', 10.0, 20.5, 2.0), ('TP3', 34.0, 11.0, -2.0), ('TP4', 35.0, 21.5, 2.0),
                      ('TP5', 14.5, 20.0, 2.0), ('TP6', 31.5, 20.0, 2.0)]:
    TP[ref] = b.footprint(ref, x, y, ref_fab=True, val_pos=(0, dy))['1']
assert J1['1'] == (4.5, 10.5) and U1['1'] == (20.525, 14.095) and U1['8'] == (25.475, 14.095) and C1['1'] == (18.5, 14.095), (J1, U1, C1)

# domain A
b.seg('+3V3', PWR, J1['1'], (4.5, 8.0), (16.225, 8.0), C2['1'], (16.225, 14.095), U1['1'])
b.seg('+3V3', PWR, J1['1'], (2.5, 12.5), (2.5, 19.5), (6.5, 23.5), R3['1'])
b.seg('GND', SIG, C2['2'], (19.2, 9.9)); b.via('GND', 19.2, 9.9)
b.seg('GND', SIG, C1['2'], (18.5, 11.3)); b.via('GND', 18.5, 11.3)
b.seg('GND', SIG, U1['4'], (18.75, 17.905)); b.via('GND', 18.75, 17.905)
b.seg('GND', SIG, D1['1'], (19.8, 23.5)); b.via('GND', 19.8, 23.5)
b.seg('GND', SIG, TP['TP5'], (16.0, 20.0)); b.via('GND', 16.0, 20.0)
b.seg('Net-(J1-Pin_2)', SIG, J1['2'], (12.0, 13), (14.365, 15.365), U1['2'])
b.seg('Net-(J1-Pin_2)', SIG, (11.5, 13), TP['TP1'])
b.seg('Net-(J1-Pin_3)', SIG, J1['3'], (6.0, 15.5), (7.135, 16.635), U1['3'])
b.seg('Net-(J1-Pin_3)', SIG, (10.0, 16.635), TP['TP2'])
b.seg('Net-(D1-A)', SIG, R3['2'], D1['2'])
# domain B
b.seg('+5V_LED', PWR, J2['1'], (41.5, 8.0), (29.775, 8.0), C4['1'], (29.775, 14.095), U1['8'])
b.seg('+5V_LED', PWR, J2['1'], (43.5, 12.5), (43.5, 19.5), (39.5, 23.5), R4['1'])
b.seg('GND_LED', SIG, C4['2'], (26.8, 9.9)); b.via('GND_LED', 26.8, 9.9)
b.seg('GND_LED', SIG, C3['2'], (27.5, 11.3)); b.via('GND_LED', 27.5, 11.3)
b.seg('GND_LED', SIG, U1['5'], (27.25, 17.905)); b.via('GND_LED', 27.25, 17.905)
b.seg('GND_LED', SIG, D2['1'], (26.2, 23.5)); b.via('GND_LED', 26.2, 23.5)
b.seg('GND_LED', SIG, TP['TP6'], (30.0, 20.0)); b.via('GND_LED', 30.0, 20.0)
b.seg('Net-(U1-OUTA)', SIG, U1['7'], R1['1'])
b.seg('Net-(J2-Pin_2)', SIG, R1['2'], (38.5, 15.365), (40.865, 13.0), J2['2'])
b.seg('Net-(J2-Pin_2)', SIG, (34.0, 15.365), TP['TP3'])
b.seg('Net-(U1-OUTB)', SIG, U1['6'], (28.5, 16.635), (29.665, 17.8), R2['1'])
b.seg('Net-(J2-Pin_3)', SIG, R2['2'], (38.5, 17.8), (40.8, 15.5), J2['3'])
b.seg('Net-(J2-Pin_3)', SIG, (35.0, 17.8), TP['TP4'])
b.seg('Net-(D2-A)', SIG, D2['2'], R4['2'])
# pours: split grounds, 3 mm barrier under U1
b.zone('GND', 'GND_A', 0, 0, 21.5, H)
b.zone('GND_LED', 'GND_B', 24.5, 0, W, H)
# outline, silk
b.outline_rect()
for layer in ('F.SilkS', 'B.SilkS'):
    b.gr_line(23.0, 4.0, 23.0, 11.5, layer, 0.15); b.gr_line(23.0, 21.0, 23.0, 26.0, layer, 0.15)
b.gr_text('PI  3.3V', 12.0, 2.2, size=1.0); b.gr_text('LED  5V', 34.0, 2.2, size=1.0); b.gr_text('ISOLATED', 23.0, 27.8)
for y, lab in zip((10.5, 13, 15.5, 18), ('3V3', 'SCLK', 'MOSI', 'GND')):
    b.gr_text(lab, 7.7, y, justify=['left'])
for y, lab in zip((10.5, 13, 15.5, 18), ('5V', 'CI', 'DI', 'GND')):
    b.gr_text(lab, 37.4, y, justify=['right'])
b.gr_text('chromatone/isolator rev A', 23.0, 2.2, layer='B.SilkS', justify=['mirror'])
b.write(PCB)
print('wrote', PCB)
