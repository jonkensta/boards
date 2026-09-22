#!/usr/bin/env python3
"""Write hat.kicad_sch: Raspberry Pi HAT = isolated SPI -> SK9822 strip + PCM5102A I2S DAC + ID EEPROM.

The header block wires the Pi's 40-pin connector with net labels; the isolator and DAC
blocks are the chromatone/isolator and chromatone/dac schematics with their Pi-side
JST connectors replaced by those labels. Block origins are grid-unit offsets so the
proven geometry of the two source boards is kept.
"""
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, 'boardtools')):
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from boardtools.schgen import Schematic, g, root_uuid_of

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'hat.kicad_sch')

R_FP = 'Resistor_SMD:R_0603_1608Metric'; C_FP = 'Capacitor_SMD:C_0603_1608Metric'
LED_FP = 'LED_SMD:LED_0603_1608Metric'; TP_FP = 'TestPoint:TestPoint_Pad_D1.5mm'
JST_FP = 'Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical'; HOLE_FP = 'MountingHole:MountingHole_2.7mm_M2.5'
JACK_FP = 'Connector_Audio:Jack_3.5mm_PJ320D_Horizontal'
HDR_FP = 'Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical'
SOIC8_FP = 'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm'
JP_FP = 'Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm'
JST = {'MPN': 'B4B-XH-A(LF)(SN)', 'Manufacturer': 'JST', 'LCSC': 'C144395'}
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
    '47': {}, 'BLUE': {}, '3.9k': {},     # pick basic parts in JLCPCB's BOM tool
}

s = Schematic('hat', root_uuid_of(OUT), 'Chromatone Pi HAT', rev='A', date='2026-09-20', paper='A3',
              comment='Pi 4B HAT: SPI (3.3 V) -> ISO7720 -> SK9822 strip (5 V, isolated); I2S -> PCM5102A line out; ID EEPROM (DNP)')

def TPT(ref, x, y, name):   # test point, body above
    s.place('Connector', 'TestPoint', ref, x, y, value=name, footprint=TP_FP, in_bom=False, in_pos_files=False, prop_pos={'Reference': (-2.0, -5.5), 'Value': (-2.0, -3.6)})
def TPB(ref, x, y, name):   # body below
    s.place('Connector', 'TestPoint', ref, x, y, rot=180, value=name, footprint=TP_FP, in_bom=False, in_pos_files=False, prop_pos={'Reference': (-2.0, 6.7), 'Value': (-2.0, 4.8)})
def R(ref, x, y, val, rot=0, pp=None, **kw):
    return s.place('Device', 'R', ref, x, y, rot=rot, value=val, footprint=R_FP, fields=PARTS[val],
                   prop_pos=pp or {'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)}, **kw)
def C(ref, x, y, val, desc, rot=0, **kw):
    return s.place('Device', 'C', ref, x, y, rot=rot, value=val, footprint=C_FP, fields=PARTS[val], description=desc,
                   prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)}, **kw)

# =====================================================================================
# Pi 40-pin header (J1), wired with labels. Symbol origin (38, 60): right pins x=64, left x=12.
# =====================================================================================
J1 = s.place('Connector', 'Raspberry_Pi_4', 'J1', g(38), g(60), value='Pi 40-pin', footprint=HDR_FP,
             fields={'MPN': 'PPTC202LFBN-RC', 'Manufacturer': 'Sullins', 'LCSC': ''},
             description='2x20 female socket, 2.54 mm, 8.5 mm body, on the back of the HAT',
             prop_pos={'Reference': (-26.0, -21.0), 'Value': (-26.0, -19.0)})
assert J1['1'] == (g(64), g(44)) and J1['2'] == (g(64), g(42)) and J1['6'] == (g(38), g(82)) and J1['12'] == (g(12), g(58)), J1
assert J1['40'] == (g(12), g(64)) and J1['29'] == (g(64), g(62)) and J1['23'] == (g(64), g(76)), J1
s.wire(J1['2'], (g(68), g(42)), (g(68), g(36))); s.power('+5V', g(68), g(36))
s.wire(J1['1'], (g(72), g(44)), (g(72), g(38))); s.power('+3V3', g(72), g(38))
s.wire(J1['6'], (g(38), g(86))); s.power('GND', g(38), g(86))
for pin, name in (('27', 'ID_SD'), ('28', 'ID_SC'), ('29', 'XSMT'), ('19', 'MOSI'), ('23', 'SCLK')):
    x, y = J1[pin]; s.wire((x, y), (g(70), y)); s.label(name, g(70), y)
for pin, name in (('12', 'BCK'), ('35', 'LRCK'), ('40', 'DIN')):
    x, y = J1[pin]; s.wire((x, y), (g(6), y)); s.label(name, g(6), y, rot=180)
for pin in ('3', '5', '7', '21', '24', '26', '31', '8', '10', '11', '13', '15', '16', '18', '22', '32', '33', '36', '37', '38'):
    s.no_connect(*J1[pin])
s.text('Pi 4B (any 40-pin Pi). SPI0: GPIO11 SCLK, GPIO10 MOSI. I2S: GPIO18 BCK, GPIO19 LRCK, GPIO21 DIN.', g(4), g(92))
s.text('GPIO5 (pin 29, default pull-up) may drive XSMT push-pull for pop-free mute; unused otherwise. ID_SD/ID_SC: HAT EEPROM only.', g(4), g(95))

# =====================================================================================
# Isolator block (chromatone/isolator rev A geometry, offset +50, +4 grid units)
# =====================================================================================
def G(k): return g(k - 40 + 50)
def GY(k): return g(k - 40 + 4)
Y_VCC, Y_CLK, Y_DATA, Y_GND, Y_TOP, Y_BOT = GY(76), GY(78), GY(80), GY(82), GY(74), GY(84)
U1 = s.place('Isolator', 'ISO7720D', 'U1', G(120), Y_DATA, value='ISO7720D',
             fields={'MPN': 'ISO7720DR', 'Manufacturer': 'Texas Instruments', 'LCSC': 'C486037'},
             prop_pos={'Reference': (-7.62, -9.5), 'Value': (0, 9.5)})
J2 = s.place('Connector', 'Conn_01x04_Pin', 'J2', G(155), Y_CLK, mirror='y', value='Strip', footprint=JST_FP, fields=JST,
             prop_pos={'Reference': (-4.0, -10.2), 'Value': (-4.0, -8.2)})
# U1: 1 VCC1 2 INA 3 INB 4 GND1 | 5 GND2 6 OUTB 7 OUTA 8 VCC2     J2: 1 5V 2 CLK 3 DATA 4 GND
assert U1['2'] == (G(112), Y_CLK) and J2['2'] == (G(151), Y_CLK) and U1['7'] == (G(128), Y_CLK), (U1, J2)
# domain A
s.wire(U1['1'], (G(110), Y_VCC), (G(110), Y_TOP)); s.power('+3V3', G(110), Y_TOP)
s.wire(U1['4'], (G(110), Y_GND), (G(110), Y_BOT)); s.power('GND', G(110), Y_BOT)
s.wire((G(92), Y_CLK), (G(98), Y_CLK), U1['2']); s.junction(G(98), Y_CLK); s.label('SCLK', G(92), Y_CLK, rot=180)
TPT('TP1', G(98), Y_CLK, 'SCLK')
s.wire((G(92), Y_DATA), (G(102), Y_DATA), U1['3']); s.junction(G(102), Y_DATA); s.label('MOSI', G(92), Y_DATA, rot=180)
TPB('TP2', G(102), Y_DATA, 'MOSI')
# domain B
s.wire(U1['8'], (G(130), Y_VCC), (G(130), Y_TOP)); s.power('+5V', G(130), Y_TOP, value='+5V_LED')
s.wire(U1['5'], (G(130), Y_GND), (G(130), Y_BOT)); s.power('GNDPWR', G(130), Y_BOT, value='GND_LED')
s.wire(J2['1'], (G(149), Y_VCC), (G(149), Y_TOP)); s.power('+5V', G(149), Y_TOP, value='+5V_LED')
s.wire(J2['4'], (G(149), Y_GND), (G(149), Y_BOT)); s.power('GNDPWR', G(149), Y_BOT, value='GND_LED')
R1 = R('R1', G(136), Y_CLK, '47', rot=90, pp={'Reference': (-3.0, -2.3), 'Value': (3.5, -2.3)})
R2 = R('R2', G(136), Y_DATA, '47', rot=90, pp={'Reference': (-3.0, 2.3), 'Value': (3.5, 2.3)})
s.wire(U1['7'], R1['1']); s.wire(R1['2'], (G(146), Y_CLK), J2['2']); s.junction(G(146), Y_CLK)
TPT('TP3', G(146), Y_CLK, 'CLK')
s.wire(U1['6'], R2['1']); s.wire(R2['2'], (G(146), Y_DATA), J2['3']); s.junction(G(146), Y_DATA)
TPB('TP4', G(146), Y_DATA, 'DATA')

def cluster(x0, vcc, vname, gnd, gname, cref, rref, dref, led_color, gnd_tp, flags):
    rail_top, rail_bot = GY(90), GY(100)
    for i, (ref, val, desc) in enumerate([(cref[0], '100n', '100 nF X7R 50 V'), (cref[1], '10u', '10 uF X5R 25 V')]):
        x = G(x0 + i * 8)
        c = C(ref, x, GY(95), val, desc)
        s.wire(c['1'], (x, rail_top)); s.wire(c['2'], (x, rail_bot))
        s.power(vcc, x, rail_top, value=vname); s.power(gnd, x, rail_bot, value=gname)
    if flags:       # rails fed only by a connector need PWR_FLAGs; the Pi header pins are power outputs already
        s.wire((G(x0), rail_top), (G(x0 - 6), rail_top)); s.junction(G(x0), rail_top); s.flag(G(x0 - 6), rail_top)
        s.wire((G(x0), rail_bot), (G(x0 - 6), rail_bot)); s.junction(G(x0), rail_bot); s.flag(G(x0 - 6), rail_bot, rot=180)
    else:
        s.wire((G(x0), rail_bot), (G(x0 - 3), rail_bot))
    s.junction(G(x0 - 3), rail_bot) if flags else s.junction(G(x0), rail_bot)
    TPB(gnd_tp[0], G(x0 - 3), rail_bot, gnd_tp[1])
    x = G(x0 + 18)
    r = R(rref, x, GY(93), '1k')
    d = s.place('Device', 'LED', dref, x, GY(101), rot=90, value=led_color, footprint=LED_FP, fields=PARTS[led_color],
                description=f'{led_color.lower()} 0603 LED', prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
    s.wire((x, GY(88)), r['1']); s.power(vcc, x, GY(88), value=vname)
    s.wire(r['2'], d['2']); s.wire(d['1'], (x, GY(106))); s.power(gnd, x, GY(106), value=gname)

cluster(97, '+3V3', None, 'GND', None, ('C1', 'C2'), 'R3', 'D1', 'GREEN', ('TP5', 'GND_A'), flags=False)
cluster(136, '+5V', '+5V_LED', 'GNDPWR', 'GND_LED', ('C3', 'C4'), 'R4', 'D2', 'BLUE', ('TP6', 'GND_B'), flags=True)
s.box(G(78), GY(66), G(116), GY(110)); s.box(G(124), GY(66), G(160), GY(110))
s.text('DOMAIN A: Pi side, 3.3 V, Pi battery', G(78) + 0.5, GY(66) - 1, 1.5, True)
s.text('DOMAIN B: LED side, 5 V, LED battery', G(124) + 0.5, GY(66) - 1, 1.5, True)
s.text('Isolation barrier: only SPI CLK and DATA cross, A -> B. GND and GND_LED never touch (nylon standoff at the LED-side hole).', G(78) + 0.5, GY(114))
s.text('J2 to pixel 0 of the strip: 1=5V, 2=CI, 3=DI, 4=GND. Tap 5V/GND at the strip end so VCC2 never exceeds the pixel rail.', G(78) + 0.5, GY(117))
s.text('R1/R2 tame ringing on the CLK/DATA leads; keep leads to pixel 0 short, twisted with GND_LED. Start SPI at 8 MHz.', G(78) + 0.5, GY(120))

# =====================================================================================
# DAC block (chromatone/dac rev A geometry, offset +30, +44 grid units); refs renumbered
# =====================================================================================
def X(k): return g(k + 30)
def Y(k): return g(k + 44)
def DP(x, y, rot=0): s.power('+3V3', x, y, value='+3V3_DAC', rot=rot)     # the LDO rail, not the Pi's 3V3
U2 = s.place('Audio', 'PCM5102A', 'U2', X(100), Y(90), value='PCM5102A',
             fields={'MPN': 'PCM5102APWR', 'Manufacturer': 'Texas Instruments', 'LCSC': 'C107671'},
             prop_pos={'Reference': (-10.16, -17.5), 'Value': (10.16, -17.5)})
assert U2['15'] == (X(90), Y(82)) and U2['6'] == (X(110), Y(82)) and U2['1'] == (X(98), Y(78)) and U2['9'] == (X(102), Y(104)), U2
# I2S in from the header labels (where J1 of the dac board used to be), 33 R damping at the receiving end
for name, y, upin, ref, tp in (('LRCK', Y(82), '15', 'R5', ('TP7', 'LRCK', TPT)), ('DIN', Y(84), '14', 'R6', None), ('BCK', Y(86), '13', 'R7', ('TP8', 'BCK', TPB))):
    rx = X(70) if name != 'DIN' else X(78)
    r = R(ref, rx, y, '33', rot=90, pp={'Reference': (-3.0, -2.3), 'Value': (3.0, -2.3)} if name != 'DIN' else {'Reference': (-3.0, 2.3), 'Value': (3.0, 2.3)})
    s.wire((X(64), y), r['1']); s.wire(r['2'], U2[upin]); s.label(name, X(64), y, rot=180)
    if tp:
        s.junction(X(84), y); tp[2](tp[0], X(84), y, tp[1])
# XSMT: 10k pull-up (soft un-mute) + optional GPIO drive; routed under the chip's config pins
s.wire((X(64), Y(88)), (X(66), Y(88)), (X(66), Y(104)), (X(88), Y(104)), (X(88), Y(96)), U2['17']); s.label('XSMT', X(64), Y(88), rot=180)
R10 = R('R10', X(76), Y(101), '10k')
s.wire(R10['2'], (X(76), Y(104))); s.junction(X(76), Y(104))
s.wire(R10['1'], (X(76), Y(95))); DP(X(76), Y(95))
# config pins to GND: SCK (BCK-PLL mode), FLT (normal), DEMP (off), FMT (I2S)
for upin in ('12', '11', '10'):
    x, y = U2[upin]
    s.wire((x, y), (X(84), y)); s.power('GND', X(84), y, rot=270)
s.wire(U2['16'], (X(90), Y(100))); s.power('GND', X(90), Y(100))
# supplies on top, grounds on the bottom
for upin in ('1', '20', '8'):
    x, y = U2[upin]; s.wire((x, y), (x, Y(76)))
s.wire((X(98), Y(76)), (X(102), Y(76))); s.junction(X(100), Y(76)); DP(X(100), Y(76))
for upin in ('3', '19', '9'):
    x, y = U2[upin]; s.wire((x, y), (x, Y(106)))
s.wire((X(98), Y(106)), (X(102), Y(106))); s.junction(X(100), Y(106)); s.power('GND', X(100), Y(106))
# charge pump / LDO caps on the right
C9 = C('C9', X(116), Y(91), '2.2u', '2.2 uF X5R 16 V flying cap')
s.wire(U2['2'], C9['1']); s.wire(U2['4'], C9['2'])
C10 = C('C10', X(120), Y(103), '2.2u', '2.2 uF X5R 16 V (VNEG)')
s.wire(U2['5'], (X(120), Y(100)), C10['1']); s.wire(C10['2'], (X(120), Y(108))); s.power('GND', X(120), Y(108))
C11 = C('C11', X(124), Y(101), '2.2u', '2.2 uF X5R 16 V (LDOO 1.8 V)')
s.wire(U2['18'], (X(124), Y(98)), C11['1']); s.wire(C11['2'], (X(124), Y(106))); s.power('GND', X(124), Y(106))
# line outputs: 470 R + 2.2 nF (TI recommended filter), L above / R below the rows
R8 = R('R8', X(116), Y(82), '470', rot=90, pp={'Reference': (-3.0, -2.3), 'Value': (3.0, -2.3)})
R9 = R('R9', X(120), Y(84), '470', rot=90, pp={'Reference': (-3.0, 2.3), 'Value': (3.0, 2.3)})
s.wire(U2['6'], R8['1']); s.wire(U2['7'], R9['1'])
C12 = C('C12', X(127), Y(79), '2.2n', '2.2 nF 50 V X7R (C0G preferred if stocked)', rot=180)
C13 = C('C13', X(131), Y(87), '2.2n', '2.2 nF 50 V X7R (C0G preferred if stocked)')
assert C12['1'] == (X(127), Y(82)) and C13['1'] == (X(131), Y(84)), (C12, C13)
s.wire(C12['2'], (X(127), Y(74))); s.power('GND', X(127), Y(74), rot=180)
s.wire(C13['2'], (X(131), Y(92))); s.power('GND', X(131), Y(92))
# 3.5 mm jack (TRRS footprint; ring 2 and sleeve both grounded so a TRS plug is fine)
J3 = s.place('Connector_Audio', 'AudioJack4', 'J3', X(139), Y(86), mirror='x', value='Line out', footprint=JACK_FP,
             fields={'MPN': 'PJ-320D', 'Manufacturer': 'SHOU HAN', 'LCSC': 'C431535'}, prop_pos={'Reference': (7.0, -9.5), 'Value': (7.0, -7.7)})
assert J3['T'] == (X(143), Y(82)) and J3['R1'] == (X(143), Y(84)) and J3['R2'] == (X(143), Y(86)) and J3['S'] == (X(143), Y(88)), J3
s.wire(R8['2'], (X(127), Y(82)), J3['T']); s.junction(X(127), Y(82))
s.wire(R9['2'], (X(131), Y(84)), J3['R1']); s.junction(X(131), Y(84))
s.wire(J3['R2'], (X(141), Y(86)), (X(141), Y(88)), J3['S']); s.junction(X(141), Y(88))
s.wire((X(141), Y(88)), (X(141), Y(90))); s.power('GND', X(141), Y(90))
# 3.3 V regulator from the Pi's 5 V (the DAC's analog rail is not the Pi's noisy 3V3)
U3 = s.place('Regulator_Linear', 'ME6211C33M5', 'U3', X(70), Y(56), value='ME6211C33',
             fields={'MPN': 'ME6211C33M5G-N', 'Manufacturer': 'Microne', 'LCSC': 'C82942'}, prop_pos={'Reference': (-5.0, -6.5), 'Value': (6.0, 6.0)})
assert U3['1'] == (X(64), Y(54)) and U3['3'] == (X(64), Y(56)) and U3['2'] == (X(70), Y(62)) and U3['5'] == (X(76), Y(54)), U3
s.wire(U3['1'], (X(60), Y(54)), (X(60), Y(52))); s.power('+5V', X(60), Y(52))
s.wire(U3['3'], (X(60), Y(56)), (X(60), Y(54))); s.junction(X(60), Y(54))        # CE tied to VIN
s.wire(U3['2'], (X(70), Y(64))); s.power('GND', X(70), Y(64))
s.wire(U3['5'], (X(78), Y(54)), (X(78), Y(52))); DP(X(78), Y(52))
s.no_connect(*U3['4'])
# decoupling cluster + LED (C7/C8 are rail bulk; the per-pin 100 nF are C14..C16)
def cap(ref, x, val, desc, rail_top, rail_bot, dac_rail):
    c = C(ref, x, Y(58), val, desc)
    s.wire(c['1'], (x, rail_top)); s.wire(c['2'], (x, rail_bot))
    (DP(x, rail_top) if dac_rail else s.power('+5V', x, rail_top)); s.power('GND', x, rail_bot)
top, bot = Y(53), Y(63)
cap('C5', X(86), '10u', '10 uF X5R 25 V (LDO in)', top, bot, False)
for i, (ref, val, desc) in enumerate([('C6', '10u', '10 uF X5R 25 V (LDO out)'), ('C7', '10u', '10 uF X5R 25 V (rail)'), ('C8', '10u', '10 uF X5R 25 V (rail)'),
                                      ('C14', '100n', '100 nF X7R 50 V (AVDD)'), ('C15', '100n', '100 nF X7R 50 V (DVDD)'), ('C16', '100n', '100 nF X7R 50 V (CPVDD)')]):
    cap(ref, X(94 + 6 * i), val, desc, top, bot, True)
s.wire((X(86), bot), (X(89), bot)); s.junction(X(86), bot); TPB('TP9', X(89), bot, 'GND')
x = X(134)
R11 = R('R11', x, Y(56), '1k')
D3 = s.place('Device', 'LED', 'D3', x, Y(64), rot=90, value='GREEN', footprint=LED_FP, fields=PARTS['GREEN'], description='green 0603 LED',
             prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
s.wire((x, Y(51)), R11['1']); DP(x, Y(51)); s.wire(R11['2'], D3['2']); s.wire(D3['1'], (x, Y(69))); s.power('GND', x, Y(69))
s.box(X(56), Y(46), X(150), Y(112))
s.text('I2S DAC (experiment): PCM5102A, BCK-only PLL mode, 2.1 Vrms ground-centred line out', X(56) + 0.5, Y(46) - 1, 1.5, True)
s.text('SCK grounded: the PCM5102A derives its clocks from BCK (3-wire mode). FMT low = I2S, DEMP low, FLT low = normal latency.', X(56), Y(115))
s.text('XSMT: 10k pull-up un-mutes at power-up; GPIO5 can drive it for pop-free mute (edges must be < 20 ns, so no RC on this pin).', X(56), Y(118))
s.text('Output: 2.1 Vrms ground-centred (no coupling caps); 470 R + 2.2 nF is the TI-recommended filter. Load >= 1 kOhm.', X(56), Y(121))
s.text('Pi: dtoverlay=hifiberry-dac (PCM5102A, no MCLK) in config.txt, or program the ID EEPROM to load it.', X(56), Y(124))

# =====================================================================================
# HAT ID EEPROM (all DNP: config.txt does the job; populate + program with eepflash to auto-load overlays)
# =====================================================================================
U4 = s.place('Memory_EEPROM', '24LC32', 'U4', g(30), g(110), value='24LC32', footprint=SOIC8_FP, dnp=True,
             fields={'MPN': '24LC32AT-I/SN', 'Manufacturer': 'Microchip', 'LCSC': ''}, prop_pos={'Reference': (-8.0, -9.0), 'Value': (-8.0, 9.0)})
assert U4['1'] == (g(22), g(108)) and U4['5'] == (g(38), g(108)) and U4['7'] == (g(38), g(112)) and U4['8'] == (g(30), g(104)) and U4['4'] == (g(30), g(116)), U4
for pin in ('1', '2', '3'):
    s.wire(U4[pin], (g(18), U4[pin][1]))
s.wire((g(18), g(108)), (g(18), g(118))); s.junction(g(18), g(110)); s.junction(g(18), g(112)); s.power('GND', g(18), g(118))
s.wire(U4['4'], (g(30), g(118))); s.power('GND', g(30), g(118))
s.wire(U4['8'], (g(30), g(100))); s.power('+3V3', g(30), g(100))
C17 = C('C17', g(24), g(101), '100n', '100 nF X7R 50 V (EEPROM)', dnp=True)
s.wire(C17['1'], (g(24), g(96))); s.power('+3V3', g(24), g(96)); s.wire(C17['2'], (g(24), g(106))); s.power('GND', g(24), g(106))
s.wire(U4['5'], (g(50), g(108))); s.label('ID_SD', g(50), g(108))
s.wire(U4['6'], (g(58), g(110))); s.label('ID_SC', g(58), g(110))
R12 = R('R12', g(46), g(105), '3.9k', dnp=True); s.junction(g(46), g(108)); s.wire(R12['1'], (g(46), g(100))); s.power('+3V3', g(46), g(100))
R13 = R('R13', g(54), g(107), '3.9k', dnp=True); s.junction(g(54), g(110)); s.wire(R13['1'], (g(54), g(100))); s.power('+3V3', g(54), g(100))
assert R12['2'] == (g(46), g(108)) and R13['2'] == (g(54), g(110)), (R12, R13)
# WP: 10k pull-up = write-protected; close JP1 to program
s.wire(U4['7'], (g(50), g(112))); s.junction(g(42), g(112))
R14 = R('R14', g(42), g(115), '10k', dnp=True); s.wire(R14['2'], (g(42), g(120))); s.power('+3V3', g(42), g(120), rot=180)
JP1 = s.place('Jumper', 'SolderJumper_2_Open', 'JP1', g(50), g(116), rot=90, value='WP', footprint=JP_FP, in_bom=False, in_pos_files=False,
              prop_pos={'Reference': (2.0, -1.27), 'Value': (2.0, 1.27)})
assert R14['1'] == (g(42), g(112)) and JP1['2'] == (g(50), g(112)) and JP1['1'] == (g(50), g(120)), (R14, JP1)
s.wire(JP1['1'], (g(50), g(122))); s.power('GND', g(50), g(122))
s.box(g(4), g(98), g(72), g(126))
s.text('HAT ID EEPROM (DNP): 24LC32 on ID_SD/ID_SC, 3.9k pull-ups, WP high; short JP1 to program', g(4) + 0.5, g(98) - 1, 1.5, True)
s.text('Populate U4, C17, R12-R14 and program with eepflash.sh (hats/eepromutils) to have the Pi enable SPI and load hifiberry-dac by itself.', g(4), g(130))

for i in range(4):
    s.place('Mechanical', 'MountingHole', f'H{i+1}', g(8 + i * 10), g(142), value='M2.5', footprint=HOLE_FP, in_bom=False, in_pos_files=False,
            prop_pos={'Reference': (-2.0, -3.0), 'Value': (-2.0, -1.0)})
s.text('H1-H4: HAT holes (58 x 49 mm). H3 (bottom left) sits in the LED domain: copper keepout, nylon standoff.', g(4), g(150))
s.write(OUT)
print('wrote', OUT)
