"""Check a KiCad BOM's LCSC part numbers against JLCPCB's parts catalog.

Default source: the search endpoint behind jlcpcb.com/parts (API_URL). It is
undocumented and unofficial, so it may change without notice; this is a manual
pre-order check, never CI. One POST per distinct LCSC number, at most WORKERS at a
time. The search is fuzzy (C2040 also returns EPC2040, MIC2040, ...), so a part
counts as found only when a result's componentCode equals the requested number.
Fields used from data.componentPageInfo.list[]:
    componentCode, componentModelEn (MPN), componentBrandEn, componentSpecificationEn
    (package: bare "0603" for chips), componentLibraryType ("base" = basic, "expand"
    = extended), preferredComponentFlag, stockCount

Offline alternative, --db PATH: a jlcparts-style SQLite file (e.g. CDFER's
jlcpcb-components.sqlite3), table jlc_components with lcsc INTEGER (C25804 -> 25804),
mfr (MPN), manufacturer, package, library_type (base/expand), preferred, stock.
Such snapshots drop parts with stock < 5 and may be partial (fewer than
FULL_CATALOG_MIN parts), so a miss there is only "not in snapshot".

Input is the BOM CSV from jobsets/fab.kicad_jobset (see jlcpcb.py). Per line:
    ERROR    malformed LCSC number, part not found, lookup failed (network/HTTP)
    WARNING  no LCSC number (no field marks lines as hand-assembled, so an empty LCSC
             may be deliberate: picked in JLCPCB's BOM tool or soldered by hand),
             stock below or near Qty x --boards (summed per LCSC number), MPN differs
             from the catalog, chip size (0402/0603/...) differs from the catalog package
Extended parts (not basic, not preferred) each cost JLCPCB's per-part loading fee;
the summary counts distinct ones.
Exit status: 0 clean, 1 on any ERROR (with --strict also on any WARNING),
2 on usage errors, an unusable --db, or when every lookup failed.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import sqlite3
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .jlcpcb import _read

API_URL = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList"
USER_AGENT = "boardtools-parts/1 (BOM availability check; https://github.com/jonkensta/boards)"
TIMEOUT = 20                 # seconds per request
WORKERS = 4                  # concurrent requests, to stay polite
PAGE_SIZE = 10               # the exact match ranks first; the rest are fuzzy hits
LOW_STOCK_FACTOR = 3         # warn when stock covers fewer than this many orders
# A complete in-stock snapshot holds ~600k parts; far fewer means a partial database
# (CDFER has served ~30k since September 2026) and a miss says little.
FULL_CATALOG_MIN = 100_000
CHIP_SIZES = ("01005", "0201", "0402", "0603", "0805", "1206", "1210", "1812", "2010", "2512")
_CHIP_RE = re.compile(r"(?<![0-9])(" + "|".join(CHIP_SIZES) + r")(?![0-9])")
_LCSC_RE = re.compile(r"^C([0-9]+)$")


class CatalogUnavailable(Exception):
    pass


class LookupFailed(Exception):
    pass


@dataclass
class Part:
    lcsc: str
    mpn: str
    manufacturer: str
    package: str
    kind: str          # basic | preferred | extended
    stock: int


def _kind(library_type: str, preferred) -> str:
    return "basic" if library_type == "base" else "preferred" if preferred else "extended"


class JlcpcbApi:
    name = "JLCPCB parts search (live)"
    missing = "not found at JLCPCB"
    partial = False
    workers = WORKERS

    def __init__(self, opener: Callable = urllib.request.urlopen):
        self.opener = opener

    def lookup(self, lcsc: str) -> Part | None:
        body = json.dumps({"keyword": lcsc, "currentPage": 1, "pageSize": PAGE_SIZE}).encode()
        req = urllib.request.Request(API_URL, data=body, method="POST", headers={
            "Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            with self.opener(req, timeout=TIMEOUT) as resp:
                data = json.load(resp)
        except (OSError, ValueError, http.client.HTTPException) as e:   # URLError is an OSError
            raise LookupFailed(str(e)) from e
        # Anything but the expected shape is a failed lookup, never "not found": an empty
        # list is only trusted when it sits where a real answer puts it.
        if not isinstance(data, dict) or data.get("code") != 200:
            code = data.get("code") if isinstance(data, dict) else "?"
            raise LookupFailed(f"unexpected API answer (code {code})")
        page = data.get("data")
        info = page.get("componentPageInfo") if isinstance(page, dict) else None
        items = info.get("list") if isinstance(info, dict) else None
        if not isinstance(items, list) or not all(
                isinstance(p, dict) and isinstance(p.get("componentCode"), str) for p in items):
            raise LookupFailed("unexpected API answer (no data.componentPageInfo.list of parts)")
        for p in items:
            if p["componentCode"] != lcsc:
                continue
            stock = p.get("stockCount")
            if not isinstance(stock, int) or isinstance(stock, bool):
                raise LookupFailed(f"unexpected API answer (stockCount {stock!r})")

            def text(key: str) -> str:
                v = p.get(key)
                return v if isinstance(v, str) else ""
            return Part(lcsc, text("componentModelEn"), text("componentBrandEn"),
                        text("componentSpecificationEn"),
                        _kind(text("componentLibraryType"), p.get("preferredComponentFlag") is True), stock)
        return None


class Catalog:
    """Offline source: a jlcparts-style SQLite snapshot (--db)."""

    workers = 1        # local and fast; sqlite3 connections also stay in their own thread

    def __init__(self, path: Path | str):
        if not Path(path).is_file():
            raise CatalogUnavailable(f"no catalog database at {path}")
        # immutable: CDFER's file is in WAL mode; this reads it without creating -wal/-shm files
        self.conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
        try:
            self.count, lo, hi = self.conn.execute(
                "SELECT count(*), min(lcsc), max(lcsc) FROM jlc_components").fetchone()
        except sqlite3.DatabaseError as e:
            raise CatalogUnavailable(f"{path}: not a JLCPCB parts database ({e})") from e
        self.partial = self.count < FULL_CATALOG_MIN
        self.name = f"{path} ({self.count} parts" + (f", C{lo}..C{hi}, PARTIAL)" if self.partial else ")")
        self.missing = "not in snapshot" + (
            "; snapshot is partial, the part may well exist" if self.partial
            else " (out of stock / below 5, or no such part)")

    def lookup(self, lcsc: str) -> Part | None:
        row = self.conn.execute(
            "SELECT mfr, manufacturer, package, library_type, preferred, stock"
            " FROM jlc_components WHERE lcsc = ?", (int(lcsc[1:]),)).fetchone()
        if row is None:
            return None
        mpn, manufacturer, package, library_type, preferred, stock = row
        return Part(lcsc, mpn or "", manufacturer or "", package or "",
                    _kind(library_type, preferred), int(stock or 0))


# --- checks -------------------------------------------------------------------

@dataclass
class Line:
    refs: str
    value: str
    lcsc: str
    qty: int
    part: Part | None = None
    looked_up: bool = False       # a well-formed LCSC number was queried
    failed: bool = False          # ... and the lookup itself failed (network/HTTP/API)
    issues: list[tuple[str, str]] = field(default_factory=list)   # (ERROR|WARNING, text)

    @property
    def status(self) -> str:
        levels = {lvl for lvl, _ in self.issues}
        return "ERROR" if "ERROR" in levels else "WARN" if "WARNING" in levels else "ok"


def _norm(s: str) -> str:
    return "".join(s.split()).casefold()


def check_bom(path: str, source, boards: int = 5) -> list[Line]:
    rows = _read(path, {"Refs", "Value", "Footprint", "MPN", "LCSC", "Qty"})
    lines = []
    for r in rows:
        try:
            qty = int(r["Qty"].strip())
        except ValueError:
            raise ValueError(f"{path}: {r['Refs']}: Qty is not an integer: {r['Qty']!r}") from None
        if qty < 1:   # a zero or negative line would cancel real demand when summed per LCSC
            raise ValueError(f"{path}: {r['Refs']}: Qty must be positive: {r['Qty']!r}")
        lines.append(Line(r["Refs"], r["Value"], r["LCSC"].strip(), qty))
    # stock is checked against the total per LCSC number: grouping by Description can
    # split one part over several BOM lines
    need: dict[str, int] = {}
    for ln in lines:
        need[ln.lcsc] = need.get(ln.lcsc, 0) + ln.qty * boards
    codes = sorted(c for c in need if _LCSC_RE.match(c))

    def lookup(code: str) -> Part | LookupFailed | None:
        try:
            return source.lookup(code)
        except LookupFailed as e:
            return e
    if source.workers > 1:
        with ThreadPoolExecutor(source.workers) as pool:
            found = dict(zip(codes, pool.map(lookup, codes)))
    else:
        found = {c: lookup(c) for c in codes}

    for ln, r in zip(lines, rows):
        if not ln.lcsc:
            ln.issues.append(("WARNING", "no LCSC number (pick in JLCPCB's BOM tool or hand-assemble)"))
            continue
        if ln.lcsc not in found:
            ln.issues.append(("ERROR", f"malformed LCSC number {ln.lcsc!r}"))
            continue
        ln.looked_up = True
        part = found[ln.lcsc]
        if isinstance(part, LookupFailed):
            ln.failed = True
            ln.issues.append(("ERROR", f"lookup failed: {part}"))
            continue
        if part is None:
            ln.issues.append(("ERROR", source.missing))
            continue
        ln.part = part
        n = need[ln.lcsc]
        if part.stock < n:
            ln.issues.append(("WARNING", f"stock {part.stock} < {n} needed for {boards} boards"))
        elif part.stock < n * LOW_STOCK_FACTOR:
            ln.issues.append(("WARNING", f"low stock {part.stock} ({n} needed for {boards} boards)"))
        mpn = r["MPN"].strip()
        if mpn and _norm(mpn) != _norm(part.mpn):
            ln.issues.append(("WARNING", f"MPN {mpn} but catalog has {part.mpn}"))
        size = _CHIP_RE.search(r["Footprint"].split(":")[-1])
        if size and part.package in CHIP_SIZES and part.package != size.group(1):
            ln.issues.append(("WARNING", f"footprint is {size.group(1)} but catalog package is {part.package}"))
    return lines


# --- report -------------------------------------------------------------------

def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 3] + "..."


def report(lines: list[Line], source, out=None) -> tuple[int, int]:
    """Print the table and summary; return (errors, warnings) counted per BOM line."""
    out = out or sys.stdout
    print(f"source: {source.name}", file=out)
    if source.partial:
        print("warning: the snapshot is partial (a complete one holds ~600k parts), so "
              "'not in snapshot' is unreliable; drop --db to query JLCPCB live.", file=out)
    table = [("Refs", "Value", "LCSC", "Qty", "Type", "Stock", "Status", "Notes")]
    for ln in lines:
        p = ln.part
        table.append((_clip(ln.refs, 24), _clip(ln.value, 14), ln.lcsc or "-", str(ln.qty),
                      p.kind if p else "-", str(p.stock) if p else "-", ln.status,
                      "; ".join(text for _, text in ln.issues)))
    widths = [max(len(row[i]) for row in table) for i in range(len(table[0]) - 1)]
    for row in table:
        print(("  ".join(c.ljust(w) for c, w in zip(row, widths)) + "  " + row[-1]).rstrip(), file=out)
    errors = sum(ln.status == "ERROR" for ln in lines)
    warnings = sum(ln.status == "WARN" for ln in lines)
    kinds: dict[str, set[str]] = {}
    for ln in lines:
        if ln.part:
            kinds.setdefault(ln.part.kind, set()).add(ln.lcsc)
    ext = len(kinds.get("extended", ()))
    print(f"{len(lines)} BOM lines: {errors} error, {warnings} warning; distinct parts: "
          f"{len(kinds.get('basic', ()))} basic, {len(kinds.get('preferred', ()))} preferred, "
          f"{ext} extended" + (f" ({ext} extended-part loading fees)" if ext else ""), file=out)
    return errors, warnings


def main(argv: list[str], opener: Callable = urllib.request.urlopen) -> int:
    # argv = ["parts", bom.csv, options...]
    ap = argparse.ArgumentParser(prog="boardtools parts",
                                 description="Check BOM LCSC numbers against JLCPCB's parts catalog.")
    ap.add_argument("bom", help="KiCad BOM CSV from jobsets/fab.kicad_jobset")
    ap.add_argument("--db", help="offline: jlcparts-style SQLite snapshot instead of the live API")
    ap.add_argument("--boards", type=int, default=5, help="boards ordered, for the stock check (default 5)")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    args = ap.parse_args(argv[1:])
    if args.boards < 1:
        ap.error("--boards must be at least 1")
    try:
        source = Catalog(args.db) if args.db else JlcpcbApi(opener)
        lines = check_bom(args.bom, source, args.boards)
    except CatalogUnavailable as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    errors, warnings = report(lines, source)
    looked_up = [ln for ln in lines if ln.looked_up]
    if looked_up and all(ln.failed for ln in looked_up):
        print("error: every catalog lookup failed (offline, or the API changed?)", file=sys.stderr)
        return 2
    return 1 if errors or (args.strict and warnings) else 0
