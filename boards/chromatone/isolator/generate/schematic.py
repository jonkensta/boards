#!/usr/bin/env python3
"""Generate boards/chromatone/chromatone.kicad_sch from the KiCad stock libraries."""
import os, re, sys, uuid
_d = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(_d, 'boardtools')):
    _d = os.path.dirname(_d)
sys.path.insert(0, _d)   # repo root, whatever depth this board sits at
from boardtools import sexpr
Q = sexpr.Quoted

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'isolator.kicad_sch')
LIBDIR = '/usr/share/kicad/symbols'
existing = sexpr.parse(open(OUT).read())
ROOT_UUID = sexpr.child(existing, 'uuid')[1]

def u(): return Q(str(uuid.uuid4()))
def n(x): return f"{x:.2f}".rstrip('0').rstrip('.') if isinstance(x, float) else str(x)

# ---------------------------------------------------------------- library symbols
_libcache = {}
def lib_symbol(lib, name):
    if lib not in _libcache:
        _libcache[lib] = sexpr.parse(open(f'{LIBDIR}/{lib}.kicad_sym').read())
    for s in sexpr.children(_libcache[lib], 'symbol'):
        if s[1] == name:
            assert sexpr.child(s, 'extends') is None, name
            s = [x for x in s]  # shallow copy
            s[1] = Q(f'{lib}:{name}')
            return s
    raise KeyError(f'{lib}:{name}')

def pin_offsets(sym):
    """{number: (x, y_screen)} relative offsets for rotation 0 (lib y flipped)."""
    out = {}
    for unit in sexpr.children(sym, 'symbol'):
        for pin in sexpr.children(unit, 'pin'):
            at = sexpr.child(pin, 'at'); num = sexpr.child(pin, 'number')[1]
            out[num] = (float(at[1]), -float(at[2]))
    return out

def xform(dx, dy, rot, mirror=None):
    if mirror == 'y': dx = -dx
    if mirror == 'x': dy = -dy
    for _ in range(rot // 90):
        dx, dy = dy, -dx
    return dx, dy

# ---------------------------------------------------------------- schematic body
lib_symbols = {}
items = []
refs = {}

def place(lib, name, ref, x, y, rot=0, value=None, footprint='', fields=None, mirror=None, in_bom=True, on_board=True, prop_pos=None, hide_value=False, description=None):
    key = f'{lib}:{name}'
    if key not in lib_symbols:
        lib_symbols[key] = lib_symbol(lib, name)
    sym = lib_symbols[key]
    lib_fp = next((p[2] for p in sexpr.children(sym, 'property') if p[1] == 'Footprint'), '')
    lib_ds = next((p[2] for p in sexpr.children(sym, 'property') if p[1] == 'Datasheet'), '')
    lib_desc = next((p[2] for p in sexpr.children(sym, 'property') if p[1] == 'Description'), '')
    fp = footprint or lib_fp
    val = value if value is not None else name
    pp = prop_pos or {}
    def prop(k, v, hide=False, dx=2.54, dy=0, rotp=None):
        px, py = pp.get(k, (dx, dy))
        if rotp is None: rotp = rot % 180   # keep text horizontal on rotated symbols
        e = ['effects', ['font', ['size', '1.27', '1.27']]]
        if hide: e.append(['hide', 'yes'])
        return ['property', Q(k), Q(v), ['at', n(x + px), n(y + py), n(rotp)], e]
    node = ['symbol', ['lib_id', Q(key)], ['at', n(x), n(y), n(rot)]]
    if mirror: node.append(['mirror', mirror])
    node += [['unit', '1'], ['exclude_from_sim', 'no'], ['in_bom', 'yes' if in_bom else 'no'],
             ['on_board', 'yes' if on_board else 'no'], ['dnp', 'no'], ['uuid', u()],
             prop('Reference', ref, hide=key.startswith('power:'), dx=2.54, dy=-1.27),
             prop('Value', val, hide=hide_value, dx=2.54, dy=1.27),
             prop('Footprint', fp, hide=True), prop('Datasheet', lib_ds, hide=True),
             prop('Description', description if description is not None else lib_desc, hide=True)]
    for k, v in (fields or {}).items():
        node.append(prop(k, v, hide=True))
    offs = pin_offsets(sym)
    pins = {}
    for num, (dx, dy) in offs.items():
        node.append(['pin', Q(num), ['uuid', u()]])
        ex, ey = xform(dx, dy, rot, mirror)
        pins[num] = (round(x + ex, 2), round(y + ey, 2))
    node.append(['instances', ['project', Q('isolator'), ['path', Q('/' + ROOT_UUID), ['reference', Q(ref)], ['unit', '1']]]])
    items.append(node)
    return pins

def wire(*pts):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        items.append(['wire', ['pts', ['xy', n(x1), n(y1)], ['xy', n(x2), n(y2)]],
                      ['stroke', ['width', '0'], ['type', 'default']], ['uuid', u()]])
def junction(x, y):
    items.append(['junction', ['at', n(x), n(y)], ['diameter', '0'], ['color', '0', '0', '0', '0'], ['uuid', u()]])
def text(s, x, y, size=1.27, bold=False):
    f = ['font', ['size', n(size), n(size)]]
    if bold: f.append(['bold', 'yes'])
    items.append(['text', Q(s), ['exclude_from_sim', 'no'], ['at', n(x), n(y), '0'], ['effects', f, ['justify', 'left', 'bottom']], ['uuid', u()]])
def box(x1, y1, x2, y2):
    items.append(['rectangle', ['start', n(x1), n(y1)], ['end', n(x2), n(y2)],
                  ['stroke', ['width', '0.3'], ['type', 'dash']], ['fill', ['type', 'none']], ['uuid', u()]])

R_FP = 'Resistor_SMD:R_0603_1608Metric'; C_FP = 'Capacitor_SMD:C_0603_1608Metric'
LED_FP = 'LED_SMD:LED_0603_1608Metric'; TP_FP = 'TestPoint:TestPoint_Pad_D1.5mm'
JST_FP = 'Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical'; HOLE_FP = 'MountingHole:MountingHole_2.7mm_M2.5'
JST = {'MPN': 'B4B-XH-A(LF)(SN)', 'Manufacturer': 'JST', 'LCSC': 'C144395'}

def pwr(name, x, y, value=None, ref=None):
    global _pwr_n
    _pwr_n += 1
    return place('power', name, ref or f'#PWR{_pwr_n:02d}', x, y, value=value, in_bom=False, on_board=False)
_pwr_n = 0
_flag_n = 0
def flag(x, y, rot=0):
    global _flag_n
    _flag_n += 1
    return place('power', 'PWR_FLAG', f'#FLG{_flag_n:02d}', x, y, rot=rot, in_bom=False, on_board=False, hide_value=True)

# ---- everything below is placed in grid units (1.27 mm) so ERC sees on-grid endpoints
G = 1.27
SHIFT = -40
def g(k): return round((k + SHIFT) * G, 2)
Y_VCC, Y_CLK, Y_DATA, Y_GND, Y_TOP, Y_BOT = g(76), g(78), g(80), g(82), g(74), g(84)

U1 = place('Isolator', 'ISO7720D', 'U1', g(120), Y_DATA, value='ISO7720D',
           fields={'MPN': 'ISO7720DR', 'Manufacturer': 'Texas Instruments', 'LCSC': 'C486037'},
           prop_pos={'Reference': (-7.62, -9.5), 'Value': (0, 9.5)})
J1 = place('Connector', 'Conn_01x04_Pin', 'J1', g(84), Y_CLK, value='Pi SPI', footprint=JST_FP, fields=JST,
           prop_pos={'Reference': (-1.27, -10.2), 'Value': (-1.27, -8.2)})
J2 = place('Connector', 'Conn_01x04_Pin', 'J2', g(155), Y_CLK, mirror='y', value='Strip', footprint=JST_FP, fields=JST,
           prop_pos={'Reference': (-4.0, -10.2), 'Value': (-4.0, -8.2)})

# J1: 1 3V3, 2 SCLK, 3 MOSI, 4 GND        U1: 1 VCC1 2 INA 3 INB 4 GND1 | 5 GND2 6 OUTB 7 OUTA 8 VCC2
# J2: 1 5V, 2 CLK, 3 DATA, 4 GND
assert J1['2'] == (g(88), Y_CLK) and U1['2'] == (g(112), Y_CLK), (J1, U1)
assert J2['2'] == (g(151), Y_CLK) and U1['7'] == (g(128), Y_CLK), (J2, U1)

# domain A supplies at the pins
wire(J1['1'], (g(90), Y_VCC), (g(90), Y_TOP)); pwr('+3V3', g(90), Y_TOP)
wire(J1['4'], (g(90), Y_GND), (g(90), Y_BOT)); pwr('GND', g(90), Y_BOT)
wire(U1['1'], (g(110), Y_VCC), (g(110), Y_TOP)); pwr('+3V3', g(110), Y_TOP)
wire(U1['4'], (g(110), Y_GND), (g(110), Y_BOT)); pwr('GND', g(110), Y_BOT)
# SCLK / MOSI with test points
wire(J1['2'], (g(98), Y_CLK), U1['2']); junction(g(98), Y_CLK)
TP1 = place('Connector', 'TestPoint', 'TP1', g(98), Y_CLK, value='SCLK', footprint=TP_FP, in_bom=False, prop_pos={'Reference': (-2.0, -5.5), 'Value': (-2.0, -3.6)})
wire(J1['3'], (g(102), Y_DATA), U1['3']); junction(g(102), Y_DATA)
TP2 = place('Connector', 'TestPoint', 'TP2', g(102), Y_DATA, rot=180, value='MOSI', footprint=TP_FP, in_bom=False, prop_pos={'Reference': (-2.0, 6.7), 'Value': (-2.0, 4.8)})

# domain B supplies at the pins
wire(U1['8'], (g(130), Y_VCC), (g(130), Y_TOP)); pwr('+5V', g(130), Y_TOP, value='+5V_LED')
wire(U1['5'], (g(130), Y_GND), (g(130), Y_BOT)); pwr('GNDPWR', g(130), Y_BOT, value='GND_LED')  # label auto-placed right of the symbol
wire(J2['1'], (g(149), Y_VCC), (g(149), Y_TOP)); pwr('+5V', g(149), Y_TOP, value='+5V_LED')
wire(J2['4'], (g(149), Y_GND), (g(149), Y_BOT)); pwr('GNDPWR', g(149), Y_BOT, value='GND_LED')
# CLK / DATA through series resistors, with test points
R1 = place('Device', 'R', 'R1', g(136), Y_CLK, rot=90, value='47', footprint=R_FP, prop_pos={'Reference': (-3.0, -2.3), 'Value': (3.5, -2.3)})
R2 = place('Device', 'R', 'R2', g(136), Y_DATA, rot=90, value='47', footprint=R_FP, prop_pos={'Reference': (-3.0, 2.3), 'Value': (3.5, 2.3)})
assert R1['1'] == (g(133), Y_CLK) and R1['2'] == (g(139), Y_CLK), R1
wire(U1['7'], R1['1']); wire(R1['2'], (g(146), Y_CLK), J2['2']); junction(g(146), Y_CLK)
TP3 = place('Connector', 'TestPoint', 'TP3', g(146), Y_CLK, value='CLK', footprint=TP_FP, in_bom=False, prop_pos={'Reference': (-2.0, -5.5), 'Value': (-2.0, -3.6)})
wire(U1['6'], R2['1']); wire(R2['2'], (g(146), Y_DATA), J2['3']); junction(g(146), Y_DATA)
TP4 = place('Connector', 'TestPoint', 'TP4', g(146), Y_DATA, rot=180, value='DATA', footprint=TP_FP, in_bom=False, prop_pos={'Reference': (-2.0, 6.7), 'Value': (-2.0, 4.8)})

# ---- decoupling + indicator clusters ------------------------------------------
def cluster(x0, vcc, vname, gnd, gname, cref, rref, dref, led_color, gnd_tp):
    rail_top, rail_bot = g(90), g(100)
    for i, (ref, val, desc) in enumerate([(cref[0], '100n', '100 nF X7R 50 V'), (cref[1], '10u', '10 uF X5R 10 V')]):
        x = g(x0 + i * 8)
        c = place('Device', 'C', ref, x, g(95), value=val, footprint=C_FP, description=desc, prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
        assert c['1'] == (x, g(92)) and c['2'] == (x, g(98)), c
        wire(c['1'], (x, rail_top)); wire(c['2'], (x, rail_bot))
        pwr(vcc, x, rail_top, value=vname); pwr(gnd, x, rail_bot, value=gname)
    # PWR_FLAGs on both rails, hanging off the first cap's nodes
    wire((g(x0), rail_top), (g(x0 - 6), rail_top)); junction(g(x0), rail_top); flag(g(x0 - 6), rail_top)
    wire((g(x0), rail_bot), (g(x0 - 6), rail_bot)); junction(g(x0), rail_bot); flag(g(x0 - 6), rail_bot, rot=180)
    junction(g(x0 - 3), rail_bot)
    place('Connector', 'TestPoint', gnd_tp[0], g(x0 - 3), rail_bot, rot=180, value=gnd_tp[1], footprint=TP_FP, in_bom=False,
          prop_pos={'Reference': (-2.0, 6.7), 'Value': (-2.0, 4.8)})
    # indicator LED: rail -> 1k -> LED -> gnd
    x = g(x0 + 18)
    r = place('Device', 'R', rref, x, g(93), value='1k', footprint=R_FP, prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
    d = place('Device', 'LED', dref, x, g(101), rot=90, value=led_color, footprint=LED_FP, prop_pos={'Reference': (1.5, -1.27), 'Value': (1.5, 1.27)})
    assert r['1'] == (x, g(90)) and r['2'] == (x, g(96)), r
    assert d['2'] == (x, g(98)) and d['1'] == (x, g(104)), d
    wire((x, g(88)), r['1']); pwr(vcc, x, g(88), value=vname)
    wire(r['2'], d['2']); wire(d['1'], (x, g(106))); pwr(gnd, x, g(106), value=gname)

cluster(97, '+3V3', None, 'GND', None, ('C1', 'C2'), 'R3', 'D1', 'GREEN', ('TP5', 'GND_A'))
cluster(136, '+5V', '+5V_LED', 'GNDPWR', 'GND_LED', ('C3', 'C4'), 'R4', 'D2', 'BLUE', ('TP6', 'GND_B'))

# ---- mounting holes ----------------------------------------------------------
for i in range(4):
    place('Mechanical', 'MountingHole', f'H{i+1}', g(164 + i * 8), g(98), value='M2.5', footprint=HOLE_FP, in_bom=False, prop_pos={'Reference': (-2.0, -3.0), 'Value': (-2.0, -1.0)})

# ---- annotation --------------------------------------------------------------
box(g(78), g(66), g(116), g(110)); box(g(124), g(66), g(160), g(110))
text('DOMAIN A: Pi side, 3.3 V, Pi battery', g(78) + 0.5, g(66) - 1, 1.5, True)
text('DOMAIN B: LED side, 5 V, LED battery', g(124) + 0.5, g(66) - 1, 1.5, True)
text('Isolation barrier: only SPI CLK and DATA cross, A -> B. GND and GND_LED never touch.', g(78) + 0.5, g(114), 1.27)
text('J1 to Pi header: 1=3V3 (pin 1), 2=SCLK (GPIO11), 3=MOSI (GPIO10), 4=GND.', g(78) + 0.5, g(117), 1.27)
text('J2 to pixel 0 of the strip: 1=5V, 2=CI, 3=DI, 4=GND. Tap 5V/GND at the strip end so VCC2 never exceeds the pixel rail.', g(78) + 0.5, g(120), 1.27)
text('R1/R2 tame ringing on the CLK/DATA leads; keep leads to pixel 0 short, twisted with GND_LED.', g(78) + 0.5, g(123), 1.27)

# ---------------------------------------------------------------- assemble
sch = ['kicad_sch', ['version', '20250114'], ['generator', Q('eeschema')], ['generator_version', Q('9.0')],
       ['uuid', Q(ROOT_UUID)], ['paper', Q('A4')],
       ['title_block', ['title', Q('Chromatone isolated SPI daughterboard')], ['date', Q('2026-09-15')], ['rev', Q('A')],
        ['comment', '1', Q('Pi Zero 2 W (3.3 V) -> ISO7720 -> SK9822 strip (5 V), galvanically isolated')]],
       ['lib_symbols'] + [lib_symbols[k] for k in sorted(lib_symbols)]]
sch += items
sch.append(['sheet_instances', ['path', Q('/'), ['page', Q('1')]]])
open(OUT, 'w').write(sexpr.dumps(sch) + '\n')
print('wrote', OUT, len(items), 'items')
