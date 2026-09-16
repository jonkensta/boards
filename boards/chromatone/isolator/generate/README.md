# generate/

How rev A of this board was first produced, without opening KiCad: `schematic.py`
writes `isolator.kicad_sch` from the stock symbol libraries, `pcb.py` writes
`isolator.kicad_pcb` (placement, routing, pours, outline, silk) from the
schematic's netlist and the stock footprint libraries, using `boardtools.sexpr`.

```sh
python3 boards/chromatone/isolator/generate/schematic.py
kicad-cli sch export netlist --format kicadsexpr -o boards/chromatone/isolator/generate/isolator.net boards/chromatone/isolator.kicad_sch
python3 boards/chromatone/isolator/generate/pcb.py
kicad-cli pcb drc --refill-zones --save-board --schematic-parity boards/chromatone/isolator.kicad_pcb
```

Regenerating replaces every UUID and discards any edits made in the KiCad GUI.
Once the board is edited by hand, treat these scripts as history, not as the source.
