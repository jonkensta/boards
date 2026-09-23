#!/usr/bin/env bash
# Smoke-test the scaffolder and export pipeline without touching boards/ or out/.
# Copies the repo into a temp dir, scaffolds two boards (the second at a nested id
# and converted to eight copper layers with hostile layer names/text), checks UUID handling and placeholder
# substitution, runs `make fab` and `make jlcpcb` on both, and verifies the
# outputs, then `make parts` against a local fixture catalog (no network).
# Needs bash, python3, kicad-cli, unzip, make.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

fail() { echo "smoke: FAIL: $*" >&2; exit 1; }
for tool in python3 kicad-cli unzip make; do
  command -v "$tool" >/dev/null || fail "missing tool: $tool"
done

cp -r "$root/Makefile" "$root/scripts" "$root/templates" "$root/lib" "$root/jobsets" "$root/boardtools" "$tmp/"
mkdir -p "$tmp/boards"
cd "$tmp"

make --no-print-directory new NAME=smoke-a >/dev/null
make --no-print-directory new NAME=nest/deeper/smoke-b >/dev/null   # nested board id

# --- scaffolder -------------------------------------------------------------
A=smoke-a; B=nest/deeper/smoke-b
for b in $A $B; do
  leaf=$(basename "$b")
  for ext in kicad_pro kicad_sch kicad_pcb; do
    [ -f "boards/$b/$leaf.$ext" ] || fail "missing boards/$b/$leaf.$ext"
  done
  grep -rq '{{NAME}}\|{{LIBREL}}' "boards/$b" && fail "unsubstituted placeholder in boards/$b"
  sch_uuid=$(grep -oE '\(uuid "[0-9a-f-]{36}"\)' "boards/$b/$leaf.kicad_sch" | head -1 | grep -oE '[0-9a-f-]{36}')
  [ -n "$sch_uuid" ] || fail "$b: no uuid in schematic"
  grep -q "\"$sch_uuid\"" "boards/$b/$leaf.kicad_pro" || fail "$b: .kicad_pro sheet uuid != schematic uuid"
  # the lib tables must resolve to the repo's lib/ from this board's directory
  rel=$(grep -oE 'KIPRJMOD}/[^"]*lib' "boards/$b/sym-lib-table" | head -1 | sed 's|.*KIPRJMOD}/||')
  [ -d "boards/$b/$rel" ] && [ -f "boards/$b/$rel/symbols/boards.kicad_sym" ] || fail "$b: lib table path '$rel' does not reach lib/"
done
uuids_a=$(grep -ohE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' boards/$A/* | sort -u)
uuids_b=$(grep -ohE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' boards/$B/* | sort -u)
[ -z "$(comm -12 <(echo "$uuids_a") <(echo "$uuids_b"))" ] || fail "boards share UUIDs"
grep -q 'templates/board' boards/$A/sym-lib-table && fail "lib table still points at template"
[ "$(make --no-print-directory list | paste -sd' ')" = "$B $A" ] || fail "make list: got '$(make --no-print-directory list | paste -sd' ')'"

# --- smoke-b: eight copper layers, space-indented, hostile names/text ------------------
pcb_b=boards/$B/smoke-b.kicad_pcb
sed -i 's/^\(\s*\)(0 "F.Cu" signal)$/\1(0 "F.Cu" signal "Top copper )")\n\1(4 "In1.Cu" signal)\n\1(6 "In2.Cu" signal)\n\1(8 "In3.Cu" signal)\n\1(10 "In4.Cu" signal)\n\1(12 "In5.Cu" signal)\n\1(14 "In6.Cu" signal)/' "$pcb_b"
sed -i 's/^\(\s*\)(paper "A4")$/\1(paper "A4")\n\1(title_block (title "Notes: (layers are listed below) \\"quoted\\"") (rev "B"))/' "$pcb_b"
sed -i 's/\t/  /g' "$pcb_b"
python3 - "$pcb_b" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read().rstrip()
assert s.endswith(")")
items = "".join(f'  (gr_text "{t}" (at {x} 55) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n'
                for t, x in (("(", 60), (")", 62), ('a \\"quoted\\" (legend)', 70)))
open(p, "w").write(s[:-1] + items + ")\n")
PY
[ "$(python3 -m boardtools layers "$pcb_b")" = "F.Cu,In1.Cu,In2.Cu,In3.Cu,In4.Cu,In5.Cu,In6.Cu,B.Cu" ] || fail "boardtools layers on 8-layer board"
python3 -m boardtools info "$pcb_b" | grep -q '^rev: B$' || fail "boardtools info rev"

# --- pipeline ---------------------------------------------------------------
for b in $A $B; do
  leaf=$(basename "$b"); out=boards/$b/out
  make --no-print-directory -j4 jlcpcb BOARD=$b >"$tmp/fab-$leaf.log" 2>&1 || { cat "$tmp/fab-$leaf.log"; fail "make jlcpcb BOARD=$b"; }
  grep -q 'erc-warnings.rpt' "$tmp/fab-$leaf.log" || fail "$b: Makefile checks did not run before the jobset"
  for f in erc.rpt drc.rpt erc-warnings.rpt drc-warnings.rpt $leaf-gerbers.zip $leaf-all-pos.csv $leaf-bom.csv $leaf-schematic.pdf $leaf.step \
           $leaf-job.gbrjob $leaf-Edge_Cuts.gm1 drill/$leaf-PTH.drl drill/$leaf-NPTH.drl drill/$leaf-PTH-drl_map.gbr \
           jlcpcb/$leaf-cpl.csv jlcpcb/$leaf-bom.csv; do
    [ -s "$out/$f" ] || fail "$b: missing or empty $out/$f"
  done
  # KiCad names gerbers after the user layer name, so match copper by extension (gtl/gbl = F.Cu/B.Cu)
  for ext in gtl gbl; do ls $out/*.$ext >/dev/null 2>&1 || fail "$b: no .$ext copper gerber"; done
  listing=$(unzip -Z1 "$out/$leaf-gerbers.zip") || fail "$b: cannot list gerber zip"
  for f in $out/*.g?? $out/*.g? $out/*.gbrjob $out/drill/*.drl; do
    [ -e "$f" ] || continue
    grep -qE "(^|/)$(basename "$f")$" <<<"$listing" || fail "$b: $(basename "$f") missing from gerber zip"
  done
  grep -q 'drl_map' <<<"$listing" && fail "$b: drill maps leaked into gerber zip"
  head -1 "$out/jlcpcb/$leaf-cpl.csv" | grep -qx 'Designator,Mid X,Mid Y,Rotation,Layer' || fail "$b: JLCPCB CPL header"
  head -1 "$out/jlcpcb/$leaf-bom.csv" | grep -qx 'Comment,Designator,Footprint,LCSC Part #' || fail "$b: JLCPCB BOM header"
done
outb=boards/$B/out
for i in 1 2 3 4 5 6; do
  [ -s "$outb/smoke-b-In${i}_Cu.g$i" ] || fail "8-layer board: missing inner layer gerber In${i}_Cu.g$i"
  grep -q "smoke-b-In${i}_Cu.g$i" <<<"$(unzip -Z1 $outb/smoke-b-gerbers.zip)" || fail "8-layer board: In${i}.Cu missing from zip"
done

# --- parts: checks the BOM fab left in out/ against a local fixture catalog (no network)
python3 -c 'import sqlite3, sys; sqlite3.connect(sys.argv[1]).execute("CREATE TABLE jlc_components (lcsc INTEGER PRIMARY KEY, mfr, manufacturer, package, library_type, preferred, stock)")' "$tmp/parts.sqlite3"
parts_db="--db $tmp/parts.sqlite3"
make --no-print-directory parts BOARD=$A PARTS_ARGS="$parts_db" >"$tmp/parts.log" 2>&1 || { cat "$tmp/parts.log"; fail "make parts BOARD=$A"; }
grep -q '^0 BOM lines: 0 error' "$tmp/parts.log" || fail "make parts summary: $(tail -1 "$tmp/parts.log")"
# the BOM must be newer than every input: schematics, the project (text variables), the jobset
for input in boards/$A/smoke-a.kicad_pro jobsets/fab.kicad_jobset boards/$A/smoke-a.kicad_sch; do
  touch -d '+2 seconds' "$input"
  make --no-print-directory parts BOARD=$A PARTS_ARGS="$parts_db" >"$tmp/parts.log" 2>&1 && fail "make parts accepted a BOM older than $input"
  grep -q "is stale.*$input" "$tmp/parts.log" || fail "make parts: expected stale-BOM message for $input"
  touch -d '-1 hour' "$input"
done
make --no-print-directory parts BOARD=$A PARTS_ARGS="$parts_db" >/dev/null 2>&1 || fail "make parts after restoring input mtimes"
mv boards/$A/smoke-a.kicad_sch "$tmp/"
make --no-print-directory parts BOARD=$A PARTS_ARGS="$parts_db" >/dev/null 2>&1 && fail "make parts passed without a schematic"
mv "$tmp/smoke-a.kicad_sch" boards/$A/

# --- gating: after a good build, a DRC failure must stop fab before the jobset runs
# and must not leave the previous zip looking current
sed -i 's/^\(\s*\)(gr_text "(" /\1(segment (start 60 60) (end 70 60) (width 0.1) (layer "F.Cu") (net 0))\n\1(gr_text "(" /' "$pcb_b"
[ -s $outb/smoke-b-gerbers.zip ] || fail "precondition: previous good zip missing"
if make --no-print-directory -j4 fab BOARD=$B >"$tmp/fail.log" 2>&1; then fail "fab succeeded on a board with a DRC error"; fi
[ ! -e $outb/smoke-b-gerbers.zip ] || fail "stale gerber zip survived a failed check"
[ ! -e $outb/smoke-b.step ] || fail "stale STEP survived a failed check"
grep -q 'track_width' $outb/drc.rpt || fail "expected track_width violation in drc.rpt"
# the full jobset alone (make export, like GUI "run all") must not write a BOM past the failed DRC
if make --no-print-directory export BOARD=$B >"$tmp/fail-export.log" 2>&1; then fail "export succeeded on a board with a DRC error"; fi
[ ! -e $outb/smoke-b-bom.csv ] || fail "full jobset wrote a BOM despite the failed DRC"
make --no-print-directory parts BOARD=$B PARTS_ARGS="$parts_db" >/dev/null 2>&1 && fail "make parts ran without a BOM"
make --no-print-directory fab BOARD=does/not/exist >/dev/null 2>&1 && fail "fab on a missing board id must fail"

echo "smoke: OK"
