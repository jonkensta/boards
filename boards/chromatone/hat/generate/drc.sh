#!/bin/sh
# Regenerate the board and print DRC findings with board-local coordinates (origin 50, 50).
# Usage: generate/drc.sh [--no-parity]
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../../../.." && pwd)
cd "$root"
python3 boards/chromatone/hat/generate/pcb.py >/dev/null
parity=--schematic-parity
[ "$1" = "--no-parity" ] && parity=
mkdir -p boards/chromatone/hat/out
kicad-cli pcb drc --severity-error --severity-warning $parity --refill-zones --save-board \
  -o boards/chromatone/hat/out/drc.rpt boards/chromatone/hat/hat.kicad_pcb >/dev/null || true
python3 - boards/chromatone/hat/out/drc.rpt <<'EOF'
import re, sys
kind = None
for line in open(sys.argv[1]):
    m = re.match(r'\[(\w+)\]: (.*)', line)
    if m:
        kind = m.group(1); print(f'{kind}: {m.group(2)}')
        continue
    m = re.search(r'@\(([-\d.]+) mm, ([-\d.]+) mm\): (.*)', line)
    if m and kind:
        print(f'    ({float(m.group(1)) - 50:.3f}, {float(m.group(2)) - 50:.3f}) {m.group(3)}')
    if line.startswith(' ** Found') or line.startswith(' ** DRC'):
        print(line.rstrip())
EOF
