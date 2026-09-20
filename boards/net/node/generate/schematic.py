#!/usr/bin/env python3
"""Write node.kicad_sch: RP2040 net node, 4 single-wire neighbour links, RGB LED, buzzer, sensor port.

Blocks are wired with local net labels; only the RP2040's crystal, TESTEN and supply pins
are wired directly. Sensor options are KiCad 10 design variants (see README.md).
"""
import os, sys
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, 'boardtools')):
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)
from boardtools.schgen import Schematic, g, root_uuid_of

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'node.kicad_sch')

R_FP = 'Resistor_SMD:R_0603_1608Metric'
C_FP = 'Capacitor_SMD:C_0603_1608Metric'
JST3_FP = 'Connector_JST:JST_XH_B3B-XH-A_1x03_P2.50mm_Vertical'
JST3 = {'MPN': 'B3B-XH-A(LF)(SN)', 'Manufacturer': 'JST', 'LCSC': ''}
VARIANTS_TOF_ONLY = {'vib': {'dnp': True}, 'bare': {'dnp': True}}      # populated by default, gone elsewhere
VARIANTS_VIB_ONLY = {'vib': {'dnp': False}}                             # DNP by default, populated in "vib"

s = Schematic('node', root_uuid_of(OUT), 'Net node: RP2040, 4 neighbour links, RGB LED, buzzer, sensor port',
              rev='A', date='2026-09-16', paper='A3',
              comment='PoC. Variants: default = VL53L0X ToF, vib = SW-18010P, bare = header only')

# ---- helpers ------------------------------------------------------------------------------
_n = {'R': 0, 'C': 0}


def passive(kind, x, y, value, desc=None, rot=0, **kw):
    """Device:R / Device:C at (x, y). rot 0: pin 1 top, pin 2 bottom; rot 90: pin 1 left, pin 2 right."""
    _n[kind] += 1
    ref = f'{kind}{_n[kind]}'
    # property text is centre-justified: keep it clear of the body and of the plates of Device:C
    pp = kw.pop('prop_pos', {'Reference': (3.2, -1.9), 'Value': (3.6, 1.9)} if rot == 0 else {'Reference': (-2.2, -2.0), 'Value': (2.0, -2.0)})
    pins = s.place('Device', kind, ref, x, y, rot, value=value, footprint=R_FP if kind == 'R' else C_FP,
                   description=desc, prop_pos=pp, **kw)
    return ref, pins


def stub_label(pin, name, side, length=4):
    """Short wire from a pin end and a label at its far end. side: 'r', 'l', 'u', 'd'."""
    x, y = pin
    dx, dy, rot = {'r': (length, 0, 0), 'l': (-length, 0, 180), 'u': (0, -length, 90), 'd': (0, length, 270)}[side]
    end = (round(x + g(dx), 2), round(y + g(dy), 2))
    s.wire(pin, end)
    s.label(name, *end, rot=rot)
    return end


def W(*pts):
    s.wire(*[(g(x), g(y)) for x, y in pts])


def J(x, y):
    s.junction(g(x), g(y))


C100 = ('100n', '100 nF X7R 16 V')
C1U = ('1u', '1 uF X5R 10 V')
C10U = ('10u', '10 uF X5R 10 V')

# ---- U1 RP2040 (centre-left) ------------------------------------------------------------------
UX, UY = 90, 100
U1 = s.place('MCU_RaspberryPi', 'RP2040', 'U1', g(UX), g(UY), value='RP2040',
             fields={'MPN': 'RP2040', 'Manufacturer': 'Raspberry Pi', 'LCSC': 'C2040'},
             prop_pos={'Reference': (-25.4, -49.5), 'Value': (-25.4, -47.0)})
assert U1['2'] == (g(UX + 20), g(UY - 30)) and U1['20'] == (g(UX - 20), g(UY + 12)) and U1['57'] == (g(UX), g(UY + 36))

# supplies along the top: rail at UY-40 from x UX-12 .. UX+2, +3V3 at its left end
W((UX - 12, UY - 40), (UX + 2, UY - 40)); s.power('+3V3', g(UX - 12), g(UY - 40))
for pin in ('48', '43', '1', '44'):                       # USB_VDD, ADC_AVDD, IOVDD x6, VREG_VIN
    x = U1[pin][0]
    s.wire(U1[pin], (x, g(UY - 40))); s.junction(x, g(UY - 40))
# VREG_VOUT -> DVDD (1.1 V core), labelled for its capacitors
W((UX + 6, UY - 36), (UX + 6, UY - 38), (UX + 10, UY - 38), (UX + 10, UY - 36)); J(UX + 10, UY - 38)
W((UX + 10, UY - 38), (UX + 10, UY - 41)); s.label('DVDD', g(UX + 10), g(UY - 41), rot=90)
# GND, TESTEN
W((UX, UY + 36), (UX, UY + 40)); s.power('GND', g(UX), g(UY + 40))
W((UX - 20, UY - 24), (UX - 24, UY - 24), (UX - 24, UY - 20)); s.power('GND', g(UX - 24), g(UY - 20))

# GPIO map (right side) and left-side signals
GPIO = {'2': 'LINK_N', '3': 'LINK_E', '4': 'LINK_S', '5': 'LINK_W', '6': 'LED_DIN', '7': 'BUZZ',
        '8': 'SENS_INT', '9': 'SENS_XSHUT', '11': 'SDA', '12': 'SCL', '38': 'SENS_AIN'}
LEFT = {'26': 'RUN', '46': 'USB_DM', '47': 'USB_DP', '56': 'QSPI_SS', '52': 'QSPI_SCLK', '53': 'QSPI_SD0',
        '55': 'QSPI_SD1', '54': 'QSPI_SD2', '51': 'QSPI_SD3', '24': 'SWCLK', '25': 'SWDIO'}
for pin, name in GPIO.items():
    stub_label(U1[pin], name, 'r')
for pin, name in LEFT.items():
    stub_label(U1[pin], name, 'l')
for pin in [str(n) for n in range(13, 19)] + [str(n) for n in range(27, 38) if n != 33] + ['39', '40', '41']:   # 33 = IOVDD
    s.no_connect(*U1[pin])

# crystal: 12 MHz, 27 pF loads, 1k in series with XOUT (RP2040 hardware design guide)
Y1 = s.place('Device', 'Crystal_GND24', 'Y1', g(UX - 34), g(UY + 15), rot=270, value='12MHz',
             footprint='Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm', description='12 MHz crystal, 3225, 10 pF load',
             fields={'MPN': 'X322512MSB4SI', 'Manufacturer': 'YXC', 'LCSC': 'C9002'},
             prop_pos={'Reference': (4.5, -2.2), 'Value': (4.5, 2.2)})
assert Y1['1'] == (g(UX - 34), g(UY + 12)) and Y1['3'] == (g(UX - 34), g(UY + 18)) and Y1['2'] == (g(UX - 38), g(UY + 15))
s.wire(U1['20'], Y1['1'])                                                    # XIN
_, Rx = passive('R', g(UX - 26), g(UY + 20), '1k', rot=90)
s.wire(U1['21'], Rx['2']); s.wire(Rx['1'], (g(UX - 32), g(UY + 20)), (g(UX - 32), g(UY + 18)), Y1['3'])
_, Ca = passive('C', g(UX - 41), g(UY + 12), '27p', rot=90, desc='27 pF C0G 50 V', prop_pos={'Reference': (-7.0, -1.27), 'Value': (-7.0, 1.27)})
_, Cb = passive('C', g(UX - 41), g(UY + 18), '27p', rot=90, desc='27 pF C0G 50 V', prop_pos={'Reference': (-7.0, -1.27), 'Value': (-7.0, 1.27)})
s.wire(Ca['2'], Y1['1']); s.wire(Cb['2'], Y1['3']); J(UX - 34, UY + 12); J(UX - 34, UY + 18)
W((UX - 44, UY + 12), (UX - 44, UY + 18), (UX - 44, UY + 21)); s.wire(Y1['2'], (g(UX - 44), g(UY + 15)))
J(UX - 44, UY + 15); J(UX - 44, UY + 18); s.power('GND', g(UX - 44), g(UY + 21))

# ---- decoupling row (below U1) -------------------------------------------------------------------
DY = 156
s.text('RP2040 decoupling: one 100 nF per IOVDD pin (6), USB_VDD, ADC_AVDD; 1 uF on VREG_VIN; 10 uF bulk. DVDD: 1 uF + 2 x 100 nF.', g(30), g(DY - 6))
xs = list(range(34, 34 + 6 * 10, 6))
W((30, DY), (xs[-1], DY)); s.power('+3V3', g(30), g(DY))
for i, x in enumerate(xs):
    val, desc = ([C100] * 8 + [C1U, C10U])[i]
    _, c = passive('C', g(x), g(DY + 6), val, desc=desc)
    s.wire((g(x), g(DY)), c['1']); s.wire(c['2'], (g(x), g(DY + 12)))
    if x != xs[-1]:
        J(x, DY)
    J(x, DY + 12)
dvx = [xs[-1] + 10, xs[-1] + 16, xs[-1] + 22]
W((dvx[0] - 4, DY), (dvx[-1], DY)); s.label('DVDD', g(dvx[0] - 4), g(DY), rot=180)
for x, (val, desc) in zip(dvx, [C1U, C100, C100]):
    _, c = passive('C', g(x), g(DY + 6), val, desc=desc)
    s.wire((g(x), g(DY)), c['1']); s.wire(c['2'], (g(x), g(DY + 12)))
    if x != dvx[-1]:
        J(x, DY)
    J(x, DY + 12)
W((30, DY + 12), (dvx[-1], DY + 12)); s.power('GND', g(30), g(DY + 12))

# ---- U2 QSPI flash -------------------------------------------------------------------------------
FX, FY = 150, 172
U2 = s.place('Memory_Flash', 'W25Q16JVSS', 'U2', g(FX), g(FY), value='W25Q16JVSSIQ',
             footprint='Package_SO:SOIC-8_5.3x5.3mm_P1.27mm',
             fields={'MPN': 'W25Q16JVSSIQ', 'Manufacturer': 'Winbond', 'LCSC': 'C82317'},
             prop_pos={'Reference': (-7.62, -13.5), 'Value': (-7.62, 14.5)})
for pin, name in {'1': 'QSPI_SS', '6': 'QSPI_SCLK', '5': 'QSPI_SD0', '2': 'QSPI_SD1', '3': 'QSPI_SD2', '7': 'QSPI_SD3'}.items():
    stub_label(U2[pin], name, 'l', length=6)
W((FX, FY - 10), (FX, FY - 13), (FX + 10, FY - 13)); s.power('+3V3', g(FX), g(FY - 13))
_, c = passive('C', g(FX + 10), g(FY - 10), *C100)
s.wire(c['2'], (g(FX + 10), g(FY - 4))); s.power('GND', g(FX + 10), g(FY - 4))
W((FX, FY + 10), (FX, FY + 13)); s.power('GND', g(FX), g(FY + 13))

# ---- pull-ups (RUN, QSPI_SS, I2C, sensor interrupt) ---------------------------------------------
PX, PY = 140, 84
s.text('Pull-ups: RUN, QSPI_SS (boot), I2C, sensor INT (open-drain GPIO1 / switch).', g(PX - 10), g(PY - 5))
names = ['RUN', 'QSPI_SS', 'SDA', 'SCL', 'SENS_INT']
W((PX, PY), (PX + 6 * (len(names) - 1), PY)); s.power('+3V3', g(PX), g(PY))
for i, name in enumerate(names):
    x = PX + 6 * i
    _, r = passive('R', g(x), g(PY + 4), '10k' if name in ('RUN', 'QSPI_SS', 'SENS_INT') else '4k7')
    s.wire((g(x), g(PY)), r['1']); stub_label(r['2'], name, 'd', length=3)
    if 0 < i < len(names) - 1:
        J(x, PY)

# ---- J1..J4 neighbour links --------------------------------------------------------------------
s.text('Neighbour links: 5 V, single-wire half-duplex UART (open drain, 4k7 pull-up), GND. Straight 3-wire cable, no crossover.', g(130), g(22))
for i, (name, x) in enumerate(zip(['LINK_N', 'LINK_E', 'LINK_S', 'LINK_W'], [150, 174, 198, 222])):
    y = 50
    Jn = s.place('Connector_Generic', 'Conn_01x03', f'J{i + 1}', g(x), g(y), rot=270, value=name[-1],
                 footprint=JST3_FP, fields=JST3, description='JST XH 3-pin, vertical',
                 prop_pos={'Reference': (-3.0, 6.5), 'Value': (2.0, 6.5)})
    # rot 270 puts pin 1 on the right: 1 = 5 V (right), 2 = DATA (middle), 3 = GND (left)
    assert Jn['1'] == (g(x + 2), g(y - 4)) and Jn['2'] == (g(x), g(y - 4)) and Jn['3'] == (g(x - 2), g(y - 4))
    W((x + 2, y - 4), (x + 2, y - 6), (x + 6, y - 6)); s.power('+5V', g(x + 6), g(y - 6))
    W((x - 2, y - 4), (x - 2, y - 6), (x - 6, y - 6)); s.power('GND', g(x - 6), g(y - 6))
    _, rs = passive('R', g(x), g(y - 11), '100')
    s.wire(Jn['2'], rs['2'])
    W((x, y - 14), (x, y - 18)); s.label(name, g(x), g(y - 18), rot=90); J(x, y - 14)
    _, rp = passive('R', g(x - 6), g(y - 17), '4k7')
    s.wire(rp['2'], (g(x - 6), g(y - 14)), (g(x), g(y - 14)))
    s.wire(rp['1'], (g(x - 6), g(y - 24))); s.power('+3V3', g(x - 6), g(y - 24))
    if i == 0:
        s.flag(g(x + 2), g(y - 6))

# ---- J6 programming pads (pogo jig) ------------------------------------------------------------
JX, JY = 290, 44
s.text('J6: 2x4 pogo pads (2.54 mm), nothing fitted. SWD, or USB via 27R with BOOT grounding QSPI_SS.', g(248), g(22))
J6 = s.place('Connector_Generic', 'Conn_02x04_Odd_Even', 'J6', g(JX), g(JY), rot=90, value='PROG',
             footprint='Connector_PinHeader_2.54mm:PinHeader_2x04_P2.54mm_Vertical_SMD', in_bom=False, in_pos_files=False,
             description='Pogo-pin programming pads, 2x4, 2.54 mm', prop_pos={'Reference': (-9.0, -1.27), 'Value': (-9.0, 1.27)})
assert J6['1'] == (g(JX - 2), g(JY + 4)) and J6['2'] == (g(JX - 2), g(JY - 6)) and J6['8'] == (g(JX + 4), g(JY - 6))
for pin, name in {'2': 'SWDIO', '4': 'SWCLK', '6': 'RUN', '8': 'QSPI_SS'}.items():
    stub_label(J6[pin], name, 'u', length=3)
# bottom row: 1 USB_DP, 3 USB_DM, 5 GND, 7 +5V
W((JX - 2, JY + 4), (JX - 2, JY + 6), (JX - 8, JY + 6)); _, r = passive('R', g(JX - 8), g(JY + 9), '27')
s.wire((g(JX - 8), g(JY + 6)), r['1']); stub_label(r['2'], 'USB_DP', 'd', length=3)
W((JX, JY + 4), (JX, JY + 8), (JX - 4, JY + 8)); _, r = passive('R', g(JX - 4), g(JY + 11), '27')
s.wire((g(JX - 4), g(JY + 8)), r['1']); stub_label(r['2'], 'USB_DM', 'd', length=3)
W((JX + 2, JY + 4), (JX + 2, JY + 8)); s.power('GND', g(JX + 2), g(JY + 8))
W((JX + 4, JY + 4), (JX + 4, JY + 6), (JX + 8, JY + 6), (JX + 8, JY + 2)); s.power('+5V', g(JX + 8), g(JY + 2))

# ---- U4 3.3 V regulator ---------------------------------------------------------------------------
LX, LY = 44, 32
s.text('5 V comes in over the link connectors; any node can also be fed from the programming jig.', g(20), g(20))
U4 = s.place('Regulator_Linear', 'ME6211C33M5', 'U4', g(LX), g(LY), value='ME6211C33M5G',
             fields={'MPN': 'ME6211C33M5G-N', 'Manufacturer': 'Microne', 'LCSC': 'C82942'},
             prop_pos={'Reference': (0.0, -9.0), 'Value': (0.0, -11.5)})
assert U4['1'] == (g(LX - 6), g(LY - 2)) and U4['5'] == (g(LX + 6), g(LY - 2)) and U4['2'] == (g(LX), g(LY + 6))
s.no_connect(*U4['4'])
W((LX - 6, LY - 2), (LX - 10, LY - 2)); s.wire(U4['3'], (g(LX - 10), g(LY)), (g(LX - 10), g(LY - 2))); J(LX - 10, LY - 2)
W((LX - 10, LY - 2), (LX - 14, LY - 2), (LX - 14, LY - 6)); s.power('+5V', g(LX - 14), g(LY - 6))
_, ci = passive('C', g(LX - 14), g(LY + 1), *C10U, prop_pos={'Reference': (-3.4, -1.9), 'Value': (-3.4, 1.9)})
s.wire(ci['1'], (g(LX - 14), g(LY - 2))); J(LX - 14, LY - 2)
s.wire(ci['2'], (g(LX - 14), g(LY + 8)))
W((LX + 6, LY - 2), (LX + 12, LY - 2), (LX + 12, LY - 6)); s.power('+3V3', g(LX + 12), g(LY - 6))
_, co = passive('C', g(LX + 12), g(LY + 1), *C10U)
s.wire(co['1'], (g(LX + 12), g(LY - 2))); J(LX + 12, LY - 2)
s.wire(co['2'], (g(LX + 12), g(LY + 8)))
W((LX - 18, LY + 8), (LX + 12, LY + 8)); s.wire(U4['2'], (g(LX), g(LY + 8))); J(LX, LY + 8); J(LX - 14, LY + 8)
s.power('GND', g(LX), g(LY + 8)); s.flag(g(LX - 18), g(LY + 8))

# ---- D2, D4 RGB LEDs (D4 chained on DOUT, DNP: fit for double brightness) ---------------------
EX, EY = 220, 96
s.text('D1 drops the LED supply to ~4.3 V so 3.3 V logic meets the WS2812B VIH (0.7 VDD). D4 is DNP: fit it for a brighter node.', g(198), g(72))
LED_FIELDS = {'MPN': 'WS2812B-2020', 'Manufacturer': 'Worldsemi', 'LCSC': ''}
LED_PP = {'Reference': (10.0, -3.0), 'Value': (16.0, 5.0)}
D2 = s.place('LED', 'WS2812B-2020', 'D2', g(EX), g(EY), value='WS2812B-2020', fields=LED_FIELDS, prop_pos=LED_PP)
assert D2['3'] == (g(EX - 6), g(EY)) and D2['4'] == (g(EX), g(EY - 6)) and D2['1'] == (g(EX + 6), g(EY))
stub_label(D2['3'], 'LED_DIN', 'l')
DX = EX + 28                                                            # D4 column; C19 sits at EX + 48
D4 = s.place('LED', 'WS2812B-2020', 'D4', g(DX), g(EY), value='WS2812B-2020', fields=LED_FIELDS, prop_pos=LED_PP, dnp=True)
assert D4['3'] == (g(DX - 6), g(EY)) and D4['4'] == (g(DX), g(EY - 6)) and D4['1'] == (g(DX + 6), g(EY))
s.wire(D2['1'], D4['3']); s.no_connect(*D4['1'])
D1 = s.place('Device', 'D', 'D1', g(EX - 9), g(EY - 10), rot=180, value='1N4148W', footprint='Diode_SMD:D_SOD-123',
             fields={'MPN': '1N4148W', 'Manufacturer': '', 'LCSC': ''}, prop_pos={'Reference': (-2.0, -2.5), 'Value': (-3.5, 2.8)})
assert D1['2'] == (g(EX - 12), g(EY - 10)) and D1['1'] == (g(EX - 6), g(EY - 10))
s.wire(D1['1'], (g(EX), g(EY - 10)), D2['4']); J(EX, EY - 10)
s.wire(D1['2'], (g(EX - 16), g(EY - 10)), (g(EX - 16), g(EY - 14))); s.power('+5V', g(EX - 16), g(EY - 14))
_, cl = passive('C', g(EX + 48), g(EY - 7), *C100)
assert cl['1'] == (g(EX + 48), g(EY - 10))
W((EX, EY - 10), (DX, EY - 10)); s.wire((g(DX), g(EY - 10)), cl['1']); s.wire(D4['4'], (g(DX), g(EY - 10))); J(DX, EY - 10)
s.flag(g(EX + 48), g(EY - 10)); s.label('LED_VDD', g(EX + 3), g(EY - 10), rot=90)
s.wire(cl['2'], (g(EX + 48), g(EY + 8)), (g(DX), g(EY + 8))); s.wire(D4['2'], (g(DX), g(EY + 8))); J(DX, EY + 8)
W((DX, EY + 8), (EX, EY + 8)); s.wire(D2['2'], (g(EX), g(EY + 8))); s.power('GND', g(EX), g(EY + 8))

# ---- BZ1 buzzer ---------------------------------------------------------------------------------
BX, BY = 300, 92
BZ = s.place('Device', 'Buzzer', 'BZ1', g(BX), g(BY), value='Buzzer 5V', footprint='Buzzer_Beeper:Buzzer_12x9.5RM7.6',
             description='Passive magnetic buzzer, 12 mm, 5 V, THT', prop_pos={'Reference': (8.0, -1.27), 'Value': (8.0, 1.27)})
assert BZ['1'] == (g(BX - 2), g(BY - 2)) and BZ['2'] == (g(BX - 2), g(BY + 2))
Q1 = s.place('Transistor_FET', '2N7002', 'Q1', g(BX - 8), g(BY + 12), value='2N7002',
             fields={'MPN': '2N7002', 'Manufacturer': '', 'LCSC': 'C8545'}, prop_pos={'Reference': (7.0, -1.27), 'Value': (7.5, 1.27)})
assert Q1['3'] == (g(BX - 6), g(BY + 8)) and Q1['2'] == (g(BX - 6), g(BY + 16)) and Q1['1'] == (g(BX - 12), g(BY + 12))
s.wire(BZ['1'], (g(BX - 6), g(BY - 2)), (g(BX - 6), g(BY - 6))); s.power('+5V', g(BX - 6), g(BY - 6))
s.wire(BZ['2'], (g(BX - 6), g(BY + 2)), Q1['3']); J(BX - 6, BY + 8)
_, rg = passive('R', g(BX - 16), g(BY + 12), '1k', rot=90)
s.wire(rg['2'], Q1['1']); stub_label(rg['1'], 'BUZZ', 'l', length=3); J(BX - 12, BY + 12)
_, rd = passive('R', g(BX - 12), g(BY + 15), '100k')
s.wire(rd['2'], (g(BX - 12), g(BY + 18)), (g(BX - 6), g(BY + 18))); s.wire(Q1['2'], (g(BX - 6), g(BY + 18))); s.power('GND', g(BX - 6), g(BY + 18))
D3 = s.place('Device', 'D', 'D3', g(BX + 12), g(BY), rot=270, value='1N4148W', footprint='Diode_SMD:D_SOD-123',
             fields={'MPN': '1N4148W', 'Manufacturer': '', 'LCSC': ''}, prop_pos={'Reference': (5.0, -1.27), 'Value': (7.0, 1.27)})
assert D3['1'] == (g(BX + 12), g(BY - 3)) and D3['2'] == (g(BX + 12), g(BY + 3))
s.wire(D3['1'], (g(BX + 12), g(BY - 6)), (g(BX - 6), g(BY - 6))); J(BX - 6, BY - 6)
s.wire(D3['2'], (g(BX + 12), g(BY + 8)), (g(BX - 6), g(BY + 8)))

# ---- sensor port ---------------------------------------------------------------------------------
SX, SY = 200, 150
s.text('Sensor port. J5 takes off-board modules (LD2410, AM312 PIR, I2C breakouts). U3 = default variant, SW1 = "vib" variant, "bare" = header only.', g(178), g(132))
J5 = s.place('Connector_Generic', 'Conn_01x07', 'J5', g(SX), g(SY), value='SENSOR',
             footprint='Connector_PinHeader_2.54mm:PinHeader_1x07_P2.54mm_Vertical', description='Pin header 1x7, 2.54 mm',
             prop_pos={'Reference': (1.5, -11.0), 'Value': (1.5, 11.0)})
assert J5['1'] == (g(SX - 4), g(SY - 6)) and J5['7'] == (g(SX - 4), g(SY + 6))
W((SX - 4, SY - 6), (SX - 12, SY - 6), (SX - 12, SY - 12)); s.power('+5V', g(SX - 12), g(SY - 12))
W((SX - 4, SY - 4), (SX - 8, SY - 4), (SX - 8, SY - 8)); s.power('+3V3', g(SX - 8), g(SY - 8))
for pin, name in {'3': 'SENS_INT', '4': 'SDA', '5': 'SCL', '6': 'SENS_AIN'}.items():
    stub_label(J5[pin], name, 'l', length=8)
W((SX - 4, SY + 6), (SX - 8, SY + 6), (SX - 8, SY + 10)); s.power('GND', g(SX - 8), g(SY + 10))
TX, TY = 232, 172
U3 = s.place('Sensor_Distance', 'VL53L0CXV0DH1', 'U3', g(TX), g(TY), value='VL53L0CXV0DH/1', footprint='OptoDevice:ST_VL53L0X',
             fields={'MPN': 'VL53L0CXV0DH/1', 'Manufacturer': 'STMicroelectronics', 'LCSC': ''},
             variants=VARIANTS_TOF_ONLY, prop_pos={'Reference': (-9.0, -15.5), 'Value': (-9.0, 16.5)})
assert U3['11'] == (g(TX), g(TY - 12)) and U3['1'] == (g(TX + 2), g(TY - 12)) and U3['3'] == (g(TX), g(TY + 12))
s.no_connect(*U3['8'])
for pin, name in {'5': 'SENS_XSHUT', '7': 'SENS_INT', '9': 'SDA', '10': 'SCL'}.items():
    stub_label(U3[pin], name, 'l', length=6)
W((TX, TY - 12), (TX, TY - 16), (TX + 16, TY - 16)); s.power('+3V3', g(TX), g(TY - 16))
s.wire(U3['1'], (g(TX + 2), g(TY - 14)), (g(TX), g(TY - 14))); J(TX, TY - 14)
for x, (val, desc) in ((TX + 10, C100), (TX + 16, ('4u7', '4.7 uF X5R 10 V'))):
    _, c = passive('C', g(x), g(TY - 13), val, desc=desc, variants=VARIANTS_TOF_ONLY)
    s.wire(c['2'], (g(x), g(TY - 6)))
    if x != TX + 16:
        J(x, TY - 16)
W((TX + 10, TY - 6), (TX + 16, TY - 6)); s.power('GND', g(TX + 16), g(TY - 6))
W((TX, TY + 12), (TX, TY + 16)); s.wire(U3['2'], (g(TX + 2), g(TY + 14)), (g(TX), g(TY + 14))); J(TX, TY + 14)
s.power('GND', g(TX), g(TY + 16))

VX, VY = 262, 174
SW1 = s.place('Switch', 'SW_SPST', 'SW1', g(VX), g(VY), rot=90, value='SW-18010P', footprint='boards:SW-18010P',
              description='Spring vibration switch, normally open', fields={'MPN': 'SW-18010P', 'Manufacturer': '', 'LCSC': ''},
              dnp=True, variants=VARIANTS_VIB_ONLY, prop_pos={'Reference': (-9.0, -1.27), 'Value': (-9.5, 1.27)})
assert SW1['2'] == (g(VX), g(VY - 4)) and SW1['1'] == (g(VX), g(VY + 4))
W((VX, VY - 4), (VX, VY - 6), (VX, VY - 10)); s.label('SENS_INT', g(VX), g(VY - 10), rot=90); J(VX, VY - 6)
_, cd = passive('C', g(VX + 6), g(VY - 3), *C100, dnp=True, variants=VARIANTS_VIB_ONLY)
s.wire((g(VX), g(VY - 6)), cd['1']); s.wire(cd['2'], (g(VX + 6), g(VY + 8)), (g(VX), g(VY + 8)))
s.wire(SW1['1'], (g(VX), g(VY + 8))); s.power('GND', g(VX), g(VY + 8))
s.text('debounce', g(VX + 8), g(VY + 2), size=1.0)

# ---- mounting holes -------------------------------------------------------------------------------
for i in range(4):
    s.place('Mechanical', 'MountingHole', f'H{i + 1}', g(30 + 8 * i), g(200), footprint='MountingHole:MountingHole_2.2mm_M2',
            in_bom=False, in_pos_files=False, value='M2', prop_pos={'Reference': (-2.0, -3.5), 'Value': (-1.5, 3.5)})

s.write(OUT)
print('wrote', os.path.normpath(OUT))
