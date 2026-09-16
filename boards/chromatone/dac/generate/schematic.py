#!/usr/bin/env python3
"""Write dac.kicad_sch: Pi I2S (3.3 V) -> PCM5102A -> 3.5 mm line out, 3.3 V LDO from the Pi's 5 V."""
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, 'boardtools')):
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from boardtools.schgen import Schematic, g, root_uuid_of

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'dac.kicad_sch')

R_FP = 'Resistor_SMD:R_0603_1608Metric'; C_FP = 'Capacitor_SMD:C_0603_1608Metric'
LED_FP = 'LED_SMD:LED_0603_1608Metric'; TP_FP = 'TestPoint:TestPoint_Pad_D1.5mm'
JST_FP = 'Connector_JST:JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical'; HOLE_FP = 'MountingHole:MountingHole_2.7mm_M2.5'
JACK_FP = 'Connector_Audio:Jack_3.5mm_PJ320D_Horizontal'
JST = {'MPN': 'B6B-XH-A(LF)(SN)', 'Manufacturer': 'JST', 'LCSC': 'C144397'}
PARTS = {   # JLCPCB parts (checked on jlcpcb.com/partdetail, 2026-09-16); all basic except the LED
    '10u': {'MPN': 'CL10A106MA8NRNC', 'Manufacturer': 'Samsung', 'LCSC': 'C96446'},      # 10 uF 25 V X5R 0603
    '2.2u': {'MPN': 'CL10A225KO8NNNC', 'Manufacturer': 'Samsung', 'LCSC': 'C23630'},     # 2.2 uF 16 V X5R 0603
    '100n': {'MPN': 'CC0603KRX7R9BB104', 'Manufacturer': 'Yageo', 'LCSC': 'C14663'},   # 100 nF 50 V X7R 0603
    '2.2n': {'MPN': '0603B222K500NT', 'Manufacturer': 'Fenghua', 'LCSC': 'C1604'},      # 2.2 nF 50 V X7R 0603 (basic; no C0G basic in 0603)
    '33': {'MPN': '0603WAF330JT5E', 'Manufacturer': 'Uniroyal', 'LCSC': 'C23140'},
    '470': {'MPN': '0603WAF4700T5E', 'Manufacturer': 'Uniroyal', 'LCSC': 'C23179'},
    '10k': {'MPN': '0603WAF1002T5E', 'Manufacturer': 'Uniroyal', 'LCSC': 'C25804'},
    '1k': {'MPN': '0603WAF1001T5E', 'Manufacturer': 'Uniroyal', 'LCSC': 'C21190'},
    'GREEN': {'MPN': '19-217/GHC-YR1S2/3T', 'Manufacturer': 'Everlight', 'LCSC': 'C72043'},   # extended
}


s = Schematic('dac', root_uuid_of(OUT), 'Chromatone I2S DAC (experiment)', rev='A', date='2026-09-16',
              comment='Pi Zero 2 W I2S -> PCM5102A -> 2.1 Vrms line out; 3.3 V from the Pi 5 V via LDO')

def TPT(ref, x, y, name):   # test point, body above
    s.place('Connector', 'TestPoint', ref, x, y, value=name, footprint=TP_FP, in_bom=False, prop_pos={'Reference': (-2.0, -5.5), 'Value': (-2.0, -3.6)})
def TPB(ref, x, y, name):   # body below
    s.place('Connector', 'TestPoint', ref, x, y, rot=180, value=name, footprint=TP_FP, in_bom=False, prop_pos={'Reference': (-2.0, 6.7), 'Value': (-2.0, 4.8)})

# ---- PCM5102A -------------------------------------------------------------------
U1 = s.place('Audio', 'PCM5102A', 'U1', g(100), g(90), value='PCM5102A',
             fields={'MPN': 'PCM5102APWR', 'Manufacturer': 'Texas Instruments', 'LCSC': 'C107671'},
             prop_pos={'Reference': (-10.16, -17.5), 'Value': (10.16, -17.5)})
# pins (sheet coords): left x=114.3: LRCK 104.14, DIN 106.68, BCK 109.22, SCK 111.76, FLT 116.84, DEMP 119.38, XSMT 121.92, FMT 124.46
#                      right x=139.7: OUTL 104.14, OUTR 106.68, CAPP 111.76, CAPM 119.38, LDOO 124.46, VNEG 127.0
#                      top y=99.06: CPVDD 124.46, DVDD 127.0, AVDD 129.54; bottom y=132.08: CPGND, DGND, AGND
assert U1['15'] == (g(90), g(82)) and U1['6'] == (g(110), g(82)) and U1['1'] == (g(98), g(78)) and U1['9'] == (g(102), g(104)), U1

# ---- J1: Pi I2S in (order chosen to match U1's pin order, no crossings) ----------
J1 = s.place('Connector', 'Conn_01x06_Pin', 'J1', g(60), g(82), value='Pi I2S', footprint=JST_FP, fields=JST,
             prop_pos={'Reference': (-1.27, -12.7), 'Value': (-1.27, -10.7)})
# 1 5V (99.06) 2 GND (101.6) 3 LRCK (104.14) 4 DIN (106.68) 5 BCK (109.22) 6 XSMT (111.76), all at x=81.28
assert J1['3'] == (g(64), g(82)) and J1['6'] == (g(64), g(88)), J1
s.wire(J1['1'], (g(66), g(78)), (g(66), g(76))); s.power('+5V', g(66), g(76))
s.wire(J1['2'], (g(68), g(80))); s.power('GND', g(68), g(80), rot=180)         # body upward, clear of R1
for pin, upin, ref, tp in (('3', '15', 'R1', ('TP1', 'LRCK', TPT)), ('4', '14', 'R2', None), ('5', '13', 'R3', ('TP2', 'BCK', TPB))):
    y = J1[pin][1]
    rx = g(70) if pin != '4' else g(78)   # stagger the middle row so labels do not stack
    r = s.place('Device', 'R', ref, rx, y, rot=90, value='33', footprint=R_FP, fields=PARTS['33'], prop_pos={'Reference': (-3.0, -2.3), 'Value': (3.0, -2.3)} if pin != '4' else {'Reference': (-3.0, 2.3), 'Value': (3.0, 2.3)})
    s.wire(J1[pin], r['1']); s.wire(r['2'], U1[upin])
    if tp:
        s.junction(g(84), y); tp[2](tp[0], g(84), y, tp[1])
# XSMT: 10k pull-up (soft un-mute) + optional GPIO drive from J1.6; routed under the chip's config pins
s.wire(J1['6'], (g(66), g(88)), (g(66), g(104)), (g(88), g(104)), (g(88), g(96)), U1['17'])
R6 = s.place('Device', 'R', 'R6', g(76), g(101), value='10k', footprint=R_FP, fields=PARTS['10k'], prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
s.wire(R6['2'], (g(76), g(104))); s.junction(g(76), g(104))
s.wire(R6['1'], (g(76), g(95))); s.power('+3V3', g(76), g(95))
# config pins to GND: SCK (BCK-PLL mode), FLT (normal), DEMP (off), FMT (I2S)
for upin in ('12', '11', '10'):
    x, y = U1[upin]
    s.wire((x, y), (g(84), y)); s.power('GND', g(84), y, rot=270)               # body to the left
s.wire(U1['16'], (g(90), g(100))); s.power('GND', g(90), g(100))
# supplies on top, grounds on the bottom
for upin in ('1', '20', '8'):
    x, y = U1[upin]; s.wire((x, y), (x, g(76)))
s.wire((g(98), g(76)), (g(102), g(76))); s.junction(g(100), g(76)); s.power('+3V3', g(100), g(76))
for upin in ('3', '19', '9'):
    x, y = U1[upin]; s.wire((x, y), (x, g(106)))
s.wire((g(98), g(106)), (g(102), g(106))); s.junction(g(100), g(106)); s.power('GND', g(100), g(106))
# charge pump / LDO caps on the right
C5 = s.place('Device', 'C', 'C5', g(116), g(91), value='2.2u', footprint=C_FP, fields=PARTS['2.2u'], description='2.2 uF X5R 16 V flying cap', prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
s.wire(U1['2'], C5['1']); s.wire(U1['4'], C5['2'])
C6 = s.place('Device', 'C', 'C6', g(120), g(103), value='2.2u', footprint=C_FP, fields=PARTS['2.2u'], description='2.2 uF X5R 16 V (VNEG)', prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
s.wire(U1['5'], (g(120), g(100)), C6['1']); s.wire(C6['2'], (g(120), g(108))); s.power('GND', g(120), g(108))
C7 = s.place('Device', 'C', 'C7', g(124), g(101), value='2.2u', footprint=C_FP, fields=PARTS['2.2u'], description='2.2 uF X5R 16 V (LDOO 1.8 V)', prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
s.wire(U1['18'], (g(124), g(98)), C7['1']); s.wire(C7['2'], (g(124), g(106))); s.power('GND', g(124), g(106))
# line outputs: 470 R + 2.2 nF (TI recommended filter), L above / R below the rows
R4 = s.place('Device', 'R', 'R4', g(116), g(82), rot=90, value='470', footprint=R_FP, fields=PARTS['470'], prop_pos={'Reference': (-3.0, -2.3), 'Value': (3.0, -2.3)})
R5 = s.place('Device', 'R', 'R5', g(120), g(84), rot=90, value='470', footprint=R_FP, fields=PARTS['470'], prop_pos={'Reference': (-3.0, 2.3), 'Value': (3.0, 2.3)})
s.wire(U1['6'], R4['1']); s.wire(U1['7'], R5['1'])
C8 = s.place('Device', 'C', 'C8', g(127), g(79), rot=180, value='2.2n', footprint=C_FP, fields=PARTS['2.2n'], description='2.2 nF 50 V X7R (C0G preferred if stocked)', prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
C9 = s.place('Device', 'C', 'C9', g(131), g(87), value='2.2n', footprint=C_FP, fields=PARTS['2.2n'], description='2.2 nF 50 V X7R (C0G preferred if stocked)', prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
assert C8['1'] == (g(127), g(82)) and C9['1'] == (g(131), g(84)), (C8, C9)
s.wire(C8['2'], (g(127), g(74))); s.power('GND', g(127), g(74), rot=180)
s.wire(C9['2'], (g(131), g(92))); s.power('GND', g(131), g(92))
# 3.5 mm jack (TRRS footprint; ring 2 and sleeve both grounded so a TRS plug is fine)
J2 = s.place('Connector_Audio', 'AudioJack4', 'J2', g(139), g(86), mirror='x', value='Line out', footprint=JACK_FP,
             fields={'MPN': 'PJ-320D', 'Manufacturer': 'SHOU HAN', 'LCSC': 'C431535'}, prop_pos={'Reference': (7.0, -9.5), 'Value': (7.0, -7.7)})
assert J2['T'] == (g(143), g(82)) and J2['R1'] == (g(143), g(84)) and J2['R2'] == (g(143), g(86)) and J2['S'] == (g(143), g(88)), J2
s.wire(R4['2'], (g(127), g(82)), J2['T']); s.junction(g(127), g(82))
s.wire(R5['2'], (g(131), g(84)), J2['R1']); s.junction(g(131), g(84))
s.wire(J2['R2'], (g(141), g(86)), (g(141), g(88)), J2['S']); s.junction(g(141), g(88))
s.wire((g(141), g(88)), (g(141), g(90))); s.power('GND', g(141), g(90))

# ---- 3.3 V regulator -----------------------------------------------------------
U2 = s.place('Regulator_Linear', 'ME6211C33M5', 'U2', g(70), g(56), value='ME6211C33',
             fields={'MPN': 'ME6211C33M5G-N', 'Manufacturer': 'Microne', 'LCSC': 'C82942'}, prop_pos={'Reference': (-5.0, -6.5), 'Value': (6.0, 6.0)})
assert U2['1'] == (g(64), g(54)) and U2['3'] == (g(64), g(56)) and U2['2'] == (g(70), g(62)) and U2['5'] == (g(76), g(54)), U2
s.wire(U2['1'], (g(60), g(54)), (g(60), g(52))); s.power('+5V', g(60), g(52))
s.wire(U2['3'], (g(60), g(56)), (g(60), g(54))); s.junction(g(60), g(54))        # CE tied to VIN
s.wire(U2['2'], (g(70), g(64))); s.power('GND', g(70), g(64))
s.wire(U2['5'], (g(78), g(54)), (g(78), g(52))); s.power('+3V3', g(78), g(52))
s.no_connect(*U2['4'])

# ---- decoupling cluster + LED + flags (C3/C4 are rail bulk; the per-pin 100 nF are C10..C12) ----
def cap(ref, x, val, desc, rail_top, rail_bot, vcc):
    c = s.place('Device', 'C', ref, x, g(58), value=val, footprint=C_FP, description=desc, fields=PARTS[val], prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
    s.wire(c['1'], (x, rail_top)); s.wire(c['2'], (x, rail_bot)); s.power(vcc, x, rail_top); s.power('GND', x, rail_bot)
top, bot = g(53), g(63)
cap('C1', g(86), '10u', '10 uF X5R 25 V (LDO in)', top, bot, '+5V')
for i, (ref, val, desc) in enumerate([('C2', '10u', '10 uF X5R 25 V (LDO out)'), ('C3', '10u', '10 uF X5R 25 V (rail)'), ('C4', '10u', '10 uF X5R 25 V (rail)'),
                                      ('C10', '100n', '100 nF X7R 50 V (AVDD)'), ('C11', '100n', '100 nF X7R 50 V (DVDD)'), ('C12', '100n', '100 nF X7R 50 V (CPVDD)')]):
    cap(ref, g(94 + 6 * i), val, desc, top, bot, '+3V3')
s.wire((g(86), top), (g(80), top)); s.junction(g(86), top); s.flag(g(80), top)
s.wire((g(86), bot), (g(80), bot)); s.junction(g(86), bot); s.flag(g(80), bot, rot=180)
s.junction(g(83), bot); TPB('TP3', g(83), bot, 'GND')
x = g(134)
R7 = s.place('Device', 'R', 'R7', x, g(56), value='1k', footprint=R_FP, fields=PARTS['1k'], prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
D1 = s.place('Device', 'LED', 'D1', x, g(64), rot=90, value='GREEN', footprint=LED_FP, fields=PARTS['GREEN'], prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
s.wire((x, g(51)), R7['1']); s.power('+3V3', x, g(51)); s.wire(R7['2'], D1['2']); s.wire(D1['1'], (x, g(69))); s.power('GND', x, g(69))
for i in range(4):
    s.place('Mechanical', 'MountingHole', f'H{i+1}', g(60 + i * 8), g(112), value='M2.5', footprint=HOLE_FP, in_bom=False, prop_pos={'Reference': (-2.0, -3.0), 'Value': (-2.0, -1.0)})

s.text('J1 to Pi header: 1=5V (pin 2), 2=GND (pin 6), 3=LRCK (GPIO19, pin 35), 4=DIN (GPIO21, pin 40), 5=BCK (GPIO18, pin 12), 6=XSMT (any GPIO, optional).', g(58), g(118))
s.text('SCK grounded: the PCM5102A derives its clocks from BCK (3-wire mode). FMT low = I2S, DEMP low, FLT low = normal latency.', g(58), g(121))
s.text('XSMT: 10k pull-up un-mutes at power-up; a GPIO can drive it for pop-free mute (edges must be < 20 ns, so no RC on this pin).', g(58), g(124))
s.text('Output: 2.1 Vrms ground-centred (no coupling caps); 470 R + 2.2 nF is the TI-recommended filter. Load >= 1 kOhm.', g(58), g(127))
s.text('Pi: dtoverlay=hifiberry-dac (PCM5102A, no MCLK) in config.txt.', g(58), g(130))
s.write(OUT)
print('wrote', OUT)
