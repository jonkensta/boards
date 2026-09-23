"""CLI entry point: python3 -m boardtools <command> ...

Commands:
  layers <board.kicad_pcb>            print copper layers (comma-separated); exit 1 if none
  info   <board.kicad_pcb>            print title block and layer count
  jlcpcb pos|bom <in.csv> <out.csv>   convert KiCad CSV exports to JLCPCB upload format
  parts  <bom.csv> [--db PATH] [--boards N] [--strict]
                                      check BOM LCSC numbers against JLCPCB's live parts
                                      search (or an offline SQLite snapshot); exit 1 on errors
"""

from __future__ import annotations

import sys

from . import jlcpcb, parts, pcb


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    cmd = argv[1]
    try:
        if cmd == "layers" and len(argv) == 3:
            layers = pcb.copper_layers(pcb.load(argv[2]))
            if not layers:
                print(f"error: no copper layers found in {argv[2]}", file=sys.stderr)
                return 1
            print(",".join(layers))
            return 0
        if cmd == "info" and len(argv) == 3:
            root = pcb.load(argv[2])
            for k, v in pcb.title_block(root).items():
                print(f"{k}: {v}")
            print(f"copper layers: {len(pcb.copper_layers(root))}")
            return 0
        if cmd == "jlcpcb":
            return jlcpcb.main(argv[1:])
        if cmd == "parts":
            return parts.main(argv[1:])
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
