#!/usr/bin/env python3
"""Create a new KiCad board project under boards/<name>/ from templates/board/.

Usage: scripts/new-board.py <name>

The name must be a valid directory/file stem: letters, digits, '-' and '_'.
Every template file is copied, `board.` file stems are renamed to `<name>.`,
`{{NAME}}` placeholders are substituted, and all UUIDs are regenerated so two
boards never share identifiers.
"""

import re
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "board"
BOARDS = ROOT / "boards"

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in {"-h", "--help"}:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    name = argv[1]
    if not NAME_RE.match(name):
        print(f"error: invalid board name {name!r}", file=sys.stderr)
        return 2
    dest = BOARDS / name
    if dest.exists():
        print(f"error: {dest.relative_to(ROOT)} already exists", file=sys.stderr)
        return 1

    # Same template UUID -> same fresh UUID everywhere (the .kicad_pro sheet
    # list must match the root schematic's uuid).
    fresh: dict[str, str] = {}

    def swap(m: re.Match) -> str:
        return fresh.setdefault(m.group(0), str(uuid.uuid4()))

    dest.mkdir(parents=True)
    for src in sorted(TEMPLATE.rglob("*")):
        rel = src.relative_to(TEMPLATE)
        parts = list(rel.parts)
        parts[-1] = re.sub(r"^board(?=\.)", name, parts[-1])
        out = dest.joinpath(*parts)
        if src.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        try:
            text = src.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            shutil.copy2(src, out)
            continue
        text = text.replace("{{NAME}}", name)
        text = UUID_RE.sub(swap, text)
        out.write_text(text, encoding="utf-8")
        print(f"  {out.relative_to(ROOT)}")

    print(f"\ncreated boards/{name}; open with: kicad boards/{name}/{name}.kicad_pro")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
