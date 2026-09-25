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
boardtools/             Python helpers: s-expr parser, board facts, JLCPCB conversion, Specctra
                        DSN/SES, and the schematic/board generators (schgen, pcbgen) used by
                        boards/*/generate/
scripts/                scaffolder, smoke test, Freerouting autorouter (route.py)
boards/<id>/out/        generated outputs (git-ignored)
.github/workflows/      CI: unit tests, smoke test, ERC/DRC, fab exports in kicad/kicad:10.0
```

## Boards

| Board | What | Status (2026-09-19) |
| --- | --- | --- |
| [`chromatone/isolator`](boards/chromatone/isolator/README.md) | ISO7720 isolated SPI daughterboard, Pi (3.3 V) -> SK9822 strip (5 V), 46 x 30 mm | Rev A layout done, review-clean; pick passives in JLCPCB's BOM tool, then orderable |
| [`chromatone/dac`](boards/chromatone/dac/README.md) | PCM5102A I2S line-out DAC (experiment), 56 x 36 mm | Rev A layout done, review-clean, fully numbered BOM; not yet built |
| [`net/node`](boards/net/node/README.md) | RP2040 sensor-net node with neighbour links, four corner LEDs and sensor build variants, 48 x 48 mm, 4 layers | Rev A layout done and reviewed; ready to order after the owner's GUI check and quote (see its Resume path); no firmware yet |

`boards/chromatone/README.md` holds the Chromatone-wide decisions, strip wiring, order and
bench checklists. Every board so far was generated from `generate/` scripts (see below) and
put through an adversarial Codex review loop before being called done.

## Usage

```sh
make new NAME=blinky        # scaffold boards/blinky (fresh UUIDs, 50×50 mm outline, lib tables wired to lib/)
make new NAME=proj/rev2     # nested ids work too: boards/proj/rev2/rev2.kicad_pro
kicad boards/blinky/blinky.kicad_pro

make check  BOARD=blinky    # off-grid lint + ERC + DRC (schematic parity, zones refilled); fails on errors (STRICT=1: also warnings)
make fab    BOARD=blinky    # check, then run jobsets/fab.kicad_jobset -> boards/blinky/out/
make jlcpcb BOARD=blinky    # fab, then JLCPCB-format BOM + CPL -> boards/blinky/out/jlcpcb/
make parts  BOARD=blinky    # after fab: check every LCSC number in the BOM against JLCPCB's catalog
make check                  # all boards
make fab                    # all boards
make route  BOARD=blinky    # autoroute a placed board with Freerouting -> boards/blinky/out/route/ (see below)
```

`make fab` produces, per board (paths below are inside `boards/<id>/out/`):

| Output | Path |
| --- | --- |
| ERC/DRC reports (gating violations, plus a separate warnings report) | `{erc,drc}.rpt`, `{erc,drc}-warnings.rpt` |
| Off-grid connection points (gating; see `boardtools offgrid`) | `offgrid.rpt` |
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
and runs the whole pipeline, including a deliberate DRC failure and an off-grid child-sheet item), `make list`,
`make clean`.

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
python3 -m boardtools offgrid boards/blinky/blinky.kicad_sch [--grid 1.27]
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

`offgrid` lists every electrical connection point off the 1.27 mm grid (symbol pins computed
from the embedded library symbols with the instance's rotation/mirror/unit/body style, wire
and bus ends, bus entries, junctions, no-connects, labels, sheet pins) in the sheet and every
child sheet file, one line per item with the sheet file and the nearest grid point, and exits 1
if there are any. `erc/<id>` gates on it as well as on ERC (both always run, so every report is
fresh): KiCad's ERC only warns (`endpoint_off_grid`) and reports one pin per symbol. `Schematic.write()`
in schgen refuses to write an off-grid sheet.

## Generating boards from Python

`boardtools.schgen` and `boardtools.pcbgen` write native `.kicad_sch` / `.kicad_pcb` files from
short Python scripts using the stock symbol and footprint libraries. `boards/*/*/generate/`
show the pattern: place symbols on the 1.27 mm grid, draw wires (or local labels for big parts),
run ERC, export the netlist, place footprints, route with `N(ref, pin)` net lookups, pour, run
DRC with `--refill-zones --save-board`, render. No KiCad Python bindings are involved.
Regenerating replaces every UUID, so once a board is edited in the KiCad GUI the scripts become
history rather than the source. `CLAUDE.md` lists the format details that cost time to learn
(pin transforms, junctions, PWR_FLAG, 0.65 mm pitch fan-out, mirrored silk, keepouts).

## Autorouting (Freerouting)

For a board whose placement is done, `make route BOARD=<id>` autoroutes it with
[Freerouting](https://github.com/freerouting/freerouting) and DRCs the result:

```sh
make route BOARD=chromatone/isolator                     # keep existing tracks/vias, route the rest
make route BOARD=chromatone/isolator ROUTE_ARGS=--strip  # drop all tracks/vias first, route from scratch
PASSES=20 make route BOARD=...                           # cap Freerouting's passes (default 100)
```

It writes a **new** board, `boards/<id>/out/route/<leaf>.kicad_pcb` (next to copies of the
project, rules and schematic so parity DRC works there, plus the `.dsn`, `.ses`,
`freerouting.log` and `drc.rpt`), then runs the same strict DRC as `make check` with
`--save-board` so the copy has its zones filled. The source board is never touched: open the
routed copy in KiCad, review it, and copy it over `boards/<id>/<leaf>.kicad_pcb` by hand if you
keep it. The default output directory `out/route/` is the only thing the script ever deletes:
it checks that `out/` and `out/route/` are real directories, then removes and recreates
`out/route/`, so no planted symlink or hard link can redirect any write (including DRC's
report) onto a source file. `scripts/route.py -o DIR` takes a new or empty real directory
only, never clears it, and refuses one that contains the board or lies inside the board's
directory other than under `out/`. `make fab`/`make clean` delete `out/`, including this.

kicad-cli has no Specctra DSN export or SES import (only the pcbnew GUI and its SWIG bindings
do), so `boardtools/specctra.py` writes the DSN and reads the SES textually, and
`scripts/route.py` appends the session's new tracks and vias to a copy of the board.
Freerouting runs from the Docker image `ghcr.io/freerouting/freerouting:2.4.1` (the release
jar needs Java 25); set `FREEROUTING="java -jar /path/to/freerouting-2.4.1.jar"` to use a
local jar, `FREEROUTING_VERSION` to pick another image tag. It is not part of CI or smoke.

What goes into the DSN: copper layers, the Edge.Cuts outline (inner loops as cut-outs), every
pad with its real shape and rotation on either side (rect, roundrect, oval, circle; chamfered
pads as their rectangle; trapezoid and custom pads as a rectangle enclosing all their copper,
primitives and strokes included), SMD and THT, NPTH holes and slots (slot walls also get the
copper-to-edge clearance, as KiCad's DRC applies it),
rule-area keepouts on the board and inside footprints, copper pours as planes (zone holes as
windows), existing tracks and vias as protected wiring, and netclass track width / clearance /
via size from the `.kicad_pro` (patterns and explicit assignments; a net in several classes
takes each rule from the highest-priority class that sets it, as KiCad 10 does). Net, reference
and pin names that a DSN cannot carry (`"`, backslash, non-ASCII) get generated identifiers and
are mapped back on import. Not modelled: per-layer padstacks, blind/buried/micro vias, arcs
(existing ones go in as chords), `.kicad_dru` custom rules, length/differential-pair
constraints. Tracks get their netclass width, so give power nets a
netclass if they need to be wider than Default. The router knows nothing about analog
return paths or decoupling loops; route those by hand first and let it finish the rest.

Verified on `chromatone/isolator` and `chromatone/dac` with all routing stripped: 100 %
routed in 4 to 10 s, 0 DRC errors, 0 warnings, 0 unconnected, 0 parity issues. Also clean:
the isolator with R1 (30 deg) and U1 (90 deg) moved to the back, and with a quoted net name
and a hole in a ground pour.

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
  `kicad-cli` or the jobset. The one exception is `scripts/route.py`, which appends
  autorouted tracks to a *copy* of a board, because kicad-cli cannot import a Specctra session.
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
- Optional Freerouting autorouting (`make route`), outside CI.
- Backlog, ranked, lives in `CLAUDE.md` ("Ideas not yet implemented"): order bundle with a
  manifest, BOM/CPL lint (catalog side done: `make parts`), per-fab constraint profiles, HTML BOM, assembly drawings and revision
  diffs, panelization, revision in PCB markings, hierarchical sheets in `schgen`, per-variant
  jobset outputs, autorouter follow-ups.
- Known gap: `pcbgen` does not yet carry a schematic DNP flag onto footprints (parity DRC only
  warns about it).
