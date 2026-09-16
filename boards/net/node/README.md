# node

_Describe the board here: what it does, key parts, and revision notes._

## Files

- `node.kicad_pro` / `.kicad_sch` / `.kicad_pcb` — KiCad project
- `sym-lib-table` / `fp-lib-table` — project library tables pointing at the shared `lib/` in this repo

## Build

From the repo root:

```sh
make check BOARD=<id>   # ERC + DRC (id = this directory relative to boards/)
make fab   BOARD=node   # gerbers, drill, position, BOM, schematic PDF, STEP → out/node/
```
