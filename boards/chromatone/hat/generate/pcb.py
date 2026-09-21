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

# ---- pours: Pi-domain GND everywhere except the LED island (x > 44.5, y > 30) ----------
b.zone('GND', 'GND_A_top', 0, 0, W, 30.0, priority=1)
b.zone('GND', 'GND_A_left', 0, 0, 44.5, H)

# ---- outline, silk -------------------------------------------------------------------
b.outline_rect(radius=3.0)
b.gr_text('chromatone/hat rev A', 32.5, 9.0, layer='B.SilkS', justify=['mirror'])
b.gr_text('PI 40-PIN', 32.5, 7.2, size=1.0)
b.write(PCB)
print('wrote', PCB)
