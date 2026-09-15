"""Convert KiCad position/BOM CSV exports into JLCPCB's assembly upload format.

KiCad position CSV (kicad-cli pcb export pos --format csv):
    Ref,Val,Package,PosX,PosY,Rot,Side           (Side is top/bottom)
JLCPCB CPL:
    Designator,Mid X,Mid Y,Rotation,Layer         (Layer is Top/Bottom)

KiCad BOM CSV as produced by jobsets/fab.kicad_jobset:
    Refs,Value,Footprint,MPN,Manufacturer,LCSC,Qty  (Refs is comma-separated)
Both are validated by header, so a correctly headed empty export converts to an
empty file while a zero-byte or foreign CSV is rejected.
JLCPCB BOM:
    Comment,Designator,Footprint,LCSC Part #

Rotation is passed through unchanged. JLCPCB's part orientation frequently
differs from KiCad's footprint zero, so review the placement preview on the
order page; per-part corrections belong in the footprint, not here.
"""

from __future__ import annotations

import csv
import sys
from typing import Iterable

CPL_HEADER = ["Designator", "Mid X", "Mid Y", "Rotation", "Layer"]
BOM_HEADER = ["Comment", "Designator", "Footprint", "LCSC Part #"]


def _read(path: str, required: set[str]) -> list[dict[str, str]]:
    """Read a CSV, validating the header even when there are no data rows."""
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        have = set(reader.fieldnames or [])
    missing = required - have
    if missing:
        raise ValueError(f"{path}: unexpected CSV header (missing columns {sorted(missing)})")
    return rows


def _write(path: str, header: list[str], rows: Iterable[list[str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def convert_pos(src: str, dst: str) -> int:
    rows = _read(src, {"Ref", "PosX", "PosY", "Rot", "Side"})
    out = []
    for r in rows:
        side = r["Side"].strip().lower()
        if side not in ("top", "bottom"):
            raise ValueError(f"{src}: {r['Ref']}: unexpected Side value {r['Side']!r}")
        out.append([r["Ref"], r["PosX"], r["PosY"], r["Rot"], side.capitalize()])
    _write(dst, CPL_HEADER, out)
    return len(out)


def convert_bom(src: str, dst: str, *, require_lcsc: bool = False) -> list[str]:
    """Write the JLCPCB BOM. Returns the list of BOM lines lacking an LCSC part number."""
    rows = _read(src, {"Refs", "Value", "Footprint", "LCSC"})
    out, no_lcsc = [], []
    for r in rows:
        lcsc = r["LCSC"].strip()
        if not lcsc:
            no_lcsc.append(r["Refs"])
        out.append([r["Value"], r["Refs"], r["Footprint"], lcsc])
    if require_lcsc and no_lcsc:
        raise ValueError("BOM lines without an LCSC part number: " + "; ".join(no_lcsc))
    _write(dst, BOM_HEADER, out)
    return no_lcsc


def main(argv: list[str]) -> int:
    # argv = ["jlcpcb", "pos"|"bom", src, dst]
    if len(argv) != 4 or argv[1] not in ("pos", "bom"):
        print("usage: boardtools jlcpcb pos <kicad-pos.csv> <out-cpl.csv>\n"
              "       boardtools jlcpcb bom <kicad-bom.csv> <out-bom.csv>", file=sys.stderr)
        return 2
    kind, src, dst = argv[1], argv[2], argv[3]
    try:
        if kind == "pos":
            n = convert_pos(src, dst)
            print(f"wrote {dst} ({n} placements)")
        else:
            missing = convert_bom(src, dst)
            print(f"wrote {dst}")
            for refs in missing:
                print(f"warning: no LCSC part number: {refs}", file=sys.stderr)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0
