import os
import tempfile
import unittest

from boardtools import jlcpcb, pcb, sexpr

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
        src = self.path("bom.csv", '"Refs","Value","Footprint","MPN","Manufacturer","LCSC","Qty"\n'
                                   '"R1,R2","10k","R_0603","RC0603FR-0710KL","Yageo","C98220","2"\n'
                                   '"C1","100n","C_0603","","","","1"\n')
        dst = self.path("jlc-bom.csv")
        self.assertEqual(jlcpcb.convert_bom(src, dst), ["C1"])
        with open(dst) as f:
            self.assertEqual(f.read().splitlines()[1], '10k,"R1,R2",R_0603,C98220')
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


if __name__ == "__main__":
    unittest.main()
