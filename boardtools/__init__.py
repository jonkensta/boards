"""Parse-only helpers for KiCad projects: no KiCad bindings, just file formats.

KiCad's SWIG `pcbnew` bindings are deprecated and removed in KiCad 11, and the
IPC API needs a running KiCad. Everything here reads the documented on-disk
formats directly (s-expressions for .kicad_pcb/.kicad_sch, JSON for
.kicad_pro, CSV for exports), so it keeps working across KiCad versions.
Anything that must *modify* a design goes through kicad-cli or a jobset.
"""
