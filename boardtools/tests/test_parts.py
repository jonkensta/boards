import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from boardtools import parts

PARTS = [  # lcsc, mpn, manufacturer, package, library_type, preferred, stock
    ("C25804", "0603WAF1002T5E", "UNI-ROYAL", "0603", "base", False, 5_000_000),
    ("C7420316", "SS14", "MDD", "SMA_DO-214AC", "expand", True, 200_000),
    ("C107671", "PCM5102APWR", "TI", "TSSOP-20", "expand", False, 1000),
    ("C486037", "ISO7720DR", "TI", "SOIC-8", "expand", False, 12),
    ("C144397", "B6B-XH-A(LF)(SN)", "JST", "Plugin,P=2.5mm", "expand", False, 20),
]
HEADER = '"Refs","Value","Description","Footprint","MPN","Manufacturer","LCSC","Qty"\n'


def bom_line(refs: str, lcsc: str, mpn: str = "", fp: str = "Resistor_SMD:R_0603_1608Metric",
             qty: int | str = 1) -> str:
    return f'"{refs}","v","","{fp}","{mpn}","","{lcsc}","{qty}"\n'


def api_item(lcsc, mpn, manufacturer, package, library_type, preferred, stock):
    # the fields parts.py reads, as the live endpoint returns them (plus one it ignores)
    return {"componentCode": lcsc, "componentModelEn": mpn, "componentBrandEn": manufacturer,
            "componentSpecificationEn": package, "componentLibraryType": library_type,
            "preferredComponentFlag": preferred, "stockCount": stock, "lcscGoodsUrl": "https://x"}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeApi:
    """Stands in for urlopen: answers from PARTS, with fuzzy hits for keyword 'C2'."""

    def __init__(self, fail: set[str] | None = None, fail_all: bool = False):
        self.fail, self.fail_all, self.requests = fail or set(), fail_all, []

    def __call__(self, req, timeout):
        body = json.loads(req.data)
        self.requests.append((req, body))
        code = body["keyword"]
        if self.fail_all or code in self.fail:
            raise OSError("connection refused")
        if code == "C2":   # the real endpoint returns C20601999 (MG150HF12TFC2) etc. for C2
            items = [api_item("C20601999", "MG150HF12TFC2", "Yangjie", "C2", "expand", False, 3)]
        else:
            items = [api_item(*p) for p in PARTS if p[0] == code]
        return FakeResponse(json.dumps({"code": 200, "message": None, "data": {
            "componentPageInfo": {"total": len(items), "list": items}}}).encode())


class LiveApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.fake = FakeApi()

    def tearDown(self):
        self.tmp.cleanup()

    def bom(self, *lines: str, header: str = HEADER) -> str:
        p = self.dir / "bom.csv"
        p.write_text(header + "".join(lines), encoding="utf-8")
        return str(p)

    def check(self, *lines: str, boards: int = 5, header: str = HEADER):
        return parts.check_bom(self.bom(*lines, header=header), parts.JlcpcbApi(self.fake), boards)

    def test_request(self):
        self.check(bom_line("R1", "C25804"), bom_line("R2", "C25804"))
        [(req, body)] = self.fake.requests                  # one request per distinct LCSC
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(req.full_url, parts.API_URL)
        self.assertTrue(req.get_header("User-agent").startswith("boardtools-parts/"))
        self.assertEqual(body["keyword"], "C25804")

    def test_basic_ok(self):
        [ln] = self.check(bom_line("R1", "C25804", mpn=" 0603waf1002t5e "))
        assert ln.part is not None
        self.assertEqual((ln.status, ln.part.kind, ln.issues), ("ok", "basic", []))

    def test_extended_and_preferred(self):
        a, b = self.check(bom_line("U1", "C107671", "PCM5102APWR", "Package_SO:TSSOP-20"),
                          bom_line("D1", "C7420316", "SS14", "Diode_SMD:D_SMA"))
        assert a.part is not None and b.part is not None
        self.assertEqual((a.status, a.part.kind), ("ok", "extended"))
        self.assertEqual((b.status, b.part.kind), ("ok", "preferred"))

    def test_missing_lcsc_is_warning(self):
        [ln] = self.check(bom_line("C1", ""))
        self.assertEqual(ln.status, "WARN")
        self.assertIn("no LCSC", ln.issues[0][1])
        self.assertEqual(self.fake.requests, [])

    def test_not_found_fuzzy_and_malformed(self):
        a, b, c = self.check(bom_line("R1", "C999"), bom_line("R2", "C2"), bom_line("R3", "25804"))
        self.assertEqual([x.status for x in (a, b, c)], ["ERROR"] * 3)
        self.assertEqual(a.issues[0][1], "not found at JLCPCB")
        self.assertEqual(b.issues[0][1], "not found at JLCPCB")      # fuzzy hit is not a match
        self.assertIsNone(b.part)
        self.assertIn("malformed", c.issues[0][1])

    def test_stock_summed_per_lcsc(self):
        # ISO7720 has 12 in stock: 2 per board x 5 = 10 fits but is low; split over two
        # lines (as Description grouping does) the total 15 exceeds stock
        [ln] = self.check(bom_line("U1,U2", "C486037", fp="Package_SO:SOIC-8", qty=2))
        self.assertIn("low stock", ln.issues[0][1])
        a, b = self.check(bom_line("U1,U2", "C486037", fp="Package_SO:SOIC-8", qty=2),
                          bom_line("U3", "C486037", fp="Package_SO:SOIC-8"))
        self.assertIn("stock 12 < 15", a.issues[0][1])
        self.assertEqual(b.status, "WARN")
        [ln] = self.check(bom_line("U1", "C486037", fp="Package_SO:SOIC-8"), boards=1)
        self.assertEqual(ln.status, "ok")

    def test_mpn_mismatch(self):
        [ln] = self.check(bom_line("R1", "C25804", mpn="RC0603FR-0710KL"))
        self.assertEqual(ln.status, "WARN")
        self.assertIn("MPN RC0603FR-0710KL but catalog has 0603WAF1002T5E", ln.issues[0][1])

    def test_package_mismatch_only_for_chip_sizes(self):
        [ln] = self.check(bom_line("R1", "C25804", fp="Resistor_SMD:R_0402_1005Metric"))
        self.assertIn("footprint is 0402 but catalog package is 0603", ln.issues[0][1])
        # non-chip catalog packages are not compared
        [ln] = self.check(bom_line("J1", "C144397", fp="Connector_JST:JST_XH_B6B-XH-A_1x06_P2.50mm_Vertical"))
        self.assertEqual(ln.status, "ok")

    def test_header_validation(self):
        with self.assertRaises(ValueError):
            self.check(header='"Refs","Value","Footprint","LCSC"\n')
        self.assertEqual(self.check(), [])            # header-only BOM is valid and empty
        with self.assertRaises(ValueError):
            self.check(bom_line("R1", "C25804", qty="x"))

    def test_nonpositive_qty_rejected(self):
        # 3 + (-3) would sum to 0 and pass a 12-in-stock part for 15 needed
        for bad in (0, -3):
            with self.assertRaisesRegex(ValueError, "Qty must be positive"):
                self.check(bom_line("U1", "C486037", fp="Package_SO:SOIC-8", qty=3),
                           bom_line("U2", "C486037", fp="Package_SO:SOIC-8", qty=bad))

    def test_lookup_failure(self):
        self.fake = FakeApi(fail={"C107671"})
        a, b = self.check(bom_line("R1", "C25804"), bom_line("U1", "C107671", fp="Package_SO:TSSOP-20"))
        self.assertEqual((a.status, b.status), ("ok", "ERROR"))
        self.assertIn("lookup failed", b.issues[0][1])

    def test_unexpected_api_answer(self):
        def opener(req, timeout):
            return FakeResponse(b'{"code": 500, "message": "busy", "data": null}')
        with self.assertRaises(parts.LookupFailed):
            parts.JlcpcbApi(opener).lookup("C25804")
        with self.assertRaises(parts.LookupFailed):
            parts.JlcpcbApi(lambda req, timeout: FakeResponse(b"<html>")).lookup("C25804")

    def test_malformed_api_answer_is_failure_not_absence(self):
        ok = api_item(*PARTS[0])
        answers = [
            {"code": 200, "data": None},
            {"code": 200, "data": []},
            {"code": 200, "data": {"componentPageInfo": None}},
            {"code": 200, "data": {"componentPageInfo": {"list": None}}},
            {"code": 200, "data": {"componentPageInfo": {"list": {"componentCode": "C25804"}}}},
            {"code": 200, "data": {"componentPageInfo": {"list": ["C25804"]}}},
            {"code": 200, "data": {"componentPageInfo": {"list": [{"componentCode": 25804}]}}},
            {"code": 200, "data": {"componentPageInfo": {"list": [dict(ok, stockCount="many")]}}},
            [],
        ]
        for answer in answers:
            api = parts.JlcpcbApi(lambda req, timeout, a=answer: FakeResponse(json.dumps(a).encode()))
            with self.subTest(answer=answer), self.assertRaises(parts.LookupFailed):
                api.lookup("C25804")
        # a well-formed empty list is a genuine miss
        empty = {"code": 200, "data": {"componentPageInfo": {"list": []}}}
        api = parts.JlcpcbApi(lambda req, timeout: FakeResponse(json.dumps(empty).encode()))
        self.assertIsNone(api.lookup("C25804"))
        # every lookup malformed -> no usable source -> exit 2
        null = lambda req, timeout: FakeResponse(b'{"code":200,"data":null}')  # noqa: E731
        self.assertEqual(self.run_main(bom_line("R1", "C25804"), fake=null)[0], 2)

    def run_main(self, *lines: str, extra=(), fake=None):
        with contextlib.redirect_stdout(io.StringIO()) as out, \
             contextlib.redirect_stderr(io.StringIO()):
            rc = parts.main(["parts", self.bom(*lines), *extra], opener=fake or self.fake)
        return rc, out.getvalue()

    def test_main_exit_codes(self):
        rc, out = self.run_main(bom_line("R1", "C25804"), bom_line("U1", "C107671", fp="Package_SO:TSSOP-20"))
        self.assertEqual(rc, 0)
        self.assertIn("1 basic, 0 preferred, 1 extended (1 extended-part loading fees)", out)
        self.assertEqual(self.run_main(bom_line("R1", ""))[0], 0)
        self.assertEqual(self.run_main(bom_line("R1", ""), extra=["--strict"])[0], 1)
        self.assertEqual(self.run_main(bom_line("R1", "C1"))[0], 1)
        # one failed lookup is an error line; all lookups failing means no usable source
        partial = FakeApi(fail={"C107671"})
        self.assertEqual(self.run_main(bom_line("R1", "C25804"), bom_line("U1", "C107671"), fake=partial)[0], 1)
        self.assertEqual(self.run_main(bom_line("R1", "C25804"), bom_line("R2", ""),
                                       fake=FakeApi(fail_all=True))[0], 2)


class SnapshotTests(unittest.TestCase):
    """--db: the offline SQLite path (subset of the jlcparts/CDFER jlc_components schema)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "db.sqlite3"
        conn = sqlite3.connect(self.db)
        conn.execute("""CREATE TABLE jlc_components (lcsc INTEGER PRIMARY KEY NOT NULL,
            mfr TEXT NOT NULL, manufacturer TEXT NOT NULL, package TEXT NOT NULL,
            library_type TEXT NOT NULL, preferred INTEGER NOT NULL, stock INTEGER NOT NULL)""")
        conn.executemany("INSERT INTO jlc_components VALUES (?,?,?,?,?,?,?)",
                         [(int(p[0][1:]), *p[1:]) for p in PARTS])
        conn.commit()
        conn.close()
        self.bom = self.dir / "bom.csv"
        self.bom.write_text(HEADER + bom_line("R1", "C25804") + bom_line("D1", "C7420316", fp="D_SMA")
                            + bom_line("R2", "C999"), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_lookup_and_partial_wording(self):
        catalog = parts.Catalog(self.db)
        a, b, c = parts.check_bom(str(self.bom), catalog)
        catalog.conn.close()
        assert a.part is not None and b.part is not None
        self.assertEqual((a.status, a.part.kind, b.part.kind), ("ok", "basic", "preferred"))
        self.assertIn("snapshot is partial", c.issues[0][1])     # 5-part fixture is partial
        self.assertIn("PARTIAL", catalog.name)
        orig, parts.FULL_CATALOG_MIN = parts.FULL_CATALOG_MIN, 1
        try:
            catalog = parts.Catalog(self.db)
        finally:
            parts.FULL_CATALOG_MIN = orig
        self.assertIn("out of stock", catalog.missing)
        catalog.conn.close()

    def test_main_db(self):
        def run(db):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return parts.main(["parts", str(self.bom), "--db", str(db)], opener=FakeApi(fail_all=True))
        self.assertEqual(run(self.db), 1)                 # C999 missing; the API is never used
        self.assertEqual(run(self.dir / "none"), 2)
        self.assertEqual(run(self.bom), 2)                # not SQLite


if __name__ == "__main__":
    unittest.main()
