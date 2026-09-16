# generate/

How rev A was produced without opening KiCad, using the shared `boardtools.schgen`
and `boardtools.pcbgen` helpers:

```sh
python3 boards/chromatone/dac/generate/schematic.py
kicad-cli sch export netlist --format kicadsexpr -o boards/chromatone/dac/generate/dac.net boards/chromatone/dac/dac.kicad_sch
python3 boards/chromatone/dac/generate/pcb.py
kicad-cli pcb drc --refill-zones --save-board --schematic-parity boards/chromatone/dac/dac.kicad_pcb
```

`pcb.py` asks the netlist which net each pad carries (`N(ref, pin)`), so pad roles
always follow the schematic. Regenerating replaces every UUID and discards GUI
edits; once the board is edited by hand, treat these scripts as history.
