"""Locate KiCad's stock symbol and footprint libraries.

`KICAD_SYMBOL_DIR` / `KICAD_FOOTPRINT_DIR` win when set. Otherwise the Debian/Arch
package path is tried, then the flatpak library runtimes (user, then system
install), preferring the `active` deployment.
"""

from __future__ import annotations

import glob
import os

_ENV = {"symbols": "KICAD_SYMBOL_DIR", "footprints": "KICAD_FOOTPRINT_DIR"}
_PKG = {"symbols": "Symbols", "footprints": "Footprints"}


def find(kind: str) -> str:
    """Directory holding `*.kicad_sym` (kind="symbols") or `*.pretty` (kind="footprints")."""
    env = os.environ.get(_ENV[kind])
    if env:
        return env
    cands = [f"/usr/share/kicad/{kind}"]
    for base in (os.path.expanduser("~/.local/share/flatpak"), "/var/lib/flatpak"):
        pat = f"{base}/runtime/org.kicad.KiCad.Library.{_PKG[kind]}/*/*/"
        cands += sorted(glob.glob(pat + f"active/files/{kind}"))
        cands += sorted(glob.glob(pat + f"*/files/{kind}"))
    for c in cands:
        if os.path.isdir(c):
            return c
    return cands[0]
