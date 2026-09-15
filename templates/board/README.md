# {{NAME}}

_Describe the board here: what it does, key parts, and revision notes._

## Files

- `{{NAME}}.kicad_pro` / `.kicad_sch` / `.kicad_pcb` — KiCad project
- `sym-lib-table` / `fp-lib-table` — project library tables pointing at the shared `lib/` in this repo

## Build

From the repo root:

```sh
make check BOARD={{NAME}}   # ERC + DRC
make fab   BOARD={{NAME}}   # gerbers, drill, position, BOM, schematic PDF, STEP → out/{{NAME}}/
```
