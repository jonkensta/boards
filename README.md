# boards

KiCad PCB projects plus the tooling to scaffold, check, and export them.
Requires KiCad 10 (`kicad-cli` on `PATH`), GNU make, Python 3, bash, and `unzip`.
No KiCad Python bindings are used anywhere (see "Design" below).

## Layout

```
boards/<id>/            one KiCad project per board, any depth; files named after the leaf dir
                        (boards/blinky/blinky.kicad_pro, boards/chromatone/isolator/isolator.kicad_pro)
lib/                    shared symbols, footprints, 3D models (nickname `boards` in every project)
templates/board/        project template used by `make new`
jobsets/fab.kicad_jobset  the one definition of every fabrication export (GUI and CLI)
boardtools/             Python helpers: s-expr parser, board facts, JLCPCB conversion, and the
                        schematic/board generators (schgen, pcbgen) used by boards/*/generate/
scripts/                scaffolder and smoke test
boards/<id>/out/        generated outputs (git-ignored)
.github/workflows/      CI: unit tests, smoke test, ERC/DRC, fab exports in kicad/kicad:10.0
```

## Boards

| Board | What | Status (2026-09-19) |
| --- | --- | --- |
| [`chromatone/isolator`](boards/chromatone/isolator/README.md) | ISO7720 isolated SPI daughterboard, Pi (3.3 V) -> SK9822 strip (5 V), 46 x 30 mm | Rev A layout done, review-clean; pick passives in JLCPCB's BOM tool, then orderable |
| [`chromatone/dac`](boards/chromatone/dac/README.md) | PCM5102A I2S line-out DAC (experiment), 56 x 36 mm | Rev A layout done, review-clean, fully numbered BOM; not yet built |
| [`net/node`](boards/net/node/README.md) | RP2040 sensor-net node with neighbour links and sensor build variants | Parked: schematic done, no layout, no firmware |

`boards/chromatone/README.md` holds the Chromatone-wide decisions, strip wiring, order and
bench checklists. Every board so far was generated from `generate/` scripts (see below) and
put through an adversarial Codex review loop before being called done.

## Usage

```sh
make new NAME=blinky        # scaffold boards/blinky (fresh UUIDs, 50×50 mm outline, lib tables wired to lib/)
make new NAME=proj/rev2     # nested ids work too: boards/proj/rev2/rev2.kicad_pro
kicad boards/blinky/blinky.kicad_pro

make check  BOARD=blinky    # ERC + DRC (schematic parity, zones refilled); fails on errors (STRICT=1: also warnings)
make fab    BOARD=blinky    # check, then run jobsets/fab.kicad_jobset -> boards/blinky/out/
make jlcpcb BOARD=blinky    # fab, then JLCPCB-format BOM + CPL -> boards/blinky/out/jlcpcb/
make parts  BOARD=blinky    # after fab: check every LCSC number in the BOM against JLCPCB's catalog
make check                  # all boards
make fab                    # all boards
```

`make fab` produces, per board (paths below are inside `boards/<id>/out/`):

| Output | Path |
| --- | --- |
| ERC/DRC reports (gating violations, plus a separate warnings report) | `{erc,drc}.rpt`, `{erc,drc}-warnings.rpt` |
| Gerbers (all copper layers up to In30, paste, silk, mask, edge) + `.gbrjob` | `./` |
| Excellon drill (PTH/NPTH split) + Gerber X2 maps | `drill/` |
| Gerbers + drill zipped for fab upload (no drill maps) | `<leaf>-gerbers.zip` |
| Pick-and-place CSV (mm, drill origin, DNP excluded) | `<leaf>-all-pos.csv` |
| BOM CSV grouped by Value/Description/Footprint/MPN/Manufacturer/LCSC | `<leaf>-bom.csv` |
| Schematic PDF | `<leaf>-schematic.pdf` |
| STEP model | `<leaf>.step` |
| JLCPCB CPL + BOM (`make jlcpcb`) | `jlcpcb/` |

The same jobset runs from the KiCad project manager: Jobsets → open `jobsets/fab.kicad_jobset`
→ run. Change export settings there once and both GUI and CI follow.

Other targets: `make parts` (see boardtools below), `make export` (jobset without the Makefile checks), `make erc|drc`, `make test`
(boardtools unit tests), `make smoke` (scaffolds throwaway 2- and 8-layer boards in a temp dir
and runs the whole pipeline, including a deliberate DRC failure), `make list`, `make clean`.

KiCad 10 **design variants** (per-symbol DNP/field overrides, used by `net/node`) are honoured
by `kicad-cli sch export bom --variant <name>` and `pcb export pos --variant <name>`; the
jobset and `make jlcpcb` export the default variant only (backlog item 9 in `CLAUDE.md`).

## boardtools

```sh
python3 -m boardtools layers boards/blinky/blinky.kicad_pcb   # F.Cu,In1.Cu,In2.Cu,B.Cu
python3 -m boardtools info   boards/blinky/blinky.kicad_pcb   # title block + layer count
python3 -m boardtools jlcpcb pos <kicad-pos.csv> <cpl.csv>
python3 -m boardtools jlcpcb bom <kicad-bom.csv> <jlc-bom.csv>   # warns on lines without LCSC
python3 -m boardtools parts <kicad-bom.csv> [--db PATH] [--boards N] [--strict]
```

`parts` (and `make parts`, which checks the BOM `make fab` left in `out/` and refuses if it
is missing or older than the schematics, project file or jobset) is a **manual pre-order check**, not part of CI, because it
needs the network and uses the undocumented search endpoint behind jlcpcb.com/parts (one
request per distinct LCSC number, four at a time), which JLCPCB may change without notice.
`--db PATH` queries a jlcparts-style SQLite snapshot offline instead. It prints one row per
BOM line with basic/preferred/extended, live stock, and any problems:

- error: LCSC number malformed, not found at JLCPCB, or lookup failed (network/HTTP).
  With `--db` a miss is only "not in snapshot": snapshots omit parts with fewer than 5 in
  stock, and one with far fewer than ~600k parts is flagged as partial.
- warning: no LCSC number (nothing marks a line as hand-assembled, so this may be deliberate),
  stock below or within 3x of Qty x `--boards` (default 5, summed per LCSC number), MPN differs
  from the catalog, chip size in the footprint (0402/0603/...) differs from the catalog package.
- the summary counts distinct extended parts, each of which costs JLCPCB's loading fee.

Exit 1 on errors (`--strict` or `make parts STRICT=1`: also warnings), 2 if every lookup
failed or `--db` is unusable. Extra options go through `PARTS_ARGS`, e.g. `make parts PARTS_ARGS='--boards 10'`.

## Generating boards from Python

`boardtools.schgen` and `boardtools.pcbgen` write native `.kicad_sch` / `.kicad_pcb` files from
short Python scripts using the stock symbol and footprint libraries. `boards/*/*/generate/`
show the pattern: place symbols on the 1.27 mm grid, draw wires (or local labels for big parts),
run ERC, export the netlist, place footprints, route with `N(ref, pin)` net lookups, pour, run
DRC with `--refill-zones --save-board`, render. No KiCad Python bindings are involved.
Regenerating replaces every UUID, so once a board is edited in the KiCad GUI the scripts become
history rather than the source. `CLAUDE.md` lists the format details that cost time to learn
(pin transforms, junctions, PWR_FLAG, 0.65 mm pitch fan-out, mirrored silk, keepouts).

## Review workflow

Tooling changes and boards are reviewed adversarially with the Codex CLI: one fresh
`codex exec -s read-only` review, then `codex exec resume --last` rounds after each fix until
it reports no substantive findings. Codex is asked to reproduce (run `make test`/`make smoke`,
scaffold boards, run DRC in a temp copy), not just read. The findings that changed the design
are summarised in `CLAUDE.md` under "Review history".

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
  and JLCPCB conversion use them. Put ratings (dielectric, voltage, tolerance) in `Description`;
  it is exported and appended to the JLCPCB Comment.
- Custom parts go in `lib/`; stock KiCad library parts are referenced as usual.
- The template sets the drill/place origin at the outline's bottom-left corner; move it if you
  move the outline. Gerbers, drill, and position files use it.
- Board revision lives in the schematic title block.
- JLCPCB rotations are passed through unchanged; check the placement preview on the order page.
- Mounting holes get copper keepouts (`Board.keepout`) and nylon standoffs; on isolated boards
  metal hardware would tie the domains together.
- Passive references go on `F.Fab` (hidden); silk carries connector pin labels and test-point
  names instead.

## Where things stand

- Tooling is complete for the current workflow: scaffold, check, export, JLCPCB files, CI.
- Backlog, ranked, lives in `CLAUDE.md` ("Ideas not yet implemented"): order bundle with a
  manifest, BOM/CPL lint (catalog side done: `make parts`), per-fab constraint profiles, HTML BOM, assembly drawings and revision
  diffs, panelization, revision in PCB markings, hierarchical sheets in `schgen`, per-variant
  jobset outputs.
- Known gap: `pcbgen` does not yet carry a schematic DNP flag onto footprints (parity DRC only
  warns about it).
