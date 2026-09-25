# generate/

How rev A of this board was produced without opening KiCad: `schematic.py` writes
`node.kicad_sch` from the stock symbol libraries (plus `boards:SW-18010P` from `lib/`) using
`boardtools.schgen`. Blocks are joined with local net labels; the RP2040's crystal, TESTEN and
supply pins are the only direct wiring. `sch-1.png` is the rendered sheet.

```sh
python3 boards/net/node/generate/schematic.py
mkdir -p boards/net/node/out
kicad-cli sch erc --severity-error --severity-warning --exit-code-violations -o boards/net/node/out/erc-gen.rpt boards/net/node/node.kicad_sch
kicad-cli sch export pdf -o boards/net/node/out/node.pdf boards/net/node/node.kicad_sch && pdftoppm -r 100 -png -singlefile boards/net/node/out/node.pdf boards/net/node/generate/sch-1
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

`pcb.py` also fails if crystal-net copper (XIN, XOUT, the R1-Y1 node) comes within 1.0 mm of any
other non-GND copper on the same layer, or within 2.0 mm of the LED nets (+5V, LED_DATA, LED_DIN,
LED_CH1..3) or any pad of the corner LEDs D1..D4 (`xtal_check.py`,
see the README's crystal isolation), or if the crystal guard pour's outline comes within 0.2 mm of copper
other than GND and the crystal nets. Audit a board file with
`python3 boards/net/node/generate/xtal_check.py [board] [radius]` (every net within `radius`,
default 1.5 mm, plus the crystal track lengths; `--raw` drops the U1 pin-field exemption).

The corner LEDs are laid out once for the NW corner (`LED_LOCAL`, `LED_A` / `LED_B`) and rotated a
quarter turn per corner with `cw()`, which asserts a square board; the chain lanes are one NW-frame
path rotated onto the N, W and S edges (`route_leds`). The decoupling-loop numbers in the README
come from a scratch script run on the DRC-saved board (`--save-board` first: generated segments
carry net codes, saved ones net names).

`node.net` is git-ignored (`*.net`), so export it before running `pcb.py`. Without the
`--save-board` step the committed board has unfilled zones. With the flatpak KiCad, `-o` paths
must be under `$HOME` (the sandbox does not see `/tmp`).

Regenerating replaces every UUID and discards any edits made in the KiCad GUI.
Once the schematic or board is edited by hand, treat these scripts as history, not as the source.
