import contextlib
import io
import os
import tempfile
import unittest

from boardtools import jlcpcb, offgrid, pcb, pcbgen, schgen, sexpr

BOARD = '''(kicad_pcb (version 20260206) (generator "pcbnew")
  (paper "A4")
  (title_block (title "Notes: (layers are listed below) \\"quoted\\"") (rev "B"))
  (layers
    (0 "F.Cu" signal "Top copper )")
    (4 "In1.Cu" signal)
    (6 "In2.Cu" signal)
    (2 "B.Cu" signal)
    (25 "Edge.Cuts" user)
  )
  (gr_text "(" (at 60 55) (layer "F.SilkS"))
  (gr_text ")" (at 62 55) (layer "F.SilkS"))
  (gr_text "a \\"quoted\\" (legend)" (at 70 55) (layer "F.SilkS"))
)
'''


class SexprTests(unittest.TestCase):
    def test_quoted_parens_are_atoms(self):
        root = sexpr.parse(BOARD)
        self.assertEqual(root[0], "kicad_pcb")
        texts = [n[1] for n in sexpr.children(root, "gr_text")]
        self.assertEqual(texts, ["(", ")", 'a "quoted" (legend)'])

    def test_unbalanced(self):
        with self.assertRaises(ValueError):
            sexpr.parse("(kicad_pcb (layers)")
        with self.assertRaises(ValueError):
            sexpr.parse("(kicad_pcb))")


class DumpsTests(unittest.TestCase):
    def test_roundtrip_preserves_quoting_and_escapes(self):
        text = '(kicad_pcb (version 20260206) (gr_text "a \\"q\\" (x)" (at 1 2 0) (layer "F.SilkS")) (layers (0 "F.Cu" signal)))'
        root = sexpr.parse(text)
        out = sexpr.dumps(root)
        self.assertEqual(sexpr.parse(out), root)
        self.assertIn('(version 20260206)', out)          # bare atom stays bare
        self.assertIn('"F.Cu"', out)                      # quoted atom stays quoted
        self.assertIn('"a \\"q\\" (x)"', out)           # escapes re-emitted
        self.assertIsInstance(sexpr.parse(out)[2][1], sexpr.Quoted)

    def test_generated_quoting(self):
        node = ["property", sexpr.Quoted("Value"), sexpr.Quoted("47"), ["at", "0", "0", "0"]]
        self.assertEqual(sexpr.dumps(node), '(property "Value" "47"\n\t(at 0 0 0)\n)')
        self.assertEqual(sexpr.dumps(["uuid", sexpr.Quoted("x")]), '(uuid "x")')
        self.assertEqual(sexpr.dumps(["name", ""]), '(name "")')


class PcbTests(unittest.TestCase):
    def test_copper_layers_and_title(self):
        root = sexpr.parse(BOARD)
        self.assertEqual(pcb.copper_layers(root), ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"])
        self.assertEqual(pcb.title_block(root)["rev"], "B")

    def test_not_a_board(self):
        with tempfile.NamedTemporaryFile("w", suffix=".kicad_pcb", delete=False) as f:
            f.write('(kicad_sch (version 1))')
        try:
            with self.assertRaises(ValueError):
                pcb.load(f.name)
        finally:
            os.unlink(f.name)


class JlcpcbTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def path(self, name, content=None):
        p = os.path.join(self.dir, name)
        if content is not None:
            with open(p, "w", newline="") as f:
                f.write(content)
        return p

    def test_pos(self):
        src = self.path("pos.csv", 'Ref,Val,Package,PosX,PosY,Rot,Side\n'
                                   '"R1","10k","R_0603","10.0000","-5.0000","90.000000","top"\n'
                                   '"C1","100n","C_0603","12.0000","-7.0000","0.000000","bottom"\n')
        dst = self.path("cpl.csv")
        self.assertEqual(jlcpcb.convert_pos(src, dst), 2)
        with open(dst) as f:
            self.assertEqual(f.read().splitlines(), [
                "Designator,Mid X,Mid Y,Rotation,Layer",
                "R1,10.0000,-5.0000,90.000000,Top",
                "C1,12.0000,-7.0000,0.000000,Bottom",
            ])

    def test_bom(self):
        src = self.path("bom.csv", '"Refs","Value","Description","Footprint","MPN","Manufacturer","LCSC","Qty"\n'
                                   '"R1,R2","10k","","R_0603","RC0603FR-0710KL","Yageo","C98220","2"\n'
                                   '"C1","100n","100 nF X7R 50 V","C_0603","","","","1"\n')
        dst = self.path("jlc-bom.csv")
        self.assertEqual(jlcpcb.convert_bom(src, dst), ["C1"])
        with open(dst) as f:
            lines = f.read().splitlines()
        self.assertEqual(lines[1], '10k,"R1,R2",R_0603,C98220')
        self.assertEqual(lines[2], '100n (100 nF X7R 50 V),C1,C_0603,')
        with self.assertRaises(ValueError):
            jlcpcb.convert_bom(src, dst, require_lcsc=True)

    def test_wrong_input(self):
        for content in ("a,b\n1,2\n", "a,b\n", ""):
            src = self.path("x.csv", content)
            with self.assertRaises(ValueError):
                jlcpcb.convert_pos(src, self.path("y.csv"))
            with self.assertRaises(ValueError):
                jlcpcb.convert_bom(src, self.path("y.csv"))

    def test_empty_but_valid(self):
        src = self.path("pos.csv", "Ref,Val,Package,PosX,PosY,Rot,Side\n")
        self.assertEqual(jlcpcb.convert_pos(src, self.path("cpl.csv")), 0)
        src = self.path("bom.csv", '"Refs","Value","Footprint","MPN","Manufacturer","LCSC","Qty"\n')
        self.assertEqual(jlcpcb.convert_bom(src, self.path("b.csv")), [])

    def test_bad_side(self):
        src = self.path("pos.csv", "Ref,Val,Package,PosX,PosY,Rot,Side\nR1,1k,X,0,0,0,middle\n")
        with self.assertRaises(ValueError):
            jlcpcb.convert_pos(src, self.path("cpl.csv"))


PCBGEN_TEMPLATE = '''(kicad_pcb (version 20260206) (generator "pcbnew")
  (layers (0 "F.Cu" signal) (4 "In1.Cu" signal) (6 "In2.Cu" signal) (4 "In1.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))
  (setup (grid_origin 0 0) (aux_axis_origin 0 0))
  (net 0 "")
  (net 1 "stale")
  (segment (start 0 0) (end 1 1) (width 0.2) (layer "F.Cu") (net 1))
)
'''

PCBGEN_NETLIST = '''(export (version "E")
  (components
    (comp (ref "C1") (value "100n") (footprint "T:cap") (datasheet "~") (description "cap")
      (property (name "dnp"))
      (variants (variant (name "vib") (property (name "dnp") (value "0"))))
      (tstamps "aaaa"))
    (comp (ref "TP1") (value "GND") (footprint "T:noattr") (property (name "exclude_from_bom")) (tstamps "bbbb")))
  (nets
    (net (code "1") (name "GND") (node (ref "C1") (pin "1")) (node (ref "TP1") (pin "1")))
    (net (code "2") (name "SIG") (node (ref "C1") (pin "2")))))
'''

PCBGEN_FOOTPRINTS = {
    "cap": '''(footprint "cap" (version 20240108) (generator "x") (layer "F.Cu") (attr smd)
  (property "Reference" "REF**" (at 0 0 0) (layer "F.SilkS") (effects (font (size 1 1))))
  (property "Value" "V" (at 0 0 0) (layer "F.Fab") (effects (font (size 1 1))))
  (pad "1" smd rect (at -1 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste"))
  (pad "2" smd rect (at 1 0) (size 0.5 0.5) (layers "F.Cu" "F.Paste")))
''',
    "noattr": '''(footprint "noattr" (version 20240108) (generator "x") (layer "F.Cu")
  (property "Reference" "REF**" (at 0 0 0) (layer "F.SilkS") (effects (font (size 1 1))))
  (property "Value" "V" (at 0 0 0) (layer "F.Fab") (effects (font (size 1 1))))
  (pad "1" smd circle (at 0 0) (size 1 1) (layers "F.Cu")))
''',
}


class PcbgenTests(unittest.TestCase):
    """Board generation from a template, a netlist and a footprint library, all handwritten."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        os.makedirs(os.path.join(d, "T.pretty"))
        for name, text in PCBGEN_FOOTPRINTS.items():
            with open(os.path.join(d, "T.pretty", f"{name}.kicad_mod"), "w") as f:
                f.write(text)
        self.template = os.path.join(d, "template.kicad_pcb")
        with open(self.template, "w") as f:
            f.write(PCBGEN_TEMPLATE)
        self.netlist = os.path.join(d, "x.net")
        with open(self.netlist, "w") as f:
            f.write(PCBGEN_NETLIST)
        self.saved_dir = pcbgen.FOOTPRINT_DIR
        pcbgen.FOOTPRINT_DIR = d

    def tearDown(self):
        pcbgen.FOOTPRINT_DIR = self.saved_dir
        self.tmp.cleanup()

    def build(self, copper_layers, template=None):
        b = pcbgen.Board(template or self.template, pcbgen.Netlist(self.netlist), "x.kicad_sch", 10, 10,
                         origin=(0, 0), copper_layers=copper_layers)
        c1 = b.footprint("C1", 2, 3, 90)
        b.footprint("TP1", 5, 5)
        out = os.path.join(self.tmp.name, f"out{copper_layers}.kicad_pcb")
        b.write(out)
        return c1, sexpr.parse(open(out).read())

    def test_copper_layers_idempotent(self):
        # the template already carries stale/duplicated inner layers; the result must have exactly
        # the requested set, and re-reading the output as the template must not change it
        _, root = self.build(4)
        self.assertEqual(pcb.copper_layers(root), ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"])
        out4 = os.path.join(self.tmp.name, "out4.kicad_pcb")
        _, again = self.build(4, template=out4)
        self.assertEqual(pcb.copper_layers(again), ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"])
        _, two = self.build(2, template=out4)
        self.assertEqual(pcb.copper_layers(two), ["F.Cu", "B.Cu"])
        # stale copper and nets from the template are dropped, the netlist's nets are present
        self.assertEqual(list(sexpr.children(two, "segment")), [])
        self.assertEqual([n[2] for n in sexpr.children(two, "net")], ["", "GND", "SIG"])

    def fps(self, root):
        return {sexpr.child(fp, "property")[2]: fp for fp in sexpr.children(root, "footprint")}

    def test_attr_flags_with_and_without_attr_clause(self):
        _, root = self.build(2)
        fps = self.fps(root)
        self.assertEqual(sexpr.child(fps["C1"], "attr")[1:], ["smd", "dnp"])
        self.assertEqual(sexpr.child(fps["TP1"], "attr")[1:], ["exclude_from_bom"])

    def test_variants_emitted_board_and_footprint(self):
        _, root = self.build(2)
        self.assertEqual(sexpr.child(root, "variants"), ["variants", ["variant", ["name", "vib"]]])
        # regenerating from the output must not accumulate registries
        _, again = self.build(2, template=os.path.join(self.tmp.name, "out2.kicad_pcb"))
        self.assertEqual(list(sexpr.children(again, "variants")), [["variants", ["variant", ["name", "vib"]]]])
        fps = self.fps(root)
        self.assertEqual(list(sexpr.children(fps["C1"], "variant")), [["variant", ["name", "vib"], ["dnp", "no"]]])
        self.assertEqual(list(sexpr.children(fps["TP1"], "variant")), [])

    def test_solid_pads_and_no_paste(self):
        b = pcbgen.Board(self.template, pcbgen.Netlist(self.netlist), "x.kicad_sch", 10, 10, origin=(0, 0))
        b.footprint("C1", 2, 3, solid_pads=("2",), no_paste=True)
        out = os.path.join(self.tmp.name, "np.kicad_pcb")
        b.write(out)
        pads = {p[1]: p for p in sexpr.children(self.fps(sexpr.parse(open(out).read()))["C1"], "pad")}
        self.assertEqual(sexpr.child(pads["1"], "layers")[1:], ["F.Cu"])          # F.Paste dropped
        self.assertIsNone(sexpr.child(pads["1"], "zone_connect"))
        self.assertEqual(sexpr.child(pads["2"], "zone_connect"), ["zone_connect", "2"])

    def test_pads_rotated_and_netted(self):
        c1, root = self.build(2)
        self.assertEqual(c1, {"1": (2.0, 4.0), "2": (2.0, 2.0)})      # rot 90 (CCW on screen): pad 1 (-1,0) -> below
        pads = {p[1]: sexpr.child(p, "net") for p in sexpr.children(self.fps(root)["C1"], "pad")}
        self.assertEqual(pads, {"1": ["net", "1", "GND"], "2": ["net", "2", "SIG"]})


# Library pins are y-up; `Q` is shaped like Transistor_BJT:Q_NPN_BCE (B left, C up, E down)
# so every rotation/mirror moves each pin somewhere distinct. `Dual` has two units, a
# common (unit 0) supply pin, and a De Morgan body style that moves pin 1.
LIB = """(lib_symbols
  (symbol "T:Q"
    (property "Reference" "Q" (at 5 0 0))
    (symbol "Q_0_1" (polyline (pts (xy 0 0) (xy 1 1))))
    (symbol "Q_1_1"
      (pin input line (at -5.08 0 0) (length 2.54) (name "B") (number "1"))
      (pin passive line (at 2.54 5.08 270) (length 2.54) (name "C") (number "2"))
      (pin passive line (at 2.54 -5.08 90) (length 2.54) (name "E") (number "3"))))
  (symbol "T:Dual"
    (symbol "Dual_0_0" (pin power_in line (at 0 7.62 270) (length 2.54) (name "V") (number "8")))
    (symbol "Dual_1_1" (pin input line (at -7.62 0 0) (length 2.54) (name "A") (number "1")))
    (symbol "Dual_1_2" (pin input line (at -7.62 2.54 0) (length 2.54) (name "A") (number "1")))
    (symbol "Dual_2_1" (pin input line (at -7.62 -2.54 0) (length 2.54) (name "B") (number "2"))))
  (symbol "T:Q2" (extends "Q") (property "Reference" "Q" (at 0 0 0))))"""


def sheet(*items: str) -> sexpr.Node:
    return sexpr.parse("(kicad_sch (version 20250114) " + LIB + " ".join(items) + ")")


def sym(lib_id, ref, x, y, rot=0, mirror=None, unit=1, extra=""):
    m = f"(mirror {mirror})" if mirror else ""
    return (f'(symbol (lib_id "{lib_id}") (at {x} {y} {rot}) {m} (unit {unit}) {extra} '
            f'(property "Reference" "{ref}" (at 1.1 2.2 0)) (property "Value" "v" (at 3.3 4.4 0)))')


def pins(root):
    return {(p.name, p.pin): (round(p.x, 3), round(p.y, 3)) for p in offgrid.points(root) if p.kind == "pin"}


class OffgridTests(unittest.TestCase):
    # Expected positions for a Q at (100, 100); the same transform was checked against
    # kicad-cli ERC (no-connect flags on computed pins, all 12 rot/mirror combinations).
    CASES = {
        (0, None): {"1": (94.92, 100), "2": (102.54, 94.92), "3": (102.54, 105.08)},
        (90, None): {"1": (100, 105.08), "2": (94.92, 97.46), "3": (105.08, 97.46)},
        (180, None): {"1": (105.08, 100), "2": (97.46, 105.08), "3": (97.46, 94.92)},
        (270, None): {"1": (100, 94.92), "2": (105.08, 102.54), "3": (94.92, 102.54)},
        (0, "y"): {"1": (105.08, 100), "2": (97.46, 94.92), "3": (97.46, 105.08)},
        (0, "x"): {"1": (94.92, 100), "2": (102.54, 105.08), "3": (102.54, 94.92)},
        # order-sensitive: KiCad rotates first, then mirrors
        (90, "x"): {"1": (100, 94.92), "2": (94.92, 102.54), "3": (105.08, 102.54)},
        (90, "y"): {"1": (100, 105.08), "2": (105.08, 97.46), "3": (94.92, 97.46)},
    }

    def test_rotation_and_mirror(self):
        for (rot, mirror), want in self.CASES.items():
            with self.subTest(rot=rot, mirror=mirror):
                self.assertEqual(pins(sheet(sym("T:Q", "Q1", 100, 100, rot, mirror))),
                                 {("Q1", n): xy for n, xy in want.items()})
                # moved onto the grid (101.6 = 80 x 1.27), every pin is on it too
                self.assertEqual(offgrid.off_grid(offgrid.points(sheet(sym("T:Q", "Q1", 101.6, 101.6, rot, mirror)))), [])

    def test_schgen_xform_agrees(self):
        # schgen.place() predicts pin positions with xform(); it must match the lint
        for rot, mirror in self.CASES:
            for px, py in ((-5.08, 0), (2.54, 5.08)):
                dx, dy = schgen.xform(px, -py, rot, mirror)
                self.assertEqual((dx, dy), offgrid.transform(px, py, 0, 0, rot, mirror), (rot, mirror))

    def test_extends_uses_parent_pins(self):
        self.assertEqual(pins(sheet(sym("T:Q2", "Q9", 100, 100)))[("Q9", "1")], (94.92, 100))

    def test_multi_unit_and_body_style(self):
        root = sheet(sym("T:Dual", "U1", 50.8, 50.8, unit=2),
                     sym("T:Dual", "U1", 76.2, 50.8, unit=1, extra="(body_style 2)"),
                     sym("T:Dual", "U2", 101.6, 50.8, unit=1, extra="(convert 1)"))
        got = sorted((p.name, p.pin, round(p.x, 3), round(p.y, 3)) for p in offgrid.points(root))
        self.assertEqual(got, [("U1", "1", 68.58, 48.26),      # De Morgan pin 1
                               ("U1", "2", 43.18, 53.34),      # unit 2 only
                               ("U1", "8", 50.8, 43.18),       # common pin on every unit
                               ("U1", "8", 76.2, 43.18),
                               ("U2", "1", 93.98, 50.8),
                               ("U2", "8", 101.6, 43.18)])

    def test_flags_offgrid_items_only(self):
        root = sheet(
            sym("T:Q", "Q1", 101.1, 101.6),                    # all three pins shift off-grid
            sym("T:Q", "Q2", 50.8, 50.8, 90),
            '(wire (pts (xy 50.8 50.8) (xy 60 50.8)))',
            '(bus (pts (xy 0 0) (xy 2.54 0)))',
            '(bus_entry (at 2.54 0) (size 2.54 2.6))',
            '(junction (at 50.8 50.8))',
            '(no_connect (at 12.7 12.8))',
            '(label "SDA" (at 1 2.54 0))',
            '(global_label "SCL" (shape input) (at 2.54 2.54 0))',
            '(hierarchical_label "EN" (shape input) (at 2.54 5.1 0))',
            '(sheet (at 10.16 10.16) (size 20 20) (property "Sheetname" "Power" (at 10 9 0)) '
            '(pin "VIN" input (at 10.16 12.7 180)) (pin "EN" input (at 10.16 13 180)))',
            '(text "not a connection" (at 0.3 0.3 0))',
            '(rectangle (start 0.1 0.1) (end 3 3))',
        )
        bad = [(p.kind, p.name, p.pin) for p in offgrid.off_grid(offgrid.points(root))]
        self.assertEqual(bad, [("pin", "Q1", "1"), ("pin", "Q1", "2"), ("pin", "Q1", "3"),
                               ("wire", "", ""), ("bus_entry", "", ""), ("no_connect", "", ""),
                               ("label", "SDA", ""), ("hierarchical_label", "EN", ""),
                               ("sheet_pin", "Power", "EN")])
        line = offgrid.format_point(offgrid.off_grid(offgrid.points(root))[0])
        self.assertIn("Q1 pin 1", line)
        self.assertIn("at (96.02, 101.6)  nearest (96.52, 101.6)", line)

    def test_tolerance(self):
        root = sheet('(wire (pts (xy 2.54005 0) (xy 2.5402 0)))')
        self.assertEqual([p.x for p in offgrid.off_grid(offgrid.points(root))], [2.5402])

    def test_cli(self):
        d = tempfile.mkdtemp()
        good, bad = os.path.join(d, "good.kicad_sch"), os.path.join(d, "bad.kicad_sch")
        for p, root in ((good, sheet(sym("T:Q", "Q1", 101.6, 101.6))), (bad, sheet(sym("T:Q", "Q1", 101.6, 102)))):
            with open(p, "w") as f:
                f.write(sexpr.dumps(root))
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(offgrid.main(["offgrid", good]), 0)
            self.assertEqual(offgrid.main(["offgrid", bad]), 1)
            self.assertEqual(offgrid.main(["offgrid", bad, "--grid", "0.01"]), 0)
            self.assertEqual(offgrid.main(["offgrid"]), 2)
            self.assertEqual(offgrid.main(["offgrid", bad, "--grid", "x"]), 2)
        self.assertIn("bad.kicad_sch: 3 of 3 connection points off the 1.27 mm grid", out.getvalue())
        with open(good, "w") as f:
            f.write("(kicad_pcb (version 20260206))")
        with self.assertRaises(ValueError):
            offgrid.load(good)

    def test_hierarchy(self):
        d = tempfile.mkdtemp()
        os.mkdir(os.path.join(d, "sub"))

        def write(name, *items):
            with open(os.path.join(d, name), "w") as f:
                f.write(sexpr.dumps(sheet(*items)))

        def ref(name, f):
            return (f'(sheet (at 25.4 25.4) (size 10 10) (property "Sheetname" "{name}" (at 0 0 0)) '
                    f'(property "Sheetfile" "{f}" (at 0 0 0)))')

        # the same child sheet twice (linted once); its path resolves relative to the parent
        write("top.kicad_sch", ref("A", "sub/child.kicad_sch"), ref("B", "sub/child.kicad_sch"))
        write("sub/child.kicad_sch", sym("T:Q", "Q1", 101.6, 101.6), ref("C", "leaf.kicad_sch"))
        write("sub/leaf.kicad_sch", sym("T:Q", "Q2", 101.6, 102))
        top = os.path.join(d, "top.kicad_sch")
        self.assertEqual([os.path.relpath(f, d) for f, _ in offgrid.sheets(top)],
                         ["top.kicad_sch", "sub/child.kicad_sch", "sub/leaf.kicad_sch"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(offgrid.main(["offgrid", top]), 1)
        lines = out.getvalue().splitlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(all("sub/leaf.kicad_sch: pin" in l and "Q2" in l for l in lines[:3]), lines)
        self.assertIn("(+2 sub-sheet files): 3 of 6 connection points off", lines[3])

        write("sub/leaf.kicad_sch", ref("loop", "child.kicad_sch"))           # cycle
        with self.assertRaisesRegex(ValueError, "recursion"):
            offgrid.sheets(top)
        write("sub/leaf.kicad_sch", ref("gone", "missing.kicad_sch"))
        with self.assertRaisesRegex(ValueError, "'gone' file not found"):
            offgrid.sheets(top)


if __name__ == "__main__":
    unittest.main()
