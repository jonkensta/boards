# boards

KiCad PCB projects plus the tooling to scaffold, check, and export them.
Requires KiCad 10 (`kicad-cli` on `PATH`), GNU make, Python 3, bash, and `unzip`.
No KiCad Python bindings are used anywhere (see "Design" below).

## Layout

```
boards/<name>/          one KiCad project per board (<name>.kicad_pro/.kicad_sch/.kicad_pcb)
lib/                    shared symbols, footprints, 3D models (nickname `boards` in every project)
templates/board/        project template used by `make new`
jobsets/fab.kicad_jobset  the one definition of every fabrication export (GUI and CLI)
boardtools/             parse-only Python helpers (s-expr parser, board facts, JLCPCB conversion)
scripts/                scaffolder and smoke test
out/<name>/             generated outputs (git-ignored)
.github/workflows/      CI: unit tests, smoke test, ERC/DRC, fab exports in kicad/kicad:10.0
```

## Usage

```sh
make new NAME=blinky        # scaffold boards/blinky (fresh UUIDs, 50×50 mm outline, lib tables wired to lib/)
kicad boards/blinky/blinky.kicad_pro

make check  BOARD=blinky    # ERC + DRC (schematic parity, zones refilled); fails on errors (STRICT=1: also warnings)
make fab    BOARD=blinky    # check, then run jobsets/fab.kicad_jobset -> out/blinky/
make jlcpcb BOARD=blinky    # fab, then JLCPCB-format BOM + CPL -> out/blinky/jlcpcb/
make check                  # all boards
make fab                    # all boards
```

`make fab` produces, per board:

| Output | Path |
| --- | --- |
| ERC/DRC reports (gating violations, plus a separate warnings report) | `out/<name>/{erc,drc}.rpt`, `{erc,drc}-warnings.rpt` |
| Gerbers (all copper layers up to In30, paste, silk, mask, edge) + `.gbrjob` | `out/<name>/` |
| Excellon drill (PTH/NPTH split) + Gerber X2 maps | `out/<name>/drill/` |
| Gerbers + drill zipped for fab upload (no drill maps) | `out/<name>/<name>-gerbers.zip` |
| Pick-and-place CSV (mm, drill origin, DNP excluded) | `out/<name>/<name>-all-pos.csv` |
| BOM CSV grouped by Value/Footprint/MPN/Manufacturer/LCSC | `out/<name>/<name>-bom.csv` |
| Schematic PDF | `out/<name>/<name>-schematic.pdf` |
| STEP model | `out/<name>/<name>.step` |
| JLCPCB CPL + BOM (`make jlcpcb`) | `out/<name>/jlcpcb/` |

The same jobset runs from the KiCad project manager: Jobsets → open `jobsets/fab.kicad_jobset`
→ run. Change export settings there once and both GUI and CI follow.

Other targets: `make export` (jobset without the Makefile checks), `make erc|drc`, `make test`
(boardtools unit tests), `make smoke` (scaffolds throwaway 2- and 8-layer boards in a temp dir
and runs the whole pipeline, including a deliberate DRC failure), `make list`, `make clean`.

## boardtools

```sh
python3 -m boardtools layers boards/blinky/blinky.kicad_pcb   # F.Cu,In1.Cu,In2.Cu,B.Cu
python3 -m boardtools info   boards/blinky/blinky.kicad_pcb   # title block + layer count
python3 -m boardtools jlcpcb pos <kicad-pos.csv> <cpl.csv>
python3 -m boardtools jlcpcb bom <kicad-bom.csv> <jlc-bom.csv>   # warns on lines without LCSC
```

## Design

- **Exports live in the jobset, checks live in the Makefile.** KiCad jobsets are the native,
  declarative way to define outputs and `kicad-cli jobset run` executes them headlessly. The
  Makefile adds what jobsets cannot: a separate warnings report, `STRICT`, purging stale outputs,
  and a hard guarantee that ERC/DRC pass before anything is exported (inside a jobset, a failing
  job only stops its own destination, and only with `--stop-on-error`).
- **No KiCad Python bindings.** The SWIG `pcbnew` module is deprecated and removed in KiCad 11;
  the IPC API needs a running KiCad and cannot export before KiCad 11. `boardtools` therefore
  only parses files (s-expressions, JSON, CSV). Anything that must modify a design goes through
  `kicad-cli` or the jobset.
- **Template rules are conservative** (0.15 mm track/clearance, 0.3 mm drill, 0.3 mm copper-to-edge).
  Tighten or loosen per board in Board Setup → Constraints to match the fab.

## Conventions

- Put `MPN`, `Manufacturer`, and (for JLCPCB assembly) `LCSC` fields on symbols; the BOM export
  and JLCPCB conversion use them.
- Custom parts go in `lib/`; stock KiCad library parts are referenced as usual.
- The template sets the drill/place origin at the outline's bottom-left corner; move it if you
  move the outline. Gerbers, drill, and position files use it.
- Board revision lives in the schematic title block.
- JLCPCB rotations are passed through unchanged; check the placement preview on the order page.
