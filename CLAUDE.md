# CLAUDE.md

KiCad 10 board monorepo. `README.md` is the user-facing doc; this file holds the context that
shaped the tooling so it does not get re-derived or accidentally undone.

## Ground rules

- **Never introduce the SWIG `pcbnew` Python module** into anything CI or `make` depends on.
  It is deprecated in KiCad 9/10 and removed in KiCad 11. The only tolerated use is throwaway
  local experiments (the smoke test deliberately avoids it and edits board files textually).
- **`kicad-python` / `kipy` (IPC API)** is the official replacement but, in KiCad 9 and 10, it
  needs a running KiCad GUI, covers the PCB editor only, and cannot plot or export. KiCad 11 adds
  headless use via `kicad-cli` plus plotting. Revisit once the CI image is KiCad 11.
- **Exports are defined once in `jobsets/fab.kicad_jobset`.** Do not add parallel `kicad-cli
  pcb export ...` recipes to the Makefile; change the jobset instead so GUI and CLI stay in sync.
- **Outputs live in `boards/<id>/out/`**, hardcoded in both the Makefile and the jobset destinations
  (`${KIPRJMOD}/out/`), which keeps them depth-independent; a Make-only override would
  desynchronise them. `.gitignore` ignores any `out/` directory.
- **`boardtools/` is parse-only** (s-expressions, JSON, CSV). Anything that modifies a design
  goes through `kicad-cli` or the jobset.
- Run `make test && make smoke` before committing tooling changes. Smoke covers a 2-layer and a
  8-layer board with hostile layer names and silkscreen text, and a deliberate DRC failure.

## Keeping agent sessions bounded (learned the hard way on boards/net/node)

A previous session hit the 64k output-token cap seven times in a row, each time a turn of pure
reasoning with no tool call (13-30 min each); the "resume" nudge just started another one. The
cause was doing 0.4 mm pitch routing geometry in reasoning. Rules:

- **Never derive placement or routing coordinates in reasoning.** If more than a handful of
  numbers are needed, write a script (pad-centre dump via `pcb.py --pads`, the courtyard
  checker, a DRC-report-to-board-mm converter) and read its output. Every turn should end in a
  tool call or a message within a few paragraphs of thought.
- **Feedback signal is text, not pictures.** Iterate on the DRC report and `--pads` output;
  render (`kicad-cli pcb render`) at most once per block and at <= 400 px, only as a final check.
  A 900 px board render is ~180 KB and triggered the first runaway turn.
- **Never cat `.kicad_pcb`, `.kicad_sch` or `.net` files** (100-600 KB); grep or parse them
  with `boardtools.sexpr`.
- **One block per task**: place the crystal cluster, route the left-edge bundle, etc., DRC-clean
  it, commit, then the next. Do not take "route the board" as one prompt.
- `.claude/settings.json` in this repo caps thinking (`MAX_THINKING_TOKENS`) and sets medium
  effort for this reason; do not raise them for routing work.

## Working in this repo

- Layout: `boards/<id>/` projects (any depth; files named after the leaf directory, e.g.
  `boards/chromatone/isolator/isolator.kicad_pro`; the id is the path relative to `boards/`), `lib/` shared symbols/footprints/3D (nickname `boards`),
  `templates/board/` scaffold source, `jobsets/` exports, `boardtools/` Python, `scripts/`
  scaffolder + smoke, `out/` generated (git-ignored). `boards/` is empty until the first design.
- Entry points: `make new NAME=id`, `make check|fab|jlcpcb [BOARD=id]`, `make test`, `make smoke`.
  `make help` prints the list. Per-board targets are `erc/<id>`, `drc/<id>`, `check/<id>`,
  `export/<id>` (slash form so the pattern stem may itself contain slashes).
- **Adding a jobset job:** copy an existing block in `jobsets/fab.kicad_jobset`, give it a fresh
  UUID `id`, and add that id to the `only` list of the destinations that should include it
  (the folder destination lists every job except the map-less drill job; the archive lists
  ERC, DRC, gerbers, map-less drill). Then extend the output assertions in `scripts/smoke.sh`.
  Job ids are the fixed `6b1e2a10-0000-4000-8000-0000000000NN` series.
- **Editing template files:** `templates/board/board.kicad_pro` is the KiCad-10-native project
  with the baseline design rules; `board.kicad_sch` and `board.kicad_pcb` use literal UUIDs that
  `scripts/new-board.py` rewrites consistently (it also fills `{{LIBREL}}` in the lib tables
  with the right number of `..` for the board's depth) (same template UUID -> same fresh UUID, so the
  project's `sheets` entry keeps matching the schematic). Keep `{{NAME}}` placeholders only in
  text files. A jobset or DRC run creates `<name>.kicad_prl` next to the project; it is ignored.
- **Smoke fixtures are edited textually** (`sed`, small Python) rather than via pcbnew, on
  purpose. To add copper layers, insert `(N "InX.Cu" signal)` lines after `(0 "F.Cu" signal)`
  with N = 4, 6, 8, ... (KiCad 9+ numbering). A 0.1 mm `(segment ...)` on F.Cu is the standard
  way to provoke a DRC error against the template's 0.15 mm minimum.
- CI (`.github/workflows/ci.yml`) runs in `kicad/kicad:10.0` as root: `make test`, `make smoke`,
  `make -k check`, `make jlcpcb`; ERC/DRC reports upload even on failure, fab outputs on success.
  It passes with zero boards.
- Review workflow used so far: `\codex --profile shared exec -s read-only -o <file> "<prompt>"`
  for a fresh review, then `\codex --profile shared exec resume --last -c 'sandbox_mode="read-only"'`
  for re-check rounds until it answers NO SUBSTANTIVE FINDINGS. Codex can run `make test`/`make
  smoke` and scaffold boards in a temp copy itself; ask it to reproduce, not just read.
- Commits: author is the repo's git config (Jonathan Starr <github@jstarr.me>); do not
  override it. Push to `origin main` (GitHub `jonkensta/boards`, public).

## Verified KiCad 10.0.6 behaviour (kicad-cli / jobsets)

- `kicad-cli jobset run --file <jobset> <project.kicad_pro>` works headlessly. Without
  `--stop-on-error` every job runs regardless of earlier failures (exit code 6, but the zip and
  all exports are still produced). With it, a failing job stops **only the current
  destination**; later destinations still run their own job lists. Because both destinations in
  `fab.kicad_jobset` list ERC and DRC first, `--stop-on-error` does stop exports, but the
  destinations are still written (a folder/zip containing only the reports), and stale files
  from an earlier run are not removed. `make fab` therefore purges `out/<board>/`, runs the
  Makefile ERC/DRC, and only then runs the jobset.
- Jobset JSON: `{"meta":{"version":1},"jobs":[{id,type,description,settings}],"outputs":[{id,type:"folder"|"archive",only:[job ids],settings:{output_path[,format:"zip"]}}]}`.
  Settings keys per job type come from `common/jobs/job_*.cpp` in the KiCad source
  (`JOB_PARAM(...)` names). Job types used: `sch_erc`, `pcb_drc`, `pcb_export_gerbers`,
  `pcb_export_drill`, `pcb_export_pos`, `sch_export_bom`, `sch_export_plot_pdf`, `pcb_export_3d`.
  Also available: `special_execute` (run a command), `special_copyfiles`, `pcb_render`,
  `pcb_export_{pdf,svg,dxf,ipc2581,odb,gencad}`, `sch_export_{svg,dxf,netlist}`.
- ERC/DRC job `severity` is a bitmask: error=0x20, warning=0x10, exclusion=0x04.
  `fail_on_error: true` makes violations fail the job.
- `output_path` supports `${KIPRJMOD}` and `${PROJECTNAME}`; the repo uses
  `${KIPRJMOD}/../../out/${PROJECTNAME}/` so outputs land in `out/<board>/` at the repo root.
- **Quirk:** the gerbers job ignores `output_dir` (files land at the destination root). The
  drill job honours it. Position export appends `-all-pos` to the filename stem when
  `side: both` (hence `<name>-all-pos.csv`). Layers listed in the gerber job but absent from the
  board are silently skipped, so the job lists F.Cu, In1..In30.Cu, B.Cu and one jobset serves
  any stackup KiCad supports. (An earlier In1..In4 list silently dropped layers on 8-layer boards.)
- Gerber files are named after the *user* layer name (a custom "Top copper" name changes the
  filename but not the `.gtl` extension).
- `kicad-cli pcb drc` needs `--refill-zones` for correct results on zoned boards; gerbers use
  `check_zones`. `--severity-all` includes exclusions; use `--severity-error --severity-warning`.
- Empty schematics print "Failed to fetch schematic netlist for parity tests" during DRC parity
  but still succeed.
- `pcbnew.BOARD().Save()` rewrites the `.kicad_pro` next to it (drops `sheets`); that is how the
  template project got its KiCad-10-native structure. The schematic template is still KiCad 9
  format (`version 20250114`); KiCad 10 reads it and upgrades on first save. Board format
  version is 20260206.
- Docker image `kicad/kicad:10.0` (Debian) has `kicad-cli` and python3 but not `zip`; the
  jobset's archive destination produces the zip, so only `make`, `unzip` are installed in CI.
  Run the container as root (`options: --user root`) for apt.
- Make gotcha: pattern-rule targets (`erc/%`) must not be listed in `.PHONY`, or make skips the
  implicit-rule search and reports "Nothing to be done". `make VAR=x` beats `VAR := x` in the
  Makefile; use `override` for values that must stay fixed.
- `kicad-cli sch export bom` and the `sch_export_bom` job accept `${QUANTITY}` as a field; in a
  Makefile recipe it must be written `$${QUANTITY}` and single-quoted.
- KiCad position CSV columns are `Ref,Val,Package,PosX,PosY,Rot,Side` with Side `top`/`bottom`;
  JLCPCB wants `Designator,Mid X,Mid Y,Rotation,Layer` with `Top`/`Bottom`. Rotation is passed
  through; JLCPCB's zero orientation often differs from KiCad's, so the order-page preview is
  the final check (per-part corrections belong in footprints, not the converter).
- `python3 -m unittest discover -s boardtools/tests -t .` is what `make test` runs; tests use
  handwritten CSV/s-expr fixtures, so jobset export regressions are only caught by smoke.

## Generating KiCad files from Python (learned on boards/chromatone/isolator)

`boardtools/schgen.py` (`Schematic`: place/power/flag/wire/junction/text/box, `g()` grid helper,
`extends` flattening) and `boardtools/pcbgen.py` (`Netlist`, `Board`: footprint/seg/via/zone/
keepout/gr_*; `footprint()` returns pad centres in board-local mm) are the shared generators.
`boards/chromatone/isolator/generate/`, `boards/chromatone/dac/generate/` and
`boards/net/node/generate/` (RP2040, label-wired blocks, design variants) are the worked
examples. Route with `N(ref, pin)` net lookups from the netlist, never assumed pad roles: on the
DAC every resistor and the flying cap were initially backwards. Facts that cost time to discover:

- **Schematic connection points must sit on the 1.27 mm grid** or ERC reports every pin/wire
  end as `endpoint_off_grid`. Work in integer grid units and multiply.
- Symbol pin positions: library coords are y-up; screen is y-down. Offset = (px, -py), then
  rotate for `(at x y rot)` with (sx, sy) -> (sy, -sx) per 90 deg; `(mirror y)` negates x first.
  `Device:R` at rot 90 puts pin 1 on the left; `Device:LED` at rot 90 puts A on top, K below.
- A pin landing mid-wire needs the wire split plus an explicit `(junction ...)`. Power symbols'
  pins are `power_in`, so every rail fed only by a connector needs a `power:PWR_FLAG`.
- Power symbol net name = its Value; `power:+5V` with Value `+5V_LED` makes a separate net.
- Property text rotates with the symbol; set the property angle to `rot % 180` to keep it level.
- `lib_symbols` entries are the library symbol renamed to `Lib:Name` (sub-units keep bare names);
  none of the symbols used had `extends`, so no flattening was needed.
- `kicad-cli sch export netlist --format kicadsexpr` gives nets, per-component `tstamps`
  (= symbol UUID, used as the footprint `path "/<uuid>"` for schematic parity), datasheet,
  description and custom fields.
- PCB footprints embed the `.kicad_mod` renamed `Lib:Name` with `(at x y rot)` added; pad and
  `fp_text` angles must have the footprint rotation added (KiCad stores them absolute), graphics
  do not. Footprint rotation (px, py) -> (px cos r + py sin r, -px sin r + py cos r). Property
  positions are relative offsets in unrotated board coords. Footprints lacking a `Datasheet`
  or `Description` property need them added or parity DRC complains.
- Footprint `attr exclude_from_bom` (test points, holes) must match the symbol's `in_bom no`.
- Silk rules in the template project: text >= 0.8 mm / 0.12 mm stroke, 0.15 mm silk clearance,
  silk over pads is an error. Put passive references on F.Fab (hidden) and place the few silk
  labels deliberately; test points read best with their Value on silk instead of the reference.
- 0.65 mm pitch (TSSOP) with 0.2 mm clearance and 0.6 mm vias: a via can never sit at a pad
  column beside a neighbouring row; put vias at least (0.3 + 0.2) beyond the pad's x-span or
  0.65 mm away in y, use 0.2 mm traces, fan out with short stubs then 45 deg diagonals, and let
  DRC find the rest. Same-net overlap (via touching its own pad) is fine.
- Mirrored back-silk text: `justify left mirror` extends away from the anchor in board +x;
  `right mirror` extends toward it. Back-side labels near THT pads need ~1.5 mm from the ring.
- Rule-area keepouts: `(zone (net 0) ... (keepout (tracks not_allowed) (vias not_allowed)
  (pads allowed) (copperpour not_allowed) (footprints allowed)) (polygon ...))`. With `pads
  not_allowed` an NPTH mounting hole inside its own keepout is a violation.
- `kicad-cli pcb drc --refill-zones --save-board` stores the zone fills; without it the committed
  board looks unfilled in the GUI and in renders.
- `kicad-cli pcb render --side top|bottom --zoom 1.6 --width W --height H --background opaque`
  is the quickest visual check; `sch export pdf` + `pdftoppm -r 300 -png -x -y -W -H` for crops.
- SPI-to-LED specifics recorded in `boards/chromatone/isolator/README.md` (SK9822 has no VIH spec, only
  VDD+0.3 V abs max; ISO7720 is 2/0, fail-safe high, PWD up to 5.9 ns; start at 8 MHz).
- `Schematic.label(name, x, y, rot)` writes local labels; KiCad justifies them `left bottom` for
  rot 0/90 and `right bottom` for 180/270, so the text always extends away from the wire end.
  Wiring big parts (RP2040) block-by-block with labels is far cleaner than direct wires.
- Property (Reference/Value) text is centre-justified at its `at`, and its angle is relative to
  the symbol (schgen's default `rot % 180` keeps it horizontal; do not force 0 on rotated parts).
  Offsets of 3+ mm keep values clear of bodies and of `Device:C` plates.
- Stacked pins (RP2040 IOVDD 1/10/22/33/42/49, DVDD 23/50) share one position; one wire end
  connects them all, and a `no_connect` on any of them ties the flag to the whole net.
- **KiCad 10 design variants** live per symbol instance:
  `(instances (project "x" (path "/uuid" (reference "U3") (unit 1) (variant (name "vib") (dnp yes)))))`,
  with `dnp`, `in_bom`, `on_board`, `in_pos_files`, `exclude_from_sim` and `(field (name) (value))`
  overrides; only differences from the base symbol matter and the variant name set is collected
  from these entries (no project-file registry needed). `schgen.place(variants={...}, dnp=...)`
  writes them; `kicad-cli sch export bom --variant vib` / `pcb export pos --variant vib` apply them
  (`${VARIANT}` in `-o` for several at once). The jobset exports the default variant only.
- `kicad-cli pcb drc --schematic-parity` on a PCB with no footprints reports zero parity issues,
  so `make check` passes for a board whose layout has not started.
- **QFN-56 0.4 mm pitch with 0.2/0.2 rules and 0.6 mm vias (boards/net/node):** a via between
  two tracks needs their centres 1.2 mm apart (0.6 mm to each), so only a pin whose neighbours
  are unrouted can via near the chip and adjacent pins must escape
  straight on the front first; parallel 45 deg escapes from adjacent pins are only 0.28 mm apart
  (violation), so stagger them (one straight, one diagonal). Adjacent same-net pins (RP2040
  43+44, 48+49) can be joined at the pad tips to free a lane. A 0603 in line with a 0.4 mm pin
  is impossible (its pad is 0.95 mm wide). Decision taken: the node board is 4-layer (In1 GND,
  In2 +3V3); `pcbgen.Board(copper_layers=4)`.
- pcbgen (2026-09-20): `copper_layers` (idempotent: InN.Cu entries are rebuilt, so a generator
  may read its own output), zone `priority` and per-zone `thermal_gap`/`thermal_bridge`,
  keepouts on `*.Cu`, `boards:` footprints from `lib/footprints/boards.pretty`, the netlist's
  dnp/exclude flags copied into `attr` (added when the library footprint has no `attr`),
  per-variant overrides written as KiCad 10 `(variants ...)` on the board and `(variant (name)
  (dnp yes) ...)` on the footprint (parsed from the netlist's `(variants ...)` per component; the
  board-side syntax came from `pcb_io_kicad_sexpr_parser.cpp`), `solid_pads=` for pads that must
  connect to pours without thermal spokes, and empty fields (`(field (name "LCSC"))` with no
  value) emitted as empty properties so schematic parity passes; the board-level `(variants ...)`
  registry is rebuilt each run like the inner layers. `sch export bom --exclude-dnp --variant x`
  honours the variant (verified 2026-09-21: `vib` keeps SW1/C22, drops U3/C20/C21).
- **Routing at 0.4 mm pitch, learned on boards/net/node (DRC-verified on that board):** an
  escape that bends *towards* a routed neighbour must first run straight for >= 0.2 mm or it
  clips that neighbour's pad (bending away, or beside an unrouted pad, needs nothing); two
  neighbours bending 45 deg the same way need bend points offset >= 0.17 mm along the row (the
  pin nearer the bend direction bends first) or >= 0.97 mm the other way (parallel 45 deg lines
  offset (a, b) are |a - b| / sqrt 2 apart); a via needs 0.6 mm from every other track centre
  and 0.8 mm from other vias, so rows of parallel tracks must be >= 1.2 mm apart for a via to
  sit between them; a via connects to a pad only if their copper overlaps or a track joins them
  (a 0.3 mm gap is an open, a via inside a bare pogo pad is fine); the U1 pin whose two neighbours are unrouted is the only one that can via straight out,
  which is why GPIO7..9 are unused on the node. `R_0603` pads sit at +-0.825 mm, `C_0603` at
  +-0.775, both 0.95 across the short axis; rot 180 puts pad 1 on the right, rot 90 puts it at
  +y (below), rot 270 above. `ref_pos`/`val_pos` offsets rotate with the footprint. Vias may sit
  inside pogo/test pads. A B.Cu ring around M2 keepouts needs square notches at >= hole + 3.6
  mm; leaving one corner open costs two `track_dangling` warnings and frees the corner. Pad
  dicts returned by `footprint()` beat hand-derived pad coordinates (D2's WS2812 pads and every
  resistor were initially wrong).
- **Fan-out pattern that works:** pin k of a group bends at a staggered point, then all turn
  onto parallel rows/columns at 0.7 mm (tracks only) or 1.2 mm (vias between) pitch; give each
  row its own destination and put pull-ups *on* the run (pad 2 centred on the track, pad 1
  hanging off to a via). A via field for a bundle: stagger vias on alternate rows.
- **KiCad without a system install:** `flatpak install --user flathub org.kicad.KiCad` (10.0.6,
  ~600 MB) plus the `org.kicad.KiCad.Library.{Symbols,Footprints}` extensions; a wrapper
  `~/.local/bin/kicad-cli` running `flatpak run --user --command=kicad-cli --filesystem=host
  org.kicad.KiCad "$@"`, the global `sym-lib-table`/`fp-lib-table` copied from the extensions'
  `template/` dirs into `~/.var/app/org.kicad.KiCad/config/kicad/10.0/` (otherwise ERC reports
  every library missing), and `KICAD_SYMBOL_DIR` / `KICAD_FOOTPRINT_DIR` pointing at
  `~/.local/share/flatpak/runtime/org.kicad.KiCad.Library.*/x86_64/stable/active/files/{symbols,footprints}`
  for schgen/pcbgen. Output paths must be under `$HOME` (`/tmp` is not shared).
- `boardtools.kicadlibs.find()` locates the stock libraries (env var, `/usr/share/kicad`, then the
  flatpak runtimes' `active` deployment), so `KICAD_SYMBOL_DIR`/`KICAD_FOOTPRINT_DIR` are optional.
- `scripts/smoke.sh` makes its temp copy under `$HOME` (`${TMPDIR:-$HOME/.cache}`) so the flatpak
  `kicad-cli` can read it; an older `mktemp -d` in /tmp failed with "Unable to open boards/smoke-a/...".
- pcbgen (2026-09-21, boards/chromatone/hat): `footprint(side='B')` flips a footprint the way
  KiCad does (local y of pads/text/graphics negated, F/B layers swapped, text `justify mirror`,
  pad angle `rot - a`; verified against the KiCad HAT template: socket at (8.37, 4.77) rot 270
  puts pin 3 at +x). `gr_arc()` and `outline_rect(radius=)`; arc midpoints must be written with
  >= 5 decimals or DRC reports an open/self-intersecting outline. `Board()` now also drops
  `gr_arc/gr_circle/gr_poly` from the template (a generator reading its own output accumulated
  arcs). Library `attr` tokens other than the netlist-driven bom/pos/dnp flags are kept
  (`allow_soldermask_bridges` on solder jumpers).
- **Reusing a routed board inside a bigger one works** by transforming every literal through a
  helper (`T(x, y)`, rotation added to footprints) and tagging pad tuples (a `tuple` subclass)
  so the segment helper transforms only literals; the pad dicts come back in the new frame.
  `boards/chromatone/hat/generate/pcb.py` does this for the dac (90 deg) and isolator (180 deg).
- **HAT header escapes decide the floorplan.** Every north-south corridor from the 40-pin
  header crosses the I2S/SPI/5V escapes unless blocks sit under their own pins: BCK (pin 12)
  runs east on the back under the socket, 5V (pin 4) goes down the back, everything else on
  the front; a header link (pins 1+17) on the back isolates GND pads' pour slivers (solid
  connect + stub via). A 3.5 mm jack cannot face the Pi's USB end (the USB stack rises ~3 mm
  above the HAT top).
- `*.net` is git-ignored: PCB generators need the netlist exported first (command in each
  `generate/README.md`).
- The DRC loop that worked: a script that regenerates, runs `kicad-cli pcb drc
  --severity-error --severity-warning --schematic-parity --refill-zones`, and prints the
  report's `[type]` lines with `@(x, y)` converted to board-local mm; then a bounding-box
  courtyard checker (parse `F.CrtYd`, transform by `at`) for placement passes.

## Review history

Seven Codex critique loops so far (five rounds on the original scaffold, three on the jobset
restructure, one on the net/node placement and pcbgen changes, one on the routed net/node board
(C11 away from its pin, crystal loop length, USB series R placement, paste on pogo pads,
variants registry not idempotent, overstated escape rules; all addressed, re-check round still
owed), two rounds on chromatone/hat (no electrical or layout finding; holes/test points needed
`in_pos_files=False` to stay out of the CPL, socket is the only back-side THT part so JLCPCB
Standard assembly or hand-soldering), three on the chromatone board: JST LCSC number was the 3-pin part, decoupling
loop length, hole keepouts, ground test pads, clock margin, Description into the BOM). Findings that shaped the current design: fab must purge, then check, then export
(ordered under `-j`); zone refill; strict severity flags; whitespace/quote-proof layer parsing;
every copper layer in the fab zip (the In1..In4 cap bit an 8-layer board); warnings reports
with schematic parity; Manufacturer in BOM grouping; CSV header validation independent of row
count; CI uploading reports on failure; a smoke test with hostile fixtures and a
good-build-then-failure case. Assume any change to gating, paths, or the jobset needs a
reproduction-based re-check, not a read-through.

## Ideas not yet implemented (ranked by Codex, agreed)

1. Checked, archived order bundle with a manifest (rev, commit, KiCad version, hashes).
2. BOM/CPL lint: cross-check factory-assembled BOM subset against the CPL; assembly policy field.
3. Per-fab constraint profiles (`.kicad_dru`) and an order spec.
4. Interactive HTML BOM replacement (iBOM itself is SWIG-based) built on `boardtools.sexpr`.
5. Assembly drawings (`pcb_export_pdf` job with F.Fab/F.SilkS/Edge.Cuts) and SVG-based revision diffs.
6. Panelization (KiKit is SWIG-based; no `kicad-cli` equivalent yet).
7. Board revision in PCB markings and output filenames (currently schematic title block only).
8. `schgen`: hierarchical sheets and buses (labels exist; all boards are still single-sheet).
9. Per-variant jobset outputs (`variant_names` in the BOM/pos jobs) so `make jlcpcb` can build
   the `vib`/`bare` variants of `boards/net/node` instead of the hand-run `--variant` commands.
