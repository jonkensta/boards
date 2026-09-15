#!/usr/bin/env bash
# Smoke-test the scaffolder and export pipeline without touching boards/ or out/.
# Copies the repo into a temp dir, scaffolds two boards (one converted to four
# layers), checks UUID handling and placeholder substitution, runs `make fab`
# on both, and verifies the outputs. Needs bash, python3, kicad-cli, zip, unzip.
set -euo pipefail

root=$(cd "$(dirname "$0")/.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

fail() { echo "smoke: FAIL: $*" >&2; exit 1; }
for tool in python3 kicad-cli zip unzip make; do
  command -v "$tool" >/dev/null || fail "missing tool: $tool"
done

cp -r "$root/Makefile" "$root/scripts" "$root/templates" "$root/lib" "$tmp/"
mkdir -p "$tmp/boards"
cd "$tmp"

make --no-print-directory new NAME=smoke-a >/dev/null
make --no-print-directory new NAME=smoke-b >/dev/null

# --- scaffolder -------------------------------------------------------------
for b in smoke-a smoke-b; do
  for ext in kicad_pro kicad_sch kicad_pcb; do
    [ -f "boards/$b/$b.$ext" ] || fail "missing boards/$b/$b.$ext"
  done
  grep -rq '{{NAME}}' "boards/$b" && fail "unsubstituted {{NAME}} in boards/$b"
  sch_uuid=$(grep -oE '\(uuid "[0-9a-f-]{36}"\)' "boards/$b/$b.kicad_sch" | head -1 | grep -oE '[0-9a-f-]{36}')
  [ -n "$sch_uuid" ] || fail "$b: no uuid in schematic"
  grep -q "\"$sch_uuid\"" "boards/$b/$b.kicad_pro" || fail "$b: .kicad_pro sheet uuid != schematic uuid"
done
uuids_a=$(grep -ohE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' boards/smoke-a/* | sort -u)
uuids_b=$(grep -ohE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' boards/smoke-b/* | sort -u)
[ -z "$(comm -12 <(echo "$uuids_a") <(echo "$uuids_b"))" ] || fail "boards share UUIDs"
grep -q 'templates/board' boards/smoke-a/sym-lib-table && fail "lib table still points at template"

# --- smoke-b: four layers, space-indented (layer parsing must not depend on tabs)
pcb_b=boards/smoke-b/smoke-b.kicad_pcb
sed -i 's/^\(\s*\)(0 "F.Cu" signal)$/\1(0 "F.Cu" signal)\n\1(4 "In1.Cu" signal)\n\1(6 "In2.Cu" signal)/' "$pcb_b"
sed -i 's/\t/  /g' "$pcb_b"
# user layer name containing a paren, and a title block mentioning "(layers": neither may confuse the parser
sed -i 's/^\(\s*\)(0 "F.Cu" signal)$/\1(0 "F.Cu" signal "Top copper )")/' "$pcb_b"
sed -i 's/^\(\s*\)(paper "A4")$/\1(paper "A4")\n\1(title_block (title "Notes: (layers are listed below) \\"quoted\\"") (rev "B"))/' "$pcb_b"
# standalone "(" and ")" silkscreen text (keyboard legends) must not be read as syntax
python3 - "$pcb_b" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read().rstrip()
assert s.endswith(")")
items = "".join(f'  (gr_text "{t}" (at {x} 55) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))\n' for t, x in (("(", 60), (")", 62), ('a \\"quoted\\" (legend)', 70)))
open(p, "w").write(s[:-1] + items + ")\n")
PY
[ "$(python3 scripts/copper_layers.py "$pcb_b")" = "F.Cu,In1.Cu,In2.Cu,B.Cu" ] || fail "copper_layers.py on 4-layer board"
python3 scripts/copper_layers.py /dev/null 2>/dev/null && fail "copper_layers.py must fail on a file with no layer table"

# --- pipeline ---------------------------------------------------------------
for b in smoke-a smoke-b; do
  make --no-print-directory -j4 fab BOARD=$b >"$tmp/fab-$b.log" 2>&1 || { cat "$tmp/fab-$b.log"; fail "make fab BOARD=$b"; }
  for f in erc.rpt drc.rpt erc-warnings.rpt drc-warnings.rpt $b-gerbers.zip $b-pos.csv $b-bom.csv $b-schematic.pdf $b.step \
           gerbers/$b-Edge_Cuts.gm1 drill/$b-PTH.drl drill/$b-NPTH.drl; do
    [ -s "out/$b/$f" ] || fail "$b: missing or empty out/$b/$f"
  done
  # KiCad names gerbers after the user layer name, so match by extension (gtl/gbl = F.Cu/B.Cu)
  for ext in gtl gbl; do
    ls out/$b/gerbers/*.$ext >/dev/null 2>&1 || fail "$b: no .$ext copper gerber"
  done
  listing=$(unzip -Z1 "out/$b/$b-gerbers.zip") || fail "$b: cannot list gerber zip"
  for f in out/$b/gerbers/* out/$b/drill/*.drl; do
    grep -qxF "$(basename "$f")" <<<"$listing" || fail "$b: $(basename "$f") missing from gerber zip"
  done
  grep -q 'drl_map' <<<"$listing" && fail "$b: drill maps leaked into gerber zip"
done
for f in In1_Cu.g1 In2_Cu.g2; do
  [ -s "out/smoke-b/gerbers/smoke-b-$f" ] || fail "4-layer board: missing inner layer gerber $f"
done

echo "smoke: OK"
