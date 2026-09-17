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

There is no `pcb.py` yet: the board is not laid out. When it is, follow
`boards/chromatone/isolator/generate/` (netlist export, then `boardtools.pcbgen`).

Regenerating replaces every UUID and discards any edits made in the KiCad GUI.
Once the schematic is edited by hand, treat this script as history, not as the source.
