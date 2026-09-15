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
- **Output root is `out/`** and is hardcoded in both the Makefile and the jobset destinations
  (`${KIPRJMOD}/../../out/${PROJECTNAME}`); a Make-only override would desynchronise them.
- **`boardtools/` is parse-only** (s-expressions, JSON, CSV). Anything that modifies a design
  goes through `kicad-cli` or the jobset.
- Run `make test && make smoke` before committing tooling changes. Smoke covers a 2-layer and a
  8-layer board with hostile layer names and silkscreen text, and a deliberate DRC failure.

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
- Make gotcha: pattern-rule targets (`erc-%`) must not be listed in `.PHONY`, or make skips the
  implicit-rule search and reports "Nothing to be done".

## Review history

The scaffold went through a five-round adversarial Codex critique loop. Findings that shaped the
current design: fab must depend on check (ordered under `-j`), zone refill, strict severity
flags, whitespace/quote-proof layer parsing, inner layers in the fab zip, warnings reports with
schematic parity, CI uploading reports on failure, and a smoke test with hostile fixtures.

## Ideas not yet implemented (ranked by Codex, agreed)

1. Checked, archived order bundle with a manifest (rev, commit, KiCad version, hashes).
2. BOM/CPL lint: cross-check factory-assembled BOM subset against the CPL; assembly policy field.
3. Per-fab constraint profiles (`.kicad_dru`) and an order spec.
4. Interactive HTML BOM replacement (iBOM itself is SWIG-based) built on `boardtools.sexpr`.
5. Assembly drawings (`pcb_export_pdf` job with F.Fab/F.SilkS/Edge.Cuts) and SVG-based revision diffs.
6. Panelization (KiKit is SWIG-based; no `kicad-cli` equivalent yet).
7. Board revision in PCB markings and output filenames (currently schematic title block only).
