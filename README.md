# boards

KiCad PCB projects plus the tooling to scaffold, check, and export them.
Requires KiCad 10 (`kicad-cli` on `PATH`), GNU make, Python 3, bash, `zip`, and `unzip`.

## Layout

```
boards/<name>/      one KiCad project per board (<name>.kicad_pro/.kicad_sch/.kicad_pcb)
lib/                shared symbols, footprints, and 3D models (nickname `boards` in every project)
templates/board/    project template used by `make new`
scripts/            helper scripts
out/<name>/         generated outputs (git-ignored)
.github/workflows/  CI: ERC, DRC, and fab exports in the kicad/kicad:10.0 container
```

## Usage

```sh
make new NAME=blinky        # scaffold boards/blinky (fresh UUIDs, 50×50 mm outline, lib tables wired to lib/)
kicad boards/blinky/blinky.kicad_pro

make check BOARD=blinky     # ERC + DRC (schematic parity, zones refilled); fails on errors (STRICT=1: also warnings)
make fab   BOARD=blinky     # check, then export gerbers/drill/pos/BOM/PDF/STEP -> out/blinky/
make check                  # all boards
make fab                    # all boards
```

`make fab` produces, per board:

| Output | Path |
| --- | --- |
| ERC/DRC reports (gating violations, plus a separate warnings report) | `out/<name>/{erc,drc}.rpt`, `{erc,drc}-warnings.rpt` |
| Gerbers (copper, paste, silk, mask, edge) | `out/<name>/gerbers/` |
| Excellon drill (PTH/NPTH split) + map | `out/<name>/drill/` |
| Gerbers + drill zipped for fab upload (no drill maps) | `out/<name>/<name>-gerbers.zip` |
| Pick-and-place CSV (mm, DNP excluded) | `out/<name>/<name>-pos.csv` |
| BOM CSV grouped by Value/Footprint/MPN/LCSC | `out/<name>/<name>-bom.csv` |
| Schematic PDF | `out/<name>/<name>-schematic.pdf` |
| STEP model | `out/<name>/<name>.step` |

The position and BOM CSVs are generic KiCad output; assembly houses (JLCPCB, PCBWay) want their own column headers, so convert before uploading.

Individual targets also exist: `make export|gerbers|drill|pos|bom|pdf|step|erc|drc [BOARD=name]` (`export` skips the checks). `make smoke` scaffolds a throwaway board in a temp dir and runs the whole pipeline on it; CI runs it on every push.

## Conventions

- Put `MPN`, `Manufacturer`, and (for JLCPCB assembly) `LCSC` fields on symbols; the BOM export uses them.
- The template project ships conservative design rules (0.15 mm track/clearance, 0.3 mm drill, 0.3 mm copper-to-edge). Tighten or loosen per board in Board Setup → Constraints to match the fab you are ordering from.
- Custom parts go in `lib/`; stock KiCad library parts are referenced as usual.
- The template sets the drill/place origin at the outline's bottom-left corner; move it if you move the outline. Gerbers, drill, and position files use it.
- Board revision lives in the schematic title block.
