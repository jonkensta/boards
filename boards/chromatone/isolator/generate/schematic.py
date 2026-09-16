#!/usr/bin/env python3
"""Write isolator.kicad_sch: Pi SPI (3.3 V) -> ISO7720 -> SK9822 strip (5 V), two isolated domains."""
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, 'boardtools')):
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from boardtools.schgen import Schematic, g, root_uuid_of

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'isolator.kicad_sch')

R_FP = 'Resistor_SMD:R_0603_1608Metric'; C_FP = 'Capacitor_SMD:C_0603_1608Metric'
LED_FP = 'LED_SMD:LED_0603_1608Metric'; TP_FP = 'TestPoint:TestPoint_Pad_D1.5mm'
JST_FP = 'Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical'; HOLE_FP = 'MountingHole:MountingHole_2.7mm_M2.5'
JST = {'MPN': 'B4B-XH-A(LF)(SN)', 'Manufacturer': 'JST', 'LCSC': 'C144395'}

s = Schematic('isolator', root_uuid_of(OUT), 'Chromatone isolated SPI daughterboard', rev='A', date='2026-09-15',
              comment='Pi Zero 2 W (3.3 V) -> ISO7720 -> SK9822 strip (5 V), galvanically isolated')

# rows (grid units): supply 76, CLK 78, DATA 80, GND 82; stubs to 74 / 84. Everything shifted by -40.
def G(k): return g(k - 40)
Y_VCC, Y_CLK, Y_DATA, Y_GND, Y_TOP, Y_BOT = G(76), G(78), G(80), G(82), G(74), G(84)

U1 = s.place('Isolator', 'ISO7720D', 'U1', G(120), Y_DATA, value='ISO7720D',
             fields={'MPN': 'ISO7720DR', 'Manufacturer': 'Texas Instruments', 'LCSC': 'C486037'},
             prop_pos={'Reference': (-7.62, -9.5), 'Value': (0, 9.5)})
J1 = s.place('Connector', 'Conn_01x04_Pin', 'J1', G(84), Y_CLK, value='Pi SPI', footprint=JST_FP, fields=JST,
             prop_pos={'Reference': (-1.27, -10.2), 'Value': (-1.27, -8.2)})
J2 = s.place('Connector', 'Conn_01x04_Pin', 'J2', G(155), Y_CLK, mirror='y', value='Strip', footprint=JST_FP, fields=JST,
             prop_pos={'Reference': (-4.0, -10.2), 'Value': (-4.0, -8.2)})
# J1: 1 3V3, 2 SCLK, 3 MOSI, 4 GND     U1: 1 VCC1 2 INA 3 INB 4 GND1 | 5 GND2 6 OUTB 7 OUTA 8 VCC2     J2: 1 5V 2 CLK 3 DATA 4 GND
assert J1['2'] == (G(88), Y_CLK) and U1['2'] == (G(112), Y_CLK) and J2['2'] == (G(151), Y_CLK) and U1['7'] == (G(128), Y_CLK)

# domain A
s.wire(J1['1'], (G(90), Y_VCC), (G(90), Y_TOP)); s.power('+3V3', G(90), Y_TOP)
s.wire(J1['4'], (G(90), Y_GND), (G(90), Y_BOT)); s.power('GND', G(90), Y_BOT)
s.wire(U1['1'], (G(110), Y_VCC), (G(110), Y_TOP)); s.power('+3V3', G(110), Y_TOP)
s.wire(U1['4'], (G(110), Y_GND), (G(110), Y_BOT)); s.power('GND', G(110), Y_BOT)
s.wire(J1['2'], (G(98), Y_CLK), U1['2']); s.junction(G(98), Y_CLK)
s.place('Connector', 'TestPoint', 'TP1', G(98), Y_CLK, value='SCLK', footprint=TP_FP, in_bom=False, prop_pos={'Reference': (-2.0, -5.5), 'Value': (-2.0, -3.6)})
s.wire(J1['3'], (G(102), Y_DATA), U1['3']); s.junction(G(102), Y_DATA)
s.place('Connector', 'TestPoint', 'TP2', G(102), Y_DATA, rot=180, value='MOSI', footprint=TP_FP, in_bom=False, prop_pos={'Reference': (-2.0, 6.7), 'Value': (-2.0, 4.8)})
# domain B
s.wire(U1['8'], (G(130), Y_VCC), (G(130), Y_TOP)); s.power('+5V', G(130), Y_TOP, value='+5V_LED')
s.wire(U1['5'], (G(130), Y_GND), (G(130), Y_BOT)); s.power('GNDPWR', G(130), Y_BOT, value='GND_LED')
s.wire(J2['1'], (G(149), Y_VCC), (G(149), Y_TOP)); s.power('+5V', G(149), Y_TOP, value='+5V_LED')
s.wire(J2['4'], (G(149), Y_GND), (G(149), Y_BOT)); s.power('GNDPWR', G(149), Y_BOT, value='GND_LED')
R1 = s.place('Device', 'R', 'R1', G(136), Y_CLK, rot=90, value='47', footprint=R_FP, prop_pos={'Reference': (-3.0, -2.3), 'Value': (3.5, -2.3)})
R2 = s.place('Device', 'R', 'R2', G(136), Y_DATA, rot=90, value='47', footprint=R_FP, prop_pos={'Reference': (-3.0, 2.3), 'Value': (3.5, 2.3)})
s.wire(U1['7'], R1['1']); s.wire(R1['2'], (G(146), Y_CLK), J2['2']); s.junction(G(146), Y_CLK)
s.place('Connector', 'TestPoint', 'TP3', G(146), Y_CLK, value='CLK', footprint=TP_FP, in_bom=False, prop_pos={'Reference': (-2.0, -5.5), 'Value': (-2.0, -3.6)})
s.wire(U1['6'], R2['1']); s.wire(R2['2'], (G(146), Y_DATA), J2['3']); s.junction(G(146), Y_DATA)
s.place('Connector', 'TestPoint', 'TP4', G(146), Y_DATA, rot=180, value='DATA', footprint=TP_FP, in_bom=False, prop_pos={'Reference': (-2.0, 6.7), 'Value': (-2.0, 4.8)})

def cluster(x0, vcc, vname, gnd, gname, cref, rref, dref, led_color, gnd_tp):
    rail_top, rail_bot = G(90), G(100)
    for i, (ref, val, desc) in enumerate([(cref[0], '100n', '100 nF X7R 50 V'), (cref[1], '10u', '10 uF X5R 10 V')]):
        x = G(x0 + i * 8)
        c = s.place('Device', 'C', ref, x, G(95), value=val, footprint=C_FP, description=desc, prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
        s.wire(c['1'], (x, rail_top)); s.wire(c['2'], (x, rail_bot))
        s.power(vcc, x, rail_top, value=vname); s.power(gnd, x, rail_bot, value=gname)
    s.wire((G(x0), rail_top), (G(x0 - 6), rail_top)); s.junction(G(x0), rail_top); s.flag(G(x0 - 6), rail_top)
    s.wire((G(x0), rail_bot), (G(x0 - 6), rail_bot)); s.junction(G(x0), rail_bot); s.flag(G(x0 - 6), rail_bot, rot=180)
    s.junction(G(x0 - 3), rail_bot)
    s.place('Connector', 'TestPoint', gnd_tp[0], G(x0 - 3), rail_bot, rot=180, value=gnd_tp[1], footprint=TP_FP, in_bom=False,
            prop_pos={'Reference': (-2.0, 6.7), 'Value': (-2.0, 4.8)})
    x = G(x0 + 18)
    r = s.place('Device', 'R', rref, x, G(93), value='1k', footprint=R_FP, prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
    d = s.place('Device', 'LED', dref, x, G(101), rot=90, value=led_color, footprint=LED_FP, prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
    s.wire((x, G(88)), r['1']); s.power(vcc, x, G(88), value=vname)
    s.wire(r['2'], d['2']); s.wire(d['1'], (x, G(106))); s.power(gnd, x, G(106), value=gname)

cluster(97, '+3V3', None, 'GND', None, ('C1', 'C2'), 'R3', 'D1', 'GREEN', ('TP5', 'GND_A'))
cluster(136, '+5V', '+5V_LED', 'GNDPWR', 'GND_LED', ('C3', 'C4'), 'R4', 'D2', 'BLUE', ('TP6', 'GND_B'))
for i in range(4):
    s.place('Mechanical', 'MountingHole', f'H{i+1}', G(164 + i * 8), G(98), value='M2.5', footprint=HOLE_FP, in_bom=False,
            prop_pos={'Reference': (-2.0, -3.0), 'Value': (-2.0, -1.0)})

s.box(G(78), G(66), G(116), G(110)); s.box(G(124), G(66), G(160), G(110))
s.text('DOMAIN A: Pi side, 3.3 V, Pi battery', G(78) + 0.5, G(66) - 1, 1.5, True)
s.text('DOMAIN B: LED side, 5 V, LED battery', G(124) + 0.5, G(66) - 1, 1.5, True)
s.text('Isolation barrier: only SPI CLK and DATA cross, A -> B. GND and GND_LED never touch.', G(78) + 0.5, G(114))
s.text('J1 to Pi header: 1=3V3 (pin 1), 2=SCLK (GPIO11), 3=MOSI (GPIO10), 4=GND.', G(78) + 0.5, G(117))
s.text('J2 to pixel 0 of the strip: 1=5V, 2=CI, 3=DI, 4=GND. Tap 5V/GND at the strip end so VCC2 never exceeds the pixel rail.', G(78) + 0.5, G(120))
s.text('R1/R2 tame ringing on the CLK/DATA leads; keep leads to pixel 0 short, twisted with GND_LED.', G(78) + 0.5, G(123))
s.write(OUT)
print('wrote', OUT)
