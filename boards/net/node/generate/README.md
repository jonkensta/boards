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

`pcb.py` places the board (48 x 48 mm, 4 layers; see the README's PCB section) from the
netlist with `boardtools.pcbgen`; routing has not started. Regenerate with:

```sh
kicad-cli sch export netlist --format kicadsexpr -o boards/net/node/generate/node.net boards/net/node/node.kicad_sch
python3 boards/net/node/generate/pcb.py           # --pads prints pad centres for routing
make check BOARD=net/node
kicad-cli pcb render --side top --zoom 1.0 --width 900 --height 900 --background opaque -o /tmp/top.png boards/net/node/node.kicad_pcb
```

`node.net` is git-ignored (`*.net`), so export it before running `pcb.py`. Until the
`copper_layers` re-insertion bug in pcbgen is fixed, each run adds another In1/In2 pair to the
layer list (harmless to KiCad, ugly in the file).

Regenerating replaces every UUID and discards any edits made in the KiCad GUI.
Once the schematic is edited by hand, treat this script as history, not as the source.
