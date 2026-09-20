import os
import tempfile
import unittest

from boardtools import jlcpcb, pcb, pcbgen, sexpr

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
  (pad "1" smd rect (at -1 0) (size 0.5 0.5) (layers "F.Cu"))
  (pad "2" smd rect (at 1 0) (size 0.5 0.5) (layers "F.Cu")))
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
        fps = self.fps(root)
        self.assertEqual(list(sexpr.children(fps["C1"], "variant")), [["variant", ["name", "vib"], ["dnp", "no"]]])
        self.assertEqual(list(sexpr.children(fps["TP1"], "variant")), [])

    def test_pads_rotated_and_netted(self):
        c1, root = self.build(2)
        self.assertEqual(c1, {"1": (2.0, 4.0), "2": (2.0, 2.0)})      # rot 90 (CCW on screen): pad 1 (-1,0) -> below
        pads = {p[1]: sexpr.child(p, "net") for p in sexpr.children(self.fps(root)["C1"], "pad")}
        self.assertEqual(pads, {"1": ["net", "1", "GND"], "2": ["net", "2", "SIG"]})


if __name__ == "__main__":
    unittest.main()
