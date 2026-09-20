#!/usr/bin/env python3
"""Write node.kicad_pcb: 48 x 48 mm, one JST-XH link connector centred on each edge, LEDs in the
middle, RP2040 top-centre with the flash to its left and the crystal to its right, pogo pads
bottom-left, buzzer right, sensor and its header along the bottom, M2 holes in the corners.

Back layer: GND pour plus the 5 V ring and the 3.3 V bus; front: everything else.
"""
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, 'boardtools')):
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from boardtools.pcbgen import Board, Netlist, SIG, PWR

HERE = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(HERE, '..', 'node.kicad_pcb')
W, H = 48.0, 48.0
b = Board(PCB, Netlist(os.path.join(HERE, 'node.net')), 'node.kicad_sch', W, H, copper_layers=4)
N = lambda ref, pin: b.net.node_net[(ref, pin)]     # net of a pin, from the schematic
S2 = 0.2                                              # 0.4 mm pitch escapes
B = 'B.Cu'

for i, (hx, hy) in enumerate([(3.5, 3.5), (44.5, 3.5), (3.5, 44.5), (44.5, 44.5)]):
    b.footprint(f'H{i+1}', hx, hy, ref_fab=True); b.keepout(hx, hy)

# ---- placement ------------------------------------------------------------------------------
# U1 rot 180: GPIO0..12 on the right edge (y 11.2..15.6 top->bottom = SCL..IOVDD), crystal/SWD/RUN on the
# top edge, QSPI + USB + core power on the bottom edge, mostly-NC pins on the left edge.
J1 = b.footprint('J1', 21.5, 3.5, 0, ref_pos=(2.5, 5.5))        # N: pins 21.5 / 24 / 26.5 at y 3.5
J2 = b.footprint('J2', 44.5, 21.5, 270, ref_pos=(-5.5, 2.5))    # E: pins y 21.5 / 24 / 26.5 at x 44.5
J3 = b.footprint('J3', 26.5, 44.5, 180, ref_pos=(-2.5, -5.5))   # S: pins 26.5 / 24 / 21.5 at y 44.5
J4 = b.footprint('J4', 3.5, 26.5, 90, ref_pos=(5.5, -2.5))      # W: pins y 26.5 / 24 / 21.5 at x 3.5
U1 = b.footprint('U1', 12.0, 13.0, 180, ref_pos=(0, 5.2))       # RP2040
U2 = b.footprint('U2', 13.6, 25.4, 90, ref_pos=(-4.6, 0))       # W25Q16 below U1: top row 8 VCC 7 SD3 6 SCLK 5 SD0 (x 11.7..15.5, y 21.8)
Y1 = b.footprint('Y1', 13.7, 4.0, 180, ref_fab=True)            # 3 node (12.6,4.85) 4 GND (14.8,4.85) 2 GND (12.6,3.15) 1 XIN (14.8,3.15)
R1 = b.footprint('R1', 12.6, 7.3, 270, ref_fab=True)            # 1 node (12.6,6.475) 2 XOUT (12.6,8.125)
C2 = b.footprint('C2', 10.1, 4.85, 0, ref_fab=True)             # 1 GND (9.275) 2 node (10.925)
C1 = b.footprint('C1', 17.2, 3.4, 270, ref_fab=True)            # 1 GND (17.2,2.575) 2 XIN (17.2,4.225)
# 3.3 V decoupling (planes: every pad gets a via): C3..C8 IOVDD, C9 USB_VDD, C10 ADC_AVDD, C11 1u VREG_VIN, C12 10u bulk
C3 = b.footprint('C3', 18.0, 16.6, 0, ref_fab=True)             # IOVDD 1 (right edge bottom)
C4 = b.footprint('C4', 18.4, 12.0, 0, ref_fab=True)             # IOVDD 10 (right edge)
C5 = b.footprint('C5', 9.2, 7.9, 0, ref_fab=True)               # IOVDD 22 (top edge, via the left lanes)
C6 = b.footprint('C6', 6.4, 12.4, 90, ref_fab=True)             # IOVDD 33 (left edge)
C7 = b.footprint('C7', 6.4, 15.8, 90, ref_fab=True)             # IOVDD 42 (left edge)
C8 = b.footprint('C8', 8.9, 18.6, 0, ref_fab=True)              # IOVDD 49 / USB_VDD 48 (bottom edge, left of the flash)
C9 = b.footprint('C9', 17.2, 20.0, 0, ref_fab=True)             # USB_VDD
C10 = b.footprint('C10', 6.4, 9.0, 90, ref_fab=True)            # ADC_AVDD 43
C11 = b.footprint('C11', 8.9, 20.4, 0, ref_fab=True)            # VREG_VIN 44 (1u)
C12 = b.footprint('C12', 4.8, 12.4, 90, ref_fab=True)           # bulk 10u
C13 = b.footprint('C13', 17.2, 18.2, 0, ref_fab=True)           # DVDD 1u (VREG_VOUT 45)
C14 = b.footprint('C14', 6.8, 5.6, 90, ref_fab=True)            # DVDD 100n (pin 23, left lanes)
C15 = b.footprint('C15', 8.9, 22.2, 0, ref_fab=True)            # DVDD 100n (pin 50)
C16 = b.footprint('C16', 8.9, 24.0, 0, ref_fab=True)          # flash VCC (pin 8 at 11.7,21.8)
R2 = b.footprint('R2', 8.0, 3.2, 0, ref_fab=True)               # RUN pull-up
R3 = b.footprint('R3', 18.2, 26.8, 90, ref_fab=True)            # QSPI_SS pull-up: 1 3V3 (18,27.825) 2 SS (18,26.175)
# LEDs (rot 180: DIN left, DOUT right), LED supply diode and cap
D2 = b.footprint('D2', 21.5, 24.0, 180, ref_fab=True)           # 3 DIN (20.585,23.45) 1 DOUT (22.415,24.55) 4 VDD (20.585,24.55) 2 GND (22.415,23.45)
D4 = b.footprint('D4', 25.5, 24.0, 180, ref_fab=True)
D1 = b.footprint('D1', 19.9, 20.3, 90, ref_fab=True)            # 1N4148W: 1 K LED_VDD (19.9,21.95) 2 A +5V (19.9,18.65)
C19 = b.footprint('C19', 21.5, 27.0, 0, ref_fab=True)           # LED_VDD cap
# buzzer right of centre, driver left of it
BZ1 = b.footprint('BZ1', 34.2, 30.5, 90, ref_pos=(0, -10.0))    # 1 +5V (34.2,30.5) 2 drain (34.2,22.9); body centre (34.2,26.7) r 6
Q1 = b.footprint('Q1', 25.5, 28.5, 0, ref_fab=True)             # 2N7002: 1 G (24.56,27.55) 2 S (24.56,29.45) 3 D (26.44,28.5)
R17 = b.footprint('R17', 22.8, 30.0, 90, ref_fab=True)          # 1k gate: 1 BUZZ (22.8,30.825) 2 G (22.8,29.175)
R18 = b.footprint('R18', 25.5, 31.0, 0, ref_fab=True)           # 100k pull-down: 1 G (24.675) 2 GND (26.325)
D3 = b.footprint('D3', 34.2, 19.0, 180, ref_fab=True)           # flyback: 1 K +5V (35.85) 2 A drain (32.55)
# LDO top-right
U4 = b.footprint('U4', 34.2, 4.2, 0, ref_pos=(0, -3.0))         # 1 VIN (33.06,3.25) 2 GND (33.06,4.2) 3 CE (33.06,5.15) 4 NC 5 VOUT (35.34,3.25)
C17 = b.footprint('C17', 38.6, 4.2, 90, ref_fab=True)           # 10u in
C18 = b.footprint('C18', 39.6, 8.6, 0, ref_fab=True)            # 10u out
# links: 100 R series near the connector, 4k7 pull-up beside it
R7 = b.footprint('R7', 27.6, 8.9, 0, ref_fab=True)              # N: 1 LINK_N (26.775) 2 J1 (28.425)
R8 = b.footprint('R8', 30.6, 8.9, 180, ref_fab=True)            # N pull-up: 2 LINK_N (29.775) 1 3V3 (31.425)
R9 = b.footprint('R9', 39.0, 14.4, 270, ref_fab=True)           # E: 1 LINK_E (39,13.575) 2 J2 (39,15.225)
R10 = b.footprint('R10', 39.0, 11.4, 90, ref_fab=True)          # E pull-up: 2 LINK_E (39,10.575) 1 3V3 (39,12.225)
R11 = b.footprint('R11', 22.0, 34.2, 270, ref_fab=True)         # S: 1 LINK_S (24,33.375) 2 J3 (24,35.025)
R12 = b.footprint('R12', 19.4, 33.0, 90, ref_fab=True)           # S pull-up: 1 3V3 (20.375) 2 LINK_S (22.025)
R13 = b.footprint('R13', 8.9, 27.6, 180, ref_fab=True)          # W: 1 LINK_W (9.725) 2 J4 (8.075)
R14 = b.footprint('R14', 8.9, 25.8, 0, ref_fab=True)            # W pull-up: 1 3V3 (8.075) 2 LINK_W (9.725)
# pogo pads bottom-left, USB series resistors above them
J6 = b.footprint('J6', 12.5, 36.0, 90, ref_pos=(0, -6.5))       # even row y 33.475: 2 SWDIO 8.69, 4 SWCLK 11.23, 6 RUN 13.77, 8 BOOT 16.31; odd row y 38.525: 1 DP, 3 DM, 5 GND, 7 +5V
R15 = b.footprint('R15', 8.9, 29.3, 0, ref_fab=True)           # 27 R: 1 J6 pin 1 (9.8,29.425) 2 USB_DP (9.8,27.775)
R16 = b.footprint('R16', 18.2, 29.3, 0, ref_fab=True)           # 27 R: 1 J6 pin 3 (8.2,31.425) 2 USB_DM (8.2,29.775)
# sensor block and header along the bottom
U3 = b.footprint('U3', 30.0, 34.6, 0, ref_pos=(0, -2.7))        # VL53L0X
C20 = b.footprint('C20', 33.6, 34.6, 90, ref_fab=True)
C21 = b.footprint('C21', 35.6, 34.6, 90, ref_fab=True)
R4 = b.footprint('R4', 24.5, 34.8, 0, ref_fab=True)             # SDA pull-up: 1 3V3 (24.675) 2 SDA (26.325)
R5 = b.footprint('R5', 26.75, 34.2, 90, ref_fab=True)             # SCL pull-up
R6 = b.footprint('R6', 24.5, 33.0, 0, ref_fab=True)             # SENS_INT pull-up
J5 = b.footprint('J5', 20.73, 38.6, 90, ref_pos=(7.6, 2.6))     # pins x 20.73 + 2.54 k (1 +5V .. 7 GND); gap at x = 22 for the J3 data trace
SW1 = b.footprint('SW1', 42.0, 33.5, 0, ref_fab=True, val_pos=(0, -3.6))   # vib variant, DNP
C22 = b.footprint('C22', 38.4, 33.5, 90, ref_fab=True)

if __name__ == '__main__' and '--pads' in sys.argv:
    for ref in ('U1', 'U2', 'Y1', 'J6', 'U3', 'J5', 'BZ1', 'Q1', 'U4', 'D2', 'D4', 'D1', 'R9', 'R10', 'R11', 'R12', 'R13', 'R14', 'R15', 'R16'):
        print(ref, {k: v for k, v in globals()[ref].items() if not k.isdigit() or int(k) <= 60})

b.zone('GND', 'GND', 0, 0, W, H, layer='In1.Cu')
b.zone('+3V3', '3V3', 0, 0, W, H, layer='In2.Cu')
b.zone('GND', 'GND-B', 0, 0, W, H, layer='B.Cu')
b.outline_rect()
b.write(PCB)
print('wrote', PCB)
