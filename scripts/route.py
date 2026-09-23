#!/usr/bin/env python3
"""Autoroute a placed board with Freerouting; writes a NEW routed board, never the source.

    scripts/route.py boards/<id>/<leaf>.kicad_pcb [-o DIR] [--strip] [--passes N]

1. boardtools.specctra writes DIR/<leaf>.dsn from the board and its .kicad_pro rules
   (existing tracks and vias go in as protected wiring).
2. Freerouting routes it headless to DIR/<leaf>.ses, by default in the Docker image
   ghcr.io/freerouting/freerouting:<FREEROUTING_VERSION>; FREEROUTING="java -jar /path/x.jar"
   uses a local jar instead (it needs Java 25+).
3. The session's new wires and vias are appended to a copy of the board as (segment ...) and
   (via ...) and written to DIR/<leaf>.kicad_pcb, next to copies of the .kicad_pro, .kicad_dru
   and schematic sheets so `kicad-cli pcb drc --schematic-parity` works on DIR (`make route`
   runs it).

DIR defaults to boards/<id>/out/route/, which is deleted and recreated on every run; a custom
-o DIR must be new or empty and is never cleared. Review the result, then copy it over the
source board by hand (or open it in KiCad and compare).
--strip drops existing tracks and vias first.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from boardtools import pcb, sexpr, specctra  # noqa: E402

Q = sexpr.Quoted
VERSION = os.environ.get("FREEROUTING_VERSION", "2.4.1")


def _n(v: float) -> str:
    return f"{round(v, 6) + 0.0:.6f}".rstrip("0").rstrip(".")


def freerouting_cmd(workdir: str, dsn: str, ses: str, passes: int) -> list[str]:
    args = ["--gui-enabled=false", "--api_server-enabled=false",
            "--usage_and_diagnostic_data-disable_analytics=true",
            "-de", dsn, "-do", ses, "-mp", str(passes)]
    custom = os.environ.get("FREEROUTING")
    if custom:
        return shlex.split(custom) + [os.path.join(workdir, dsn) if a == dsn else os.path.join(workdir, ses) if a == ses
                                      else a for a in args]
    return ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp",
            "-v", f"{os.path.abspath(workdir)}:/work", "-w", "/work", "--entrypoint", "java",
            f"ghcr.io/freerouting/freerouting:{VERSION}", "-jar", "/app/freerouting-executable.jar"] + args


def add_routes(root: sexpr.Node, wires: list[dict], vias: list[dict], copper: list[str]) -> tuple[int, int]:
    """Append SES wires/vias (skipping protected ones) to a parsed board; returns counts added."""
    # KiCad 10 refers to nets by name; older boards have a (net code "name") table.
    codes = {n[2]: n[1] for n in sexpr.children(root, "net") if len(n) > 2}
    net = lambda name: ["net", codes[name]] if codes else ["net", Q(name)]
    items = []
    for w in wires:
        if w["protected"]:
            continue
        for (x1, y1), (x2, y2) in zip(w["points"], w["points"][1:]):
            if (x1, y1) == (x2, y2):
                continue
            items.append(["segment", ["start", _n(x1), _n(y1)], ["end", _n(x2), _n(y2)], ["width", _n(w["width"])],
                          ["layer", Q(w["layer"])], net(w["net"]), ["uuid", Q(str(uuid.uuid4()))]])
    nseg = len(items)
    for v in vias:
        if v["protected"]:
            continue
        size, drill = specctra.parse_via_name(v["padstack"])
        items.append(["via", ["at", _n(v["x"]), _n(v["y"])], ["size", _n(size)], ["drill", _n(drill)],
                      ["layers", Q(copper[0]), Q(copper[-1])], net(v["net"]), ["uuid", Q(str(uuid.uuid4()))]])
    # KiCad writes tracks after footprints/graphics and before zones; keep that order.
    at = next((i for i, el in enumerate(root) if isinstance(el, list) and el[0] in ("zone", "group", "embedded_fonts")),
              len(root))
    root[at:at] = items
    return nseg, len(items) - nseg


def prepare_outdir(board: str, outdir: str | None) -> str:
    """Create the output directory and return its resolved path.

    Default (`outdir` None): `<board dir>/out/route`, the only directory this script ever
    deletes. `out/` and `out/route` must be real directories (not symlinks), and the path is
    removed and recreated, so no stale symlink or hard link survives for any later write
    (including `make route`'s drc.rpt).

    Custom: must not exist or be an empty real directory; nothing there is ever deleted. It
    must not contain the input board, and may be inside the board's directory only under a
    real `out/`.
    """
    src = os.path.dirname(os.path.realpath(board))
    if outdir is None:
        out = os.path.join(src, "out", "route")
        for d in (os.path.dirname(out), out):
            if os.path.islink(d) or (os.path.lexists(d) and not os.path.isdir(d)):
                raise ValueError(f"{d} must be a real directory, not a symlink or file")
        if os.path.realpath(out) != out:
            raise ValueError(f"{out} does not resolve to itself")
        if os.path.lexists(out):
            shutil.rmtree(out)
        os.makedirs(out)
        return out
    out = os.path.realpath(outdir)
    inside = lambda p, d: os.path.commonpath([p, d]) == d
    if inside(os.path.realpath(board), out):
        raise ValueError(f"output directory {out} contains the input board")
    if inside(out, src) and not inside(out, os.path.join(src, "out")):
        raise ValueError(f"refusing to write into the source board's directory: {out}")
    if os.path.lexists(outdir):
        if os.path.islink(outdir.rstrip(os.sep)) or not os.path.isdir(outdir):
            raise ValueError(f"output path {outdir} is a symlink or not a directory")
        if os.listdir(outdir):
            raise ValueError(f"output directory {outdir} is not empty (only the default out/route is ever cleared)")
    os.makedirs(out, exist_ok=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    ap.add_argument("board", help="boards/<id>/<leaf>.kicad_pcb")
    ap.add_argument("-o", "--outdir", help="output directory (default: <board dir>/out/route)")
    ap.add_argument("--strip", action="store_true", help="drop existing tracks and vias before routing")
    ap.add_argument("--passes", type=int, default=int(os.environ.get("PASSES", 100)),
                    help="maximum Freerouting passes (default 100)")
    ap.add_argument("--default-outdir", action="store_true",
                    help="refuse -o (make route DRCs <board dir>/out/route, so it must be the output)")
    a = ap.parse_args()
    if a.default_outdir and a.outdir is not None:
        print("error: make route always writes <board dir>/out/route; run scripts/route.py "
              "directly for -o", file=sys.stderr)
        return 2

    src_dir = os.path.dirname(os.path.realpath(a.board))
    leaf = os.path.splitext(os.path.basename(a.board))[0]
    try:
        out = prepare_outdir(a.board, a.outdir)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    root = pcb.load(a.board)
    with open(os.path.join(src_dir, f"{leaf}.kicad_pro"), encoding="utf-8") as f:
        project = json.load(f)
    if a.strip:
        root[:] = [el for el in root if not (isinstance(el, list) and el[0] in ("segment", "arc", "via"))]
    copper = pcb.copper_layers(root)

    dsn, ses = f"{leaf}.dsn", f"{leaf}.ses"
    text, nets = specctra.dsn(root, project, leaf)
    with open(os.path.join(out, dsn), "w", encoding="utf-8") as f:
        f.write(text)
    cmd = freerouting_cmd(out, dsn, ses, a.passes)
    print("routing:", " ".join(shlex.quote(c) for c in cmd), flush=True)
    with open(os.path.join(out, "freerouting.log"), "w", encoding="utf-8") as log:
        rc = subprocess.run(cmd, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
    with open(os.path.join(out, "freerouting.log"), encoding="utf-8", errors="replace") as log:
        summary = [l.rstrip() for l in log if "stage completed" in l or "finished with state" in l]
    for line in summary:
        print("  " + line.split("] ", 1)[-1][:200])
    if rc != 0 or not os.path.exists(os.path.join(out, ses)):
        print(f"error: Freerouting failed (exit {rc}); see {os.path.join(out, 'freerouting.log')}", file=sys.stderr)
        return 1

    with open(os.path.join(out, ses), encoding="utf-8") as f:
        wires, vias = specctra.read_ses(f.read(), nets)
    unknown = sorted({w["layer"] for w in wires} - set(copper))
    if unknown:
        print(f"error: session uses layers not on the board: {unknown}", file=sys.stderr)
        return 1
    nseg, nvia = add_routes(root, wires, vias, copper)
    with open(os.path.join(out, f"{leaf}.kicad_pcb"), "w", encoding="utf-8") as f:
        f.write(sexpr.dumps(root) + "\n")
    # Project, rules and every sheet, so parity DRC in `out` sees the same design.
    for name in os.listdir(src_dir):
        if name.endswith(".kicad_sch") or name in (f"{leaf}.kicad_pro", f"{leaf}.kicad_dru"):
            shutil.copyfile(os.path.join(src_dir, name), os.path.join(out, name))
    print(f"added {nseg} segments and {nvia} vias -> {os.path.join(out, leaf + '.kicad_pcb')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
