import importlib.util
import math
import os
import re
import tempfile
import unittest

from boardtools import sexpr, specctra

# Two-layer 20 x 10 mm board at (50, 50): R1 rotated 90 deg with roundrect pads, a THT
# header pad, an NPTH hole, a keepout, a GND pour, and one existing track and via.
BOARD = '''(kicad_pcb (version 20260206) (generator "pcbnew")
  (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))
  (footprint "Resistor_SMD:R_0603_1608Metric" (layer "F.Cu") (at 60 55 90)
    (property "Reference" "R1" (at 0 0 90) (layer "F.Fab"))
    (pad "1" smd roundrect (at -0.8 0 90) (size 0.8 0.95) (layers "F.Cu" "F.Mask") (roundrect_rratio 0.25) (net "+5V"))
    (pad "2" smd roundrect (at 0.8 0 90) (size 0.8 0.95) (layers "F.Cu" "F.Mask") (roundrect_rratio 0.25) (net "Net-(R1-Pad2)")))
  (footprint "Connector:Pin" (layer "F.Cu") (at 65 55 0)
    (property "Reference" "J1" (at 0 0 0) (layer "F.SilkS"))
    (pad "1" thru_hole rect (at 0 0) (size 1.7 1.7) (drill 1) (layers "*.Cu" "*.Mask") (net "+5V"))
    (pad "2" thru_hole oval (at 2.54 0 90) (size 1.7 2) (drill 1) (layers "*.Cu" "*.Mask") (net "Net-(R1-Pad2)")))
  (footprint "MountingHole:Hole" (layer "F.Cu") (at 52 52)
    (property "Reference" "H1" (at 0 0 0) (layer "F.Fab"))
    (pad "" np_thru_hole circle (at 0 0) (size 2 2) (drill 2) (layers "*.Cu" "*.Mask")))
  (gr_line (start 70 60) (end 50 60) (layer "Edge.Cuts"))
  (gr_line (start 50 50) (end 70 50) (layer "Edge.Cuts"))
  (gr_line (start 50 60) (end 50 50) (layer "Edge.Cuts"))
  (gr_line (start 70 50) (end 70 60) (layer "Edge.Cuts"))
  (segment (start 60 54.2) (end 63 54.2) (width 0.25) (layer "F.Cu") (net "+5V"))
  (via (at 63 54.2) (size 0.6) (drill 0.3) (layers "F.Cu" "B.Cu") (net "+5V"))
  (zone (net "GND") (net_name "GND") (layers "B.Cu") (name "pour")
    (polygon (pts (xy 50 50) (xy 70 50) (xy 70 60) (xy 50 60))))
  (zone (net 0) (net_name "") (layers "F.Cu" "B.Cu") (name "ko")
    (keepout (tracks not_allowed) (vias not_allowed) (pads allowed) (copperpour not_allowed) (footprints allowed))
    (polygon (pts (xy 55 57) (xy 56 57) (xy 56 58))))
)
'''

PROJECT = {
    "board": {"design_settings": {"rules": {"min_copper_edge_clearance": 0.3, "min_hole_clearance": 0.25}}},
    "net_settings": {
        "classes": [
            {"name": "Default", "clearance": 0.2, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
             "priority": 2147483647},
            {"name": "Power", "clearance": 0.2, "track_width": 0.5, "via_diameter": 0.8, "via_drill": 0.4,
             "priority": 0},
        ],
        "netclass_patterns": [{"netclass": "Power", "pattern": "+*"}],
        "netclass_assignments": None,
    },
}


class GeometryTests(unittest.TestCase):
    def test_pad_position_rotation(self):
        # KiCad rotates CCW on screen (y down): local +x at 90 deg points to screen up (-y).
        self.assertEqual(tuple(round(v, 6) for v in specctra.pad_position((10, 20, 90), (1, 0))), (10, 19))
        self.assertEqual(tuple(round(v, 6) for v in specctra.pad_position((10, 20, 90), (0, 1))), (11, 20))
        self.assertEqual(tuple(round(v, 6) for v in specctra.pad_position((10, 20, 180), (1, 2))), (9, 18))
        self.assertEqual(specctra.to_dsn(10, 20), (10, -20))

    def test_rect_and_oval(self):
        self.assertEqual(specctra.pad_shape("rect", 2, 1, 0), ("rect", -1, -0.5, 1, 0.5))
        self.assertEqual(specctra.pad_shape("rect", 2, 1, 270), ("rect", -0.5, -1, 0.5, 1))
        self.assertEqual(specctra.pad_shape("oval", 1, 1, 0), ("circle", 1))
        kind, width, x1, y1, x2, y2 = specctra.pad_shape("oval", 1.7, 2.0, 90)  # long axis y, turned to x
        self.assertEqual((kind, width), ("path", 1.7))
        self.assertAlmostEqual(abs(x2 - x1), 0.3)
        self.assertAlmostEqual(y2 - y1, 0)

    def test_roundrect_contains_true_outline(self):
        w, h, rr = 0.8, 0.95, 0.25
        kind, pts = specctra.pad_shape("roundrect", w, h, 0, rr)
        self.assertEqual((kind, len(pts)), ("polygon", 12))
        self.assertAlmostEqual(max(x for x, _ in pts), w / 2)
        self.assertAlmostEqual(max(y for _, y in pts), h / 2)
        # Every chord lies outside the corner arc (circumscribed), never inside it.
        r = rr * min(w, h)
        cx, cy = w / 2 - r, h / 2 - r
        corner = [p for p in pts if p[0] > cx and p[1] > cy]
        self.assertTrue(all(math.dist(p, (cx, cy)) >= r - 1e-9 for p in corner))
        _, turned = specctra.pad_shape("roundrect", w, h, 45, rr)
        self.assertAlmostEqual(max(math.hypot(x, y) for x, y in turned), max(math.hypot(x, y) for x, y in pts))

    def test_outline_chains_unordered_lines(self):
        loops = specctra.outline_loops(sexpr.parse(BOARD))
        self.assertEqual(len(loops), 1)
        self.assertEqual(len(loops[0]), 5)
        self.assertEqual(loops[0][0], loops[0][-1])

    def test_open_outline_rejected(self):
        with self.assertRaises(ValueError):
            specctra.outline_loops(sexpr.parse('(kicad_pcb (gr_line (start 0 0) (end 1 0) (layer "Edge.Cuts")))'))


class NetNameTests(unittest.TestCase):
    def test_both_formats(self):
        for text, want in [('(pad (net "GND"))', "GND"), ('(pad (net "3"))', "3"), ('(pad (net 3 "GND"))', "GND"),
                           ("(pad (net 0))", None), ("(pad)", None)]:
            self.assertEqual(specctra._net(sexpr.parse(text)), want, text)


class NetclassTests(unittest.TestCase):
    def test_patterns_assignments_default(self):
        proj = {"net_settings": dict(PROJECT["net_settings"], netclass_assignments={"GND": ["Power"]})}
        classes, of = specctra.netclasses(proj, ["+5V", "GND", "SIG"])
        self.assertEqual(of, {"+5V": "Power", "GND": "Power", "SIG": "Default"})
        self.assertEqual(classes["Power"]["track_width"], 0.5)

    def test_combined_classes_resolve_per_rule(self):
        proj = {"net_settings": {
            "classes": [
                {"name": "Default", "clearance": 0.2, "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3,
                 "priority": 2147483647},
                {"name": "Wide", "track_width": 0.5, "clearance": None, "priority": 1},
                {"name": "Safe", "track_width": 0.3, "clearance": 0.3, "via_diameter": 0.8, "via_drill": 0.4,
                 "priority": 2},
            ],
            "netclass_patterns": [{"netclass": "Safe", "pattern": "HV*"}],
            "netclass_assignments": {"HV1": ["Wide"]}}}
        classes, of = specctra.netclasses(proj, ["HV1", "HV2", "LV"])
        self.assertEqual(of, {"HV1": "Wide,Safe", "HV2": "Safe", "LV": "Default"})
        self.assertEqual(classes["Wide,Safe"], dict(track_width=0.5, clearance=0.3, via_diameter=0.8, via_drill=0.4))
        self.assertEqual(classes["Safe"]["track_width"], 0.3)

    def test_empty_project(self):
        classes, of = specctra.netclasses({}, ["A"])
        self.assertEqual(of, {"A": "Default"})
        self.assertEqual(classes["Default"]["clearance"], 0.2)


class DsnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, cls.nets = specctra.dsn(sexpr.parse(BOARD), PROJECT, "t")

    def test_header_units_layers_boundary(self):
        t = self.text
        self.assertIn("(resolution um 10)", t)
        self.assertIn("(unit um)", t)
        self.assertIn('(layer "F.Cu" (type signal) (property (index 0)))', t)
        self.assertIn('(layer "B.Cu" (type signal) (property (index 1)))', t)
        self.assertIn("(boundary (path pcb 0 70000 -60000 50000 -60000 50000 -50000 70000 -50000 70000 -60000))", t)

    def test_rotated_footprint_pins(self):
        # R1 at (60, 55) rot 90: pad 1 (-0.8, 0) lands at (60, 55.8) -> DSN offset (0, -800).
        self.assertIn('(component "R1__img" (place "R1" 60000 -55000 front 0))', self.text)
        self.assertRegex(self.text, r'\(pin "Pad_\d+_roundrect_S" "1" 0 -800\)')
        self.assertRegex(self.text, r'\(pin "Pad_\d+_roundrect_S" "2" 0 800\)')

    def test_tht_padstacks_on_every_layer(self):
        m = re.search(r'\(padstack "(Pad_\d+_rect_T)" (.*) \(attach off\)\)', self.text)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), '(shape (rect "F.Cu" -850 -850 850 850)) (shape (rect "B.Cu" -850 -850 850 850))')
        # oval 1.7 x 2 at 90 deg: round-ended path along x, width 1.7 mm
        self.assertIn('(shape (path "F.Cu" 1700 150 0 -150 0))', self.text)

    def test_nets_and_classes(self):
        t = self.text
        self.assertIn('(net "+5V" (pins "R1"-"1" "J1"-"1"))', t)
        self.assertIn('(net "Net-(R1-Pad2)" (pins "R1"-"2" "J1"-"2"))', t)
        self.assertIn('(class "Power" "+5V" (circuit (use_via "Via[0-1]_800:400_um")) (rule (width 500) (clearance 200)))', t)
        self.assertIn('(class "Default" "Net-(R1-Pad2)" (circuit (use_via "Via[0-1]_600:300_um"))', t)
        self.assertIn('(padstack "Via[0-1]_800:400_um" (shape (circle "F.Cu" 800)) (shape (circle "B.Cu" 800)) (attach off))', t)

    def test_keepouts_planes_holes_edge(self):
        t = self.text
        self.assertIn('(keepout "" (polygon "B.Cu" 0 55000 -57000 56000 -57000 56000 -58000))', t)
        self.assertIn('(plane "GND" (polygon "B.Cu" 0 50000 -50000 70000 -50000 70000 -60000 50000 -60000))', t)
        self.assertIn('(keepout "" (circle "F.Cu" 2100 52000 -52000))', t)  # 2 mm hole + 2 x (0.25 - 0.2)
        self.assertIn('(keepout "" (path "F.Cu" 200 70000 -60000 50000 -60000))', t)  # 2 x (0.3 - 0.2)
        self.assertNotIn('"H1', t)  # a pinless footprint is only its hole keepout

    def test_existing_wiring_protected(self):
        self.assertIn('(wire (path "F.Cu" 250 60000 -54200 63000 -54200) (net "+5V") (type protect))', self.text)
        self.assertIn('(via "Via[0-1]_600:300_um" 63000 -54200 (net "+5V") (type protect))', self.text)


# Footprints as KiCad 10.0.6 saved them (flipped/rotated in pcbnew, pads trimmed to what
# matters). C1 pad 1 has absolute angle 0 in a 90 deg footprint, so KiCad omits the angle.
# Oracle pad centres from KiCad: C1.1 (68.5, 64.095); R1.1 (80.2855, 65.7775) on B.Cu at
# 30 deg; U1.1 (74.905, 68.475) on B.Cu. The slot is KiCad's: pad centre (60.866025, 69.5),
# hole segment (60.433012, 69.75)-(61.299038, 69.25), width 1. The footprint keepout is the
# ESP32-C3-WROOM-02 antenna keepout of a module placed at (120, 70, 90): board coordinates.
SAVED = '''(kicad_pcb (version 20260206)
  (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))
  (gr_rect (start 50 50) (end 130 90) (layer "Edge.Cuts"))
  (footprint "Capacitor_SMD:C_0603_1608Metric" (layer "F.Cu") (at 68.5 63.32 90) (property "Reference" "C1")
    (pad "1" smd roundrect (at -0.775 0) (size 0.9 0.95) (layers "F.Cu" "F.Mask" "F.Paste") (roundrect_rratio 0.25) (net "+3V3"))
    (pad "2" smd roundrect (at 0.775 0 90) (size 0.9 0.95) (layers "F.Cu" "F.Mask" "F.Paste") (roundrect_rratio 0.25) (net "GND")))
  (footprint "Resistor_SMD:R_0603_1608Metric" (layer "B.Cu") (at 81 65.365 30) (property "Reference" "R1")
    (pad "1" smd roundrect (at -0.825 0 30) (size 0.8 0.95) (layers "B.Cu" "B.Mask" "B.Paste") (roundrect_rratio 0.25) (net "Net-(U1-OUTA)"))
    (pad "2" smd roundrect (at 0.825 0 30) (size 0.8 0.95) (layers "B.Cu" "B.Mask" "B.Paste") (roundrect_rratio 0.25) (net "Net-(J2-Pin_2)")))
  (footprint "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm" (layer "B.Cu") (at 73 66 90) (property "Reference" "U1")
    (pad "1" smd roundrect (at -2.475 1.905 90) (size 1.95 0.6) (layers "B.Cu" "B.Mask" "B.Paste") (roundrect_rratio 0.25) (net "+3V3")))
  (footprint "Slot" (layer "F.Cu") (at 60 70 30) (property "Reference" "H9")
    (pad "" np_thru_hole oval (at 1 0 120) (size 1 2) (drill oval 1 2) (layers "*.Cu" "*.Mask")))
  (footprint "RF_Module:ESP32-C3-WROOM-02" (layer "F.Cu") (at 120 70 90) (property "Reference" "U9")
    (zone (layers "F.Cu" "B.Cu")
      (keepout (tracks not_allowed) (vias not_allowed) (pads not_allowed) (copperpour not_allowed) (footprints not_allowed))
      (polygon (pts (xy 112.9 84) (xy 112.9 56) (xy 101.9 56) (xy 101.9 84)))))
  (zone (net "GND") (net_name "GND") (layers "B.Cu") (name "GND_A")
    (polygon (pts (xy 50 50) (xy 71.5 50) (xy 71.5 80) (xy 50 80)))
    (polygon (pts (xy 55 65) (xy 60 65) (xy 60 70) (xy 55 70))))
)
'''


def _pins(text: str, ref: str) -> dict[str, tuple[float, float]]:
    """Absolute DSN pin centres (um) of one component, from its place and image."""
    place = re.search(rf'\(place "{ref}" (\S+) (\S+) front 0\)', text)
    image = re.search(rf'\(image "{ref}__img"\n(.*?)\n    \)', text, re.S)
    fx, fy = float(place.group(1)), float(place.group(2))
    return {m[1]: (fx + float(m[2]), fy + float(m[3]))
            for m in re.findall(r'\(pin "([^"]+)" "([^"]+)" (\S+) (\S+)\)', image.group(1))}


class KiCadSavedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, _ = specctra.dsn(sexpr.parse(SAVED), {"board": {"design_settings": {"rules": {}}}}, "s")

    def padstack(self, ref, pin):
        image = re.search(rf'\(image "{ref}__img"\n(.*?)\n    \)', self.text, re.S).group(1)
        ps = re.search(rf'\(pin "([^"]+)" "{pin}" ', image).group(1)
        return re.search(rf'\(padstack "{re.escape(ps)}" (.*) \(attach off\)\)', self.text).group(1)

    def test_positions_match_kicad(self):
        for ref, pin, want in [("C1", "1", (68.5, 64.095)), ("R1", "1", (80.2855, 65.7775)), ("U1", "1", (74.905, 68.475))]:
            x, y = _pins(self.text, ref)[pin]
            self.assertAlmostEqual(x / 1000, want[0], places=3, msg=ref)
            self.assertAlmostEqual(-y / 1000, want[1], places=3, msg=ref)

    def test_omitted_pad_angle_is_absolute_zero(self):
        xs = lambda body: [float(v) for v in re.findall(r"-?[\d.]+", body.split(" 0 ", 1)[1])[0::2]]
        self.assertAlmostEqual(max(xs(self.padstack("C1", "1"))), 450, delta=0.1)   # 0.9 wide, not turned
        self.assertAlmostEqual(max(xs(self.padstack("C1", "2"))), 475, delta=0.1)   # 90 deg: 0.95 across x

    def test_bottom_side_pads_on_back_copper(self):
        self.assertIn('"B.Cu"', self.padstack("R1", "1"))
        self.assertNotIn('"F.Cu"', self.padstack("R1", "1"))
        self.assertIn('"B.Cu"', self.padstack("U1", "1"))

    def test_slot_keepout_matches_kicad_hole(self):
        # no hole-clearance growth here (empty rules): width 1, KiCad's own segment
        self.assertIn('(keepout "" (path "F.Cu" 1000 61299 -69250 60433 -69750))', self.text)

    def test_hole_and_slot_clearance_growth(self):
        # KiCad 10 DRC (checked): round NPTH -> min_hole_clearance only; slot wall -> also
        # copper edge clearance. Freerouting already keeps `clearance` (0.2).
        rules = {"board": {"design_settings": {"rules": {"min_hole_clearance": 0.25, "min_copper_edge_clearance": 0.3}}}}
        text, _ = specctra.dsn(sexpr.parse(SAVED), rules, "s")
        self.assertIn('(keepout "" (path "F.Cu" 1200 61299 -69250 60433 -69750))', text)  # stroke 1 + 2 x 0.1
        text, _ = specctra.dsn(sexpr.parse(BOARD), rules, "t")
        self.assertIn('(keepout "" (circle "F.Cu" 2100 52000 -52000))', text)  # 2 + 2 x 0.05

    def test_footprint_keepout_in_board_coordinates(self):
        self.assertIn('(keepout "" (polygon "B.Cu" 0 112900 -84000 112900 -56000 101900 -56000 101900 -84000))', self.text)

    def test_zone_hole_becomes_window(self):
        self.assertIn('(plane "GND" (polygon "B.Cu" 0 50000 -50000 71500 -50000 71500 -80000 50000 -80000)'
                      ' (window (polygon "B.Cu" 0 55000 -65000 60000 -65000 60000 -70000 55000 -70000)))', self.text)

    def test_keepout_hole_becomes_window(self):
        board = SAVED.replace('(polygon (pts (xy 112.9 84) (xy 112.9 56) (xy 101.9 56) (xy 101.9 84)))',
                              '(polygon (pts (xy 112.9 84) (xy 112.9 56) (xy 101.9 56) (xy 101.9 84)))'
                              ' (polygon (pts (xy 105 60) (xy 106 60) (xy 106 61)))')
        text, _ = specctra.dsn(sexpr.parse(board), {}, "s")
        self.assertIn(' (window (polygon "F.Cu" 0 105000 -60000 106000 -60000 106000 -61000)))', text)


# KiCad-saved (pcbnew oracle) custom and trapezoid pads, with KiCad's own effective-polygon
# bounding boxes on F.Cu: BT1.1 [84.508, 105.5468, 88.918, 109.9919] (custom pad whose
# primitive is far larger than its 1 x 1 anchor, turned 30 deg), D9.1 [148.85, 101.1,
# 151.15, 104.7] (trapezoid, 90 deg).
ENVELOPES = '''(kicad_pcb (version 20260206)
  (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))
  (gr_rect (start 50 50) (end 200 150) (layer "Edge.Cuts"))
  (footprint "Battery:BatteryHolder_Keystone_1057_1x2032" (layer "F.Cu") (at 100 100 30) (property "Reference" "BT1")
    (pad "1" smd custom (at -15.15 -0.1 30) (size 1 1) (layers "F.Cu" "F.Mask" "F.Paste") (options (clearance outline) (anchor rect))
      (primitives (gr_poly (pts (xy 0.2 -1.65) (xy 0.271537 -1.594563) (xy 0.343074 -1.539127) (xy 0.500662 -1.450081)
        (xy 0.58506 -1.417404) (xy 0.669458 -1.384728) (xy 0.757691 -1.364583) (xy 0.845923 -1.344438) (xy 1.026357 -1.330056)
        (xy 1.235196 -1.330056) (xy 1.444035 -1.330057) (xy 1.444034 1.539942) (xy 1.044035 1.539967) (xy 0.86174 1.553331)
        (xy 0.683343 1.593137) (xy 0.512659 1.658535) (xy 0.353336 1.748125) (xy 0.28106 1.804058) (xy 0.208783 1.859992)
        (xy -1.65 1.859992) (xy -1.65 -1.650007)) (width 0.12) (fill yes))) (net "A")))
  (footprint "Diode_SMD:D_SMA-SMB_Universal_Handsoldering" (layer "F.Cu") (at 150 100 90) (property "Reference" "D9")
    (pad "1" smd trapezoid (at -2.9 0 90) (size 3.6 1.7) (rect_delta 0.6 0) (layers "F.Cu" "F.Mask" "F.Paste") (net "A")))
)
'''


class EnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text, _ = specctra.dsn(sexpr.parse(ENVELOPES), {}, "e")

    def bbox(self, ref):
        """Axis-aligned KiCad-frame bbox (mm) of a component's pin 1 copper as exported."""
        cx, cy = _pins(self.text, ref)["1"]
        image = re.search(rf'\(image "{ref}__img"\n(.*?)\n    \)', self.text, re.S).group(1)
        ps = re.search(r'\(pin "([^"]+)" "1" ', image).group(1)
        body = re.search(rf'\(padstack "{re.escape(ps)}" \(shape \(polygon "F.Cu" 0 ([^)]*)\)', self.text).group(1)
        v = [float(t) for t in body.split()]
        xs, ys = [(cx + x) / 1000 for x in v[0::2]], [-(cy + y) / 1000 for y in v[1::2]]
        return min(xs), min(ys), max(xs), max(ys)

    def test_trapezoid_matches_kicad(self):
        for got, want in zip(self.bbox("D9"), (148.85, 101.1, 151.15, 104.7)):
            self.assertAlmostEqual(got, want, places=3)

    def test_custom_pad_contains_kicad_copper(self):
        x1, y1, x2, y2 = self.bbox("BT1")
        kx1, ky1, kx2, ky2 = 84.508, 105.5468, 88.918, 109.9919
        self.assertTrue(x1 <= kx1 and y1 <= ky1 and x2 >= kx2 and y2 >= ky2, (x1, y1, x2, y2))
        self.assertLess((x2 - x1) * (y2 - y1), 1.5 * (kx2 - kx1) * (ky2 - ky1))  # not wildly loose

    def test_custom_primitives_beyond_anchor(self):
        # the review's case: 0.5 mm anchor, a 2 x 8 mm rectangle primitive, stroke 0.1
        pad = sexpr.parse('(pad "1" smd custom (at 0 0) (size 0.5 0.5) (layers "F.Cu") (options (anchor rect))'
                          ' (primitives (gr_rect (start -1 -4) (end 1 4) (width 0.1) (fill yes))'
                          ' (gr_circle (center 0 5) (end 0.5 5) (width 0))'
                          ' (gr_arc (start 3 0) (mid 4 -1) (end 5 0) (width 0.2))))')
        x1, y1, x2, y2 = specctra.pad_envelope(pad, 0.5, 0.5)
        self.assertAlmostEqual(x1, -1.05)
        self.assertAlmostEqual(y1, -4.05)
        self.assertAlmostEqual(y2, 5.5)
        self.assertGreaterEqual(x2, 5.1)
        self.assertLessEqual(y1, -4.05)


# A custom pad whose polygon edge is an arc bulging past its start/mid/end points, as KiCad
# 10.0.6 saved it (the same (arc ...) form as the stock GaNPX-4 pads), with KiCad's
# effective-polygon bboxes: X1 [98.995, 98.995, 102.0055, 101.005] (the true arc reaches
# x = 102; start/mid/end stop at 101.707), X2 (30 deg) [108.6291, 98.4949, 111.8714, 101.3709].
ARC_PAD = '''(kicad_pcb (version 20260206)
  (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user))
  (gr_rect (start 90 90) (end 120 110) (layer "Edge.Cuts"))
  (footprint "Arc" (layer "F.Cu") (at 100 100) (property "Reference" "X1")
    (pad "1" smd custom (at 0 0) (size 0.5 0.5) (layers "F.Cu" "F.Mask") (options (clearance outline) (anchor rect))
      (primitives (gr_poly (pts (xy -1 -1) (arc (start 1 -1) (mid 1.707107 0.707107) (end 1 1)) (xy -1 1)) (width 0) (fill yes)))
      (net "A")))
  (footprint "Arc" (layer "F.Cu") (at 110 100 30) (property "Reference" "X2")
    (pad "1" smd custom (at 0 0 30) (size 0.5 0.5) (layers "F.Cu" "F.Mask") (options (clearance outline) (anchor rect))
      (primitives (gr_poly (pts (xy -1 -1) (arc (start 1 -1) (mid 1.707107 0.707107) (end 1 1)) (xy -1 1)) (width 0) (fill yes)))
      (net "A")))
)
'''


class ArcExtentTests(unittest.TestCase):
    def test_extremes_between_points(self):
        # quarter-circle steps both ways and an arc through 180 deg (the atan2 seam)
        box = lambda pts: tuple(round(v, 6) for v in (min(p[0] for p in pts), min(p[1] for p in pts),
                                                      max(p[0] for p in pts), max(p[1] for p in pts)))
        s2 = round(math.sqrt(0.5), 6)
        self.assertEqual(box(specctra.arc_extent((1, -1), (1 + s2, s2), (1, 1))), (1, -1, 2, 1))
        self.assertEqual(box(specctra.arc_extent((1, 1), (1 + s2, s2), (1, -1))), (1, -1, 2, 1))
        self.assertEqual(box(specctra.arc_extent((-s2, s2), (-1, 0), (-s2, -s2))), (-1, -s2, -s2, s2))
        self.assertEqual(box(specctra.arc_extent((0, 1), (-1, 0), (0, -1))), (-1, -1, 0, 1))
        self.assertEqual(specctra.arc_extent((0, 0), (1, 1), (2, 2)), [(0, 0), (2, 2)])  # collinear

    def test_kicad_saved_arc_pad(self):
        text, _ = specctra.dsn(sexpr.parse(ARC_PAD), {}, "a")
        env = EnvelopeTests.bbox.__get__(type("T", (), {"text": text})())
        for got, kicad in zip(env("X1"), (98.995, 98.995, 102.0055, 101.005)):
            self.assertAlmostEqual(got, kicad, delta=0.006)  # KiCad's arc polygon errs outside by ~5 um
        x1, y1, x2, y2 = env("X2")
        kx1, ky1, kx2, ky2 = 108.6291, 98.4949, 111.8714, 101.3709
        self.assertTrue(x1 <= kx1 + 0.006 and y1 <= ky1 + 0.006 and x2 >= kx2 - 0.006 and y2 >= ky2 - 0.006)


class NamesTests(unittest.TestCase):
    def test_quotes_and_collisions_round_trip(self):
        board = BOARD.replace('"Net-(R1-Pad2)"', '"N \\"a\\" space"').replace('"+5V"', '"N \'a\' space"')
        root = sexpr.parse(board)
        self.assertEqual({specctra._net(p) for fp in sexpr.children(root, "footprint") for p in sexpr.children(fp, "pad")}
                         - {None}, {'N "a" space', "N 'a' space"})
        text, nets = specctra.dsn(root, {}, "t")
        self.assertEqual(sorted(nets.values()), sorted(['N "a" space', "N 'a' space", "GND"]))
        for ident in nets:
            self.assertNotIn('"', ident)
            self.assertIn(f'"{ident}"', text)
        quoted = next(i for i, n in nets.items() if n == 'N "a" space')
        ses = SES.replace('"Net-(R1-Pad2)"', f'"{quoted}"').replace("(net +5V", "(net \"N 'a' space\"")
        wires, _ = specctra.read_ses(ses, nets)
        self.assertEqual([w["net"] for w in wires], ['N "a" space', "N 'a' space"])
        with self.assertRaises(ValueError):
            specctra.read_ses(SES, nets)  # Net-(R1-Pad2) is not in this DSN

    def test_unsafe_refs_and_pins(self):
        board = BOARD.replace('"Reference" "R1"', '"Reference" "R\\"1"').replace('(pad "2" smd', '(pad "2\\"" smd')
        text, _ = specctra.dsn(sexpr.parse(board), {}, "t")
        self.assertNotIn('\\"', text)
        self.assertEqual(len(re.findall(r'\(place "~ref\d+"', text)), 1)
        self.assertRegex(text, r'\(pins "~ref\d+"-"~pin\d+" "J1"-"2"\)')

    def test_names_unique(self):
        n = specctra.Names("net")
        ids = [n(x) for x in ["~net0", 'a"', "~net1", "b\\", "a\"", "Ω"]]
        self.assertEqual(ids[1], ids[4])
        self.assertEqual(len(set(ids)), 5)
        self.assertEqual({n.to_kicad[i] for i in ids}, {"~net0", 'a"', "~net1", "b\\", "Ω"})


SES = '''(session t
  (base_design t)
  (routes
    (resolution um 10)
    (parser (host_cad "KiCad's Pcbnew"))
    (library_out (padstack "Via[0-1]_600:300_um" (shape (circle F.Cu 6000 0 0)) (attach off)))
    (network_out
      (net "Net-(R1-Pad2)"
        (wire (path F.Cu 2000 600000 -558000 612500 -558000 625400 -550000))
        (via "Via[0-1]_600:300_um" 625400 -550000))
      (net +5V
        (wire (path B.Cu 2500 600000 -542000 630000 -542000) (type protect))))))
'''


class SesTests(unittest.TestCase):
    def test_units_yflip_nets(self):
        wires, vias = specctra.read_ses(SES)
        self.assertEqual(len(wires), 2)
        w = wires[0]
        self.assertEqual((w["net"], w["layer"], w["protected"]), ("Net-(R1-Pad2)", "F.Cu", False))
        self.assertAlmostEqual(w["width"], 0.2)
        self.assertEqual([(round(x, 4), round(y, 4)) for x, y in w["points"]], [(60, 55.8), (61.25, 55.8), (62.54, 55)])
        self.assertTrue(wires[1]["protected"])
        self.assertEqual(wires[1]["net"], "+5V")
        v = vias[0]
        self.assertEqual((v["padstack"], round(v["x"], 4), round(v["y"], 4)), ("Via[0-1]_600:300_um", 62.54, 55))
        self.assertEqual(specctra.parse_via_name(v["padstack"]), (0.6, 0.3))

    def test_other_resolution(self):
        wires, _ = specctra.read_ses(SES.replace("(resolution um 10)", "(resolution mil 1)")
                                     .replace("600000 -558000 612500 -558000 625400 -550000", "1000 -2000"))
        self.assertAlmostEqual(wires[0]["points"][0][0], 25.4)
        self.assertAlmostEqual(wires[0]["points"][0][1], 50.8)

    def test_not_a_session(self):
        with self.assertRaises(ValueError):
            specctra.read_ses("(session t (base_design t))")


class AddRoutesTests(unittest.TestCase):
    """scripts/route.py's writer: new wires become segments, protected ones are skipped."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "route.py")
        spec = importlib.util.spec_from_file_location("route", path)
        cls.route = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.route)

    def test_by_name(self):
        root = sexpr.parse(BOARD)
        wires, vias = specctra.read_ses(SES)
        self.assertEqual(self.route.add_routes(root, wires, vias, ["F.Cu", "B.Cu"]), (2, 1))
        segs = list(sexpr.children(root, "segment"))
        self.assertEqual(len(segs), 3)
        self.assertEqual(segs[1][1:5], [["start", "60", "55.8"], ["end", "61.25", "55.8"], ["width", "0.2"], ["layer", "F.Cu"]])
        self.assertEqual(sexpr.child(segs[1], "net"), ["net", "Net-(R1-Pad2)"])
        via = list(sexpr.children(root, "via"))[1]
        self.assertEqual(via[1:4], [["at", "62.54", "55"], ["size", "0.6"], ["drill", "0.3"]])
        self.assertEqual(sexpr.child(via, "layers"), ["layers", "F.Cu", "B.Cu"])
        # tracks go before the zones, as KiCad writes them
        heads = [el[0] for el in root if isinstance(el, list)]
        self.assertLess(max(i for i, h in enumerate(heads) if h in ("segment", "via")), heads.index("zone"))

    @staticmethod
    def _board(root, *parts):
        """A board file (plus project) at root/parts.../<leaf>.kicad_pcb; returns its path."""
        d = os.path.join(root, *parts)
        os.makedirs(d, exist_ok=True)
        board = os.path.join(d, f"{parts[-1]}.kicad_pcb")
        for ext in ("kicad_pcb", "kicad_pro"):
            with open(os.path.join(d, f"{parts[-1]}.{ext}"), "w") as f:
                f.write("keep")
        return board

    def test_default_recreated_without_planted_links(self):
        # round 2: out/route/drc.rpt symlinked (or hard-linked) to the source board
        with tempfile.TemporaryDirectory() as tmp:
            board = self._board(tmp, "b")
            route = os.path.join(os.path.dirname(board), "out", "route")
            os.makedirs(route)
            os.symlink(board, os.path.join(route, "drc.rpt"))
            os.link(board, os.path.join(route, "b.kicad_pcb"))
            out = self.route.prepare_outdir(board, None)
            self.assertEqual(out, os.path.join(os.path.realpath(os.path.dirname(board)), "out", "route"))
            self.assertEqual(os.listdir(out), [])
            with open(os.path.join(out, "drc.rpt"), "w") as f:  # what kicad-cli does next
                f.write("report")
            with open(board) as f:
                self.assertEqual(f.read(), "keep")

    def test_default_refuses_symlinked_out_or_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = self._board(tmp, "b")
            src = os.path.dirname(board)
            os.symlink(src, os.path.join(src, "out"))  # out -> the board's own directory
            with self.assertRaises(ValueError):
                self.route.prepare_outdir(board, None)
            self.assertTrue(os.path.exists(board))
            os.remove(os.path.join(src, "out"))
            os.makedirs(os.path.join(tmp, "elsewhere"))
            os.makedirs(os.path.join(src, "out"))
            os.symlink(os.path.join(tmp, "elsewhere"), os.path.join(src, "out", "route"))
            with self.assertRaises(ValueError):
                self.route.prepare_outdir(board, None)

    def test_custom_ancestor_of_board_refused(self):
        # round 3: an old archive/ output dir holding the board being routed
        with tempfile.TemporaryDirectory() as tmp:
            board = self._board(tmp, "archive", "edited")
            open(os.path.join(tmp, "archive", ".route-output"), "w").close()
            for bad in (os.path.join(tmp, "archive"), os.path.dirname(board), tmp):
                with self.assertRaises(ValueError, msg=bad):
                    self.route.prepare_outdir(board, bad)
            for ext in ("kicad_pcb", "kicad_pro"):
                self.assertTrue(os.path.exists(os.path.join(os.path.dirname(board), f"edited.{ext}")))

    def test_custom_non_empty_refused_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = self._board(tmp, "b")
            other = os.path.join(tmp, "other")
            os.makedirs(other)
            with open(os.path.join(other, "precious"), "w") as f:
                f.write("x")
            with self.assertRaises(ValueError):
                self.route.prepare_outdir(board, other)
            self.assertEqual(os.listdir(other), ["precious"])

    def test_custom_inside_source_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            board = self._board(tmp, "b")
            src = os.path.dirname(board)
            os.symlink(src, os.path.join(tmp, "link"))
            os.makedirs(os.path.join(tmp, "empty"))
            os.symlink(os.path.join(tmp, "empty"), os.path.join(tmp, "emptylink"))
            for bad in (os.path.join(src, "sub"), os.path.join(tmp, "link", "sub"),
                        os.path.join(src, "out", "..", "x"), os.path.join(tmp, "emptylink")):
                with self.assertRaises(ValueError, msg=bad):
                    self.route.prepare_outdir(board, bad)
            # allowed: new dirs outside the source, an empty real dir, a new dir under out/
            self.assertTrue(os.path.isdir(self.route.prepare_outdir(board, os.path.join(tmp, "new", "x"))))
            self.assertTrue(os.path.isdir(self.route.prepare_outdir(board, os.path.join(tmp, "empty"))))
            self.assertTrue(os.path.isdir(self.route.prepare_outdir(board, os.path.join(src, "out", "mine"))))

    def test_by_code(self):
        root = sexpr.parse('(kicad_pcb (net 0 "") (net 7 "Net-(R1-Pad2)") (net 8 "+5V"))')
        wires, vias = specctra.read_ses(SES)
        self.route.add_routes(root, wires, vias, ["F.Cu", "B.Cu"])
        self.assertEqual(sexpr.child(sexpr.child(root, "segment"), "net"), ["net", "7"])


if __name__ == "__main__":
    unittest.main()
