# boards

KiCad PCB projects plus the tooling to scaffold, check, and export them.
Requires KiCad 10 (`kicad-cli` on `PATH`), GNU make, Python 3, and `zip`.

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

make check BOARD=blinky     # ERC + DRC with schematic parity; fails on errors (STRICT=1: also warnings)
make fab   BOARD=blinky     # everything a fab/assembly house needs -> out/blinky/
make check                  # all boards
make fab                    # all boards
```

`make fab` produces, per board:

| Output | Path |
| --- | --- |
| Gerbers (copper, paste, silk, mask, edge) | `out/<name>/gerbers/` |
| Excellon drill (PTH/NPTH split) + map | `out/<name>/drill/` |
| Gerbers + drill zipped for upload | `out/<name>/<name>-gerbers.zip` |
| Pick-and-place CSV (mm, DNP excluded) | `out/<name>/<name>-pos.csv` |
| BOM CSV grouped by Value/Footprint/MPN | `out/<name>/<name>-bom.csv` |
| Schematic PDF | `out/<name>/<name>-schematic.pdf` |
| STEP model | `out/<name>/<name>.step` |

Individual targets also exist: `make gerbers|drill|pos|bom|pdf|step|erc|drc [BOARD=name]`.

## Conventions

- Put `MPN` and `Manufacturer` fields on symbols; the BOM export uses them.
- Custom parts go in `lib/`; stock KiCad library parts are referenced as usual.
- Set the drill/place origin in each board (Place → Drill/Place File Origin); gerbers, drill, and position files use it.
- Board revision lives in the schematic title block.
