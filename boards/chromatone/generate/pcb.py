#!/usr/bin/env python3
"""Generate boards/chromatone/chromatone.kicad_pcb: placement, routing, pours, outline."""
import math, os, sys, uuid
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
from boardtools import sexpr
Q = sexpr.Quoted
S = os.path.dirname(os.path.abspath(__file__))
PCB = os.path.join(S, '..', 'chromatone.kicad_pcb')
FPDIR = '/usr/share/kicad/footprints'
OX, OY = 50.0, 50.0          # board origin in KiCad sheet space
W, H = 46.0, 30.0

def u(): return Q(str(uuid.uuid4()))
def n(v): return f"{v:.4f}".rstrip('0').rstrip('.') if isinstance(v, float) else str(v)
def P(x, y): return (OX + x, OY + y)

# ---------------------------------------------------------------- netlist from the schematic
net = sexpr.parse(open(os.path.join(S, 'chromatone.net')).read())
nets = {}   # name -> code
node_net = {}  # (ref, pin) -> name
for nn in sexpr.children(sexpr.child(net, 'nets'), 'net'):
    name = sexpr.child(nn, 'name')[1]; code = int(sexpr.child(nn, 'code')[1])
    nets[name] = code
    for x in sexpr.children(nn, 'node'):
        node_net[(sexpr.child(x, 'ref')[1], sexpr.child(x, 'pin')[1])] = name
comp_uuid = {}; comp_value = {}; comp_fp = {}; comp_fields = {}; comp_meta = {}
for c in sexpr.children(sexpr.child(net, 'components'), 'comp'):
    ref = c[1][1]
    comp_uuid[ref] = sexpr.child(c, 'tstamps')[1]
    comp_value[ref] = sexpr.child(c, 'value')[1]
    comp_fp[ref] = sexpr.child(c, 'footprint')[1]
    comp_fields.setdefault(ref, {})
    ds = sexpr.child(c, 'datasheet'); de = sexpr.child(c, 'description')
    comp_ds = ds[1] if ds is not None and len(ds) > 1 else ''
    comp_de = de[1] if de is not None and len(de) > 1 else ''
    fields = {}
    fl = sexpr.child(c, 'fields')
    if fl:
        for f in sexpr.children(fl, 'field'):
            if len(f) > 2: fields[f[1][1]] = f[2]
    comp_fields[ref] = fields
    comp_meta[ref] = (comp_ds, comp_de)

# ---------------------------------------------------------------- base board from the template (KiCad-10 native)
board = sexpr.parse(open(PCB).read())
board = [x for x in board if not (isinstance(x, list) and x[0] in ('gr_line', 'gr_rect', 'footprint', 'segment', 'via', 'zone', 'gr_text', 'net') )]
# aux (drill/place) origin bottom-left, grid origin top-left
setup = sexpr.child(board, 'setup')
for el in setup:
    if isinstance(el, list) and el[0] == 'aux_axis_origin': el[1:] = [n(OX), n(OY + H)]
    if isinstance(el, list) and el[0] == 'grid_origin': el[1:] = [n(OX), n(OY)]
# nets: insert after (general)/(paper)/(layers)/(setup) i.e. before footprints (order is not semantically important)
net_nodes = [['net', '0', Q('')]] + [['net', str(code), Q(name)] for name, code in sorted(nets.items(), key=lambda kv: kv[1])]
board += net_nodes

items = []
def rot_pt(px, py, rot):
    r = math.radians(rot)
    return (px * math.cos(r) + py * math.sin(r), -px * math.sin(r) + py * math.cos(r))

def footprint(ref, x, y, rot=0, ref_pos=None, ref_fab=False, val_pos=None):
    lib, name = comp_fp[ref].split(':')
    fp = sexpr.parse(open(f'{FPDIR}/{lib}.pretty/{name}.kicad_mod').read())
    fp[1] = Q(f'{lib}:{name}')
    out = ['footprint', fp[1]]
    # keep layer/descr/tags/attr/graphics/pads/model; replace properties and add placement + path
    props_seen = set()
    for el in fp[2:]:
        if not isinstance(el, list):
            continue
        head = el[0]
        if head in ('version', 'generator', 'generator_version', 'tedit', 'tstamp', 'uuid'):
            continue
        if head == 'property':
            k = el[1]
            props_seen.add(k)
            val = {'Reference': ref, 'Value': comp_value[ref], 'Footprint': comp_fp[ref],
                   'Datasheet': comp_meta[ref][0], 'Description': comp_meta[ref][1]}.get(k, el[2] if len(el) > 2 else '')
            el = ['property', Q(k), Q(val)] + [c for c in el[3:] if isinstance(c, list)]
            if k in ('Reference', 'Value'):
                el = [c for c in el if not (isinstance(c, list) and c[0] in ('hide', 'at', 'layer', 'effects'))]
                pos = ref_pos if k == 'Reference' else val_pos
                on_silk = (k == 'Reference' and not ref_fab) or (k == 'Value' and val_pos is not None)
                el.append(['at', n(pos[0]) if pos else '0', n(pos[1]) if pos else '0', '0'])
                el.append(['layer', Q('F.SilkS' if on_silk else 'F.Fab')])
                if not on_silk and not (k == 'Reference' and not ref_fab): el.append(['hide', 'yes'])
                el.append(['effects', ['font', ['size', '0.8', '0.8'], ['thickness', '0.15']]])
        if head in ('fp_text', 'pad'):
            at = sexpr.child(el, 'at')
            if at is not None:
                a = float(at[3]) if len(at) > 3 else 0.0
                at[:] = ['at', at[1], at[2], n((a + rot) % 360)]
            if head == 'pad':
                nname = node_net.get((ref, el[1]))
                el = [c for c in el if not (isinstance(c, list) and c[0] == 'net')]
                if nname:
                    el.append(['net', str(nets[nname]), Q(nname)])
        # every graphic/pad element gets a uuid
        if head in ('property', 'fp_text', 'fp_line', 'fp_rect', 'fp_circle', 'fp_arc', 'fp_poly', 'pad', 'model'):
            el = [c for c in el if not (isinstance(c, list) and c[0] == 'uuid')]
            if head != 'model':
                el.append(['uuid', u()])
        out.append(el)
    for k, v in [('Footprint', comp_fp[ref]), ('Datasheet', comp_meta[ref][0]), ('Description', comp_meta[ref][1])]:
        if k not in props_seen:
            out.append(['property', Q(k), Q(v), ['at', '0', '0', n(rot)], ['layer', Q('F.Fab')], ['hide', 'yes'], ['uuid', u()],
                        ['effects', ['font', ['size', '1', '1'], ['thickness', '0.15']]]])
    for k, v in comp_fields[ref].items():
        if k in ('MPN', 'Manufacturer', 'LCSC'):
            out.append(['property', Q(k), Q(v), ['at', '0', '0', n(rot)], ['layer', Q('F.Fab')], ['hide', 'yes'], ['uuid', u()],
                        ['effects', ['font', ['size', '1', '1'], ['thickness', '0.15']]]])
    X, Y = P(x, y)
    out[2:2] = [['layer', Q('F.Cu')], ['uuid', u()], ['at', n(X), n(Y), n(rot)]]
    # drop the .kicad_mod's own (layer ..) if duplicated later
    seen_layer = False
    cleaned = []
    for el in out:
        if isinstance(el, list) and el[0] == 'layer':
            if seen_layer: continue
            seen_layer = True
        cleaned.append(el)
    cleaned.append(['path', Q('/' + comp_uuid[ref])])
    cleaned.append(['sheetname', Q('/')]); cleaned.append(['sheetfile', Q('chromatone.kicad_sch')])
    items.append(cleaned)

def seg(net_name, width, *pts, layer='F.Cu'):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        (X1, Y1), (X2, Y2) = P(x1, y1), P(x2, y2)
        items.append(['segment', ['start', n(X1), n(Y1)], ['end', n(X2), n(Y2)], ['width', n(width)],
                      ['layer', Q(layer)], ['net', str(nets[net_name])], ['uuid', u()]])
def via(net_name, x, y):
    X, Y = P(x, y)
    items.append(['via', ['at', n(X), n(Y)], ['size', '0.6'], ['drill', '0.3'], ['layers', Q('F.Cu'), Q('B.Cu')],
                  ['net', str(nets[net_name])], ['uuid', u()]])
def zone(net_name, zname, x1, y1, x2, y2, layer='B.Cu'):
    pts = [P(x1, y1), P(x2, y1), P(x2, y2), P(x1, y2)]
    items.append(['zone', ['net', str(nets[net_name])], ['net_name', Q(net_name)], ['layers', Q(layer)], ['uuid', u()],
                  ['name', Q(zname)], ['hatch', 'edge', '0.5'], ['connect_pads', ['clearance', '0.3']],
                  ['min_thickness', '0.25'], ['filled_areas_thickness', 'no'],
                  ['fill', 'yes', ['thermal_gap', '0.5'], ['thermal_bridge_width', '0.5']],
                  ['polygon', ['pts'] + [['xy', n(X), n(Y)] for X, Y in pts]]])
def gr_line(x1, y1, x2, y2, layer, width):
    (X1, Y1), (X2, Y2) = P(x1, y1), P(x2, y2)
    items.append(['gr_line', ['start', n(X1), n(Y1)], ['end', n(X2), n(Y2)], ['stroke', ['width', n(width)], ['type', 'default']],
                  ['layer', Q(layer)], ['uuid', u()]])
def gr_text(s, x, y, layer='F.SilkS', size=0.8, rot=0, justify=None):
    X, Y = P(x, y)
    eff = ['effects', ['font', ['size', n(size), n(size)], ['thickness', n(size * 0.15)]]]
    if justify: eff.append(['justify'] + justify)
    items.append(['gr_text', Q(s), ['at', n(X), n(Y), n(rot)], ['layer', Q(layer)], ['uuid', u()], eff])

SIG, PWR = 0.25, 0.4
# ---------------------------------------------------------------- placement (board-local mm, y down)
for i, (hx, hy) in enumerate([(3.5, 3.5), (42.5, 3.5), (3.5, 26.5), (42.5, 26.5)]):
    footprint(f'H{i+1}', hx, hy, ref_fab=True)
footprint('J1', 4.5, 10.5, 270, ref_pos=(11.5, 0))   # ref text below the connector (offset is in board coords: +x local after rot... see note)      # pads: 1 3V3 (4.5,10.5) 2 SCLK (4.5,13) 3 MOSI (4.5,15.5) 4 GND (4.5,18)
footprint('J2', 41.5, 10.5, 270, ref_pos=(11.5, 0))     # pads: 1 5V (41.5,10.5) 2 CLK 13 3 DATA 15.5 4 GND 18
footprint('U1', 23.0, 16.0, 0, ref_pos=(-4.0, 4.7))       # pads 1-4 x=20.525 y=14.095/15.365/16.635/17.905; 5-8 x=25.475 same y reversed
footprint('C1', 17.0, 12.3, 0, ref_fab=True)       # 1 (16.225) +3V3, 2 (17.775) GND
footprint('C2', 17.0, 9.9, 0, ref_fab=True)
footprint('C3', 29.0, 12.3, 180, ref_fab=True)     # 1 (29.775) +5V_LED, 2 (28.225) GND_LED
footprint('C4', 29.0, 9.9, 180, ref_fab=True)
footprint('R1', 31.0, 15.365, 0, ref_fab=True)     # 1 (30.175) from U1.7, 2 (31.825) to J2 CLK
footprint('R2', 31.0, 17.8, 0, ref_fab=True)
footprint('R3', 13.5, 23.5, 0, ref_fab=True)       # 1 (12.675) +3V3, 2 (14.325) -> D1 A
footprint('D1', 17.5, 23.5, 180, ref_fab=True)     # 1 K (18.2875) GND, 2 A (16.7125)
footprint('R4', 32.5, 23.5, 180, ref_fab=True)     # 1 (33.325) +5V_LED, 2 (31.675) -> D2 A
footprint('D2', 28.5, 23.5, 0, ref_fab=True)       # 1 K (27.7125) GND_LED, 2 A (29.2875)
footprint('TP1', 11.5, 10.0, ref_fab=True, val_pos=(0, -2.0)); footprint('TP2', 10.0, 20.5, ref_fab=True, val_pos=(0, 2.0))
footprint('TP3', 34.0, 11.0, ref_fab=True, val_pos=(0, -2.0)); footprint('TP4', 35.0, 21.5, ref_fab=True, val_pos=(0, 2.0))

# ---------------------------------------------------------------- routing, domain A
seg('+3V3', PWR, (4.5, 10.5), (4.5, 8.0), (16.225, 8.0), (16.225, 14.095), (20.525, 14.095))
seg('+3V3', PWR, (4.5, 10.5), (2.5, 12.5), (2.5, 21.5), (4.5, 23.5), (12.675, 23.5))
seg('GND', SIG, (17.775, 9.9), (17.775, 12.3), (19.5, 12.3)); via('GND', 19.5, 12.3)
seg('GND', SIG, (20.525, 17.905), (18.75, 17.905)); via('GND', 18.75, 17.905)
seg('GND', SIG, (18.2875, 23.5), (19.8, 23.5)); via('GND', 19.8, 23.5)
seg('Net-(J1-Pin_2)', SIG, (4.5, 13), (12.0, 13), (14.365, 15.365), (20.525, 15.365))
seg('Net-(J1-Pin_2)', SIG, (11.5, 13), (11.5, 10.0))
seg('Net-(J1-Pin_3)', SIG, (4.5, 15.5), (6.0, 15.5), (7.135, 16.635), (20.525, 16.635))
seg('Net-(J1-Pin_3)', SIG, (10.0, 16.635), (10.0, 20.5))
seg('Net-(D1-A)', SIG, (14.325, 23.5), (16.7125, 23.5))
# ---------------------------------------------------------------- routing, domain B
seg('+5V_LED', PWR, (41.5, 10.5), (41.5, 8.0), (29.775, 8.0), (29.775, 14.095), (25.475, 14.095))
seg('+5V_LED', PWR, (41.5, 10.5), (43.5, 12.5), (43.5, 21.5), (41.5, 23.5), (33.325, 23.5))
seg('GND_LED', SIG, (28.225, 9.9), (28.225, 12.3), (26.5, 12.3)); via('GND_LED', 26.5, 12.3)
seg('GND_LED', SIG, (25.475, 17.905), (27.25, 17.905)); via('GND_LED', 27.25, 17.905)
seg('GND_LED', SIG, (27.7125, 23.5), (26.2, 23.5)); via('GND_LED', 26.2, 23.5)
seg('Net-(U1-OUTA)', SIG, (25.475, 15.365), (30.175, 15.365))
seg('Net-(J2-Pin_2)', SIG, (31.825, 15.365), (38.5, 15.365), (40.865, 13.0), (41.5, 13.0))
seg('Net-(J2-Pin_2)', SIG, (34.0, 15.365), (34.0, 11.0))
seg('Net-(U1-OUTB)', SIG, (25.475, 16.635), (28.5, 16.635), (29.665, 17.8), (30.175, 17.8))
seg('Net-(J2-Pin_3)', SIG, (31.825, 17.8), (38.5, 17.8), (40.8, 15.5), (41.5, 15.5))
seg('Net-(J2-Pin_3)', SIG, (35.0, 17.8), (35.0, 21.5))
seg('Net-(D2-A)', SIG, (29.2875, 23.5), (31.675, 23.5))
# ---------------------------------------------------------------- pours: split grounds, 3 mm barrier under U1
zone('GND', 'GND_A', 0, 0, 21.5, H)
zone('GND_LED', 'GND_B', 24.5, 0, W, H)
# ---------------------------------------------------------------- outline, silk
for (x1, y1, x2, y2) in [(0, 0, W, 0), (W, 0, W, H), (W, H, 0, H), (0, H, 0, 0)]:
    gr_line(x1, y1, x2, y2, 'Edge.Cuts', 0.1)
for layer in ('F.SilkS', 'B.SilkS'):
    gr_line(23.0, 4.0, 23.0, 11.5, layer, 0.15)
    gr_line(23.0, 21.0, 23.0, 26.0, layer, 0.15)
gr_text('PI  3.3V', 12.0, 2.2, size=1.0)
gr_text('LED  5V', 34.0, 2.2, size=1.0)
gr_text('ISOLATED', 23.0, 27.8, size=0.8)
for y, lab in zip((10.5, 13, 15.5, 18), ('3V3', 'SCLK', 'MOSI', 'GND')):
    gr_text(lab, 7.7, y, size=0.8, justify=['left'])
for y, lab in zip((10.5, 13, 15.5, 18), ('5V', 'CI', 'DI', 'GND')):
    gr_text(lab, 37.4, y, size=0.8, justify=['right'])
gr_text('chromatone rev A', 23.0, 2.2, layer='B.SilkS', size=0.8, justify=['mirror'])

board += items
open(PCB, 'w').write(sexpr.dumps(board) + '\n')
print('wrote', PCB, len(items), 'items')
