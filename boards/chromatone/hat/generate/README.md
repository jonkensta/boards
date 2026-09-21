# generate/

`schematic.py` writes `hat.kicad_sch` from the stock symbol libraries using
`boardtools.schgen`; the isolator and DAC blocks are the `chromatone/isolator` and
`chromatone/dac` schematics with grid-unit offsets and their Pi-side connectors replaced by
net labels on a `Connector:Raspberry_Pi_4` header symbol. `pcb.py` (not written yet) will do
the board the same way with `boardtools.pcbgen`.

```sh
python3 boards/chromatone/hat/generate/schematic.py
kicad-cli sch erc --severity-error --severity-warning -o boards/chromatone/hat/out/erc.rpt boards/chromatone/hat/hat.kicad_sch
kicad-cli sch export netlist --format kicadsexpr -o boards/chromatone/hat/generate/hat.net boards/chromatone/hat/hat.kicad_sch
python3 boards/chromatone/hat/generate/pcb.py
kicad-cli pcb drc --refill-zones --save-board --schematic-parity boards/chromatone/hat/hat.kicad_pcb
```

Library paths: `boardtools.kicadlibs` finds the flatpak libraries by itself; with the
flatpak `kicad-cli`, report paths must be under `$HOME` (`/tmp` is not shared).

Regenerating replaces every UUID and discards GUI edits.
