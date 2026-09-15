# Shared libraries

Every board's project library tables point here under the nickname `boards`.

- `symbols/boards.kicad_sym` — shared schematic symbols
- `footprints/boards.pretty/` — shared footprints (one `.kicad_mod` per footprint)
- `3d/` — STEP/WRL models; reference them from footprints as `${KIPRJMOD}/../../lib/3d/<file>`

Keep parts that come from KiCad's stock libraries out of here; only add custom or modified parts.
