# generate/

How rev A of this board was produced without opening KiCad: `schematic.py` writes
`node.kicad_sch` from the stock symbol libraries (plus `boards:SW-18010P` from `lib/`) using
`boardtools.schgen`. Blocks are joined with local net labels; the RP2040's crystal, TESTEN and
supply pins are the only direct wiring. `sch-1.png` is the rendered sheet.

```sh
python3 boards/net/node/generate/schematic.py
kicad-cli sch erc --severity-error --severity-warning --exit-code-violations -o /tmp/erc.rpt boards/net/node/node.kicad_sch
kicad-cli sch export pdf -o /tmp/node.pdf boards/net/node/node.kicad_sch && pdftoppm -r 100 -png -singlefile /tmp/node.pdf boards/net/node/generate/sch-1
```

`pcb.py` places and routes the board (48 x 48 mm, 4 layers; see the README's PCB section) from
the netlist with `boardtools.pcbgen`. Regenerate with:

```sh
kicad-cli sch export netlist --format kicadsexpr -o boards/net/node/generate/node.net boards/net/node/node.kicad_sch
python3 boards/net/node/generate/pcb.py           # --pads [REF ...] prints pad centres; --place writes placement only
kicad-cli pcb drc --refill-zones --save-board --schematic-parity -o /dev/null boards/net/node/node.kicad_pcb
make check BOARD=net/node
kicad-cli pcb render --side top --zoom 1.0 --width 400 --height 400 --background opaque -o boards/net/node/out/top.png boards/net/node/node.kicad_pcb
```

`pcb.py` fails (AssertionError, nothing written) if the link connectors lose their tiling
alignment or if any pad or courtyard comes within 3.7 mm of a mounting-hole centre; DRC enforces
the same hole rule through a keepout annulus per hole (`Board.keepout(..., r_in=2.6, pads=False,
footprints=False, tracks=True)`), see the README's Decisions.

`node.net` is git-ignored (`*.net`), so export it before running `pcb.py`. Without the
`--save-board` step the committed board has unfilled zones. With the flatpak KiCad, `-o` paths
must be under `$HOME` (the sandbox does not see `/tmp`).

Regenerating replaces every UUID and discards any edits made in the KiCad GUI.
Once the schematic or board is edited by hand, treat these scripts as history, not as the source.
