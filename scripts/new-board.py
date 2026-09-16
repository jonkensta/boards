#!/usr/bin/env python3
"""Create a new KiCad board project under boards/<id>/ from templates/board/.

Usage: scripts/new-board.py <id>          e.g. blinky  or  chromatone/isolator

<id> is a path relative to boards/; each component is letters, digits, '-' or
'_'. The project files are named after the last component (the leaf). Every
template file is copied, `board.` file stems are renamed to `<leaf>.`, `{{NAME}}`
becomes the leaf, `{{LIBREL}}` becomes the relative path from the project dir to
the repo's shared lib/, and all UUIDs are regenerated so two boards never share
identifiers.
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
PART_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in {"-h", "--help"}:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    board_id = argv[1].strip("/")
    parts = board_id.split("/")
    if not parts or not all(PART_RE.match(p) for p in parts):
        print(f"error: invalid board id {argv[1]!r}", file=sys.stderr)
        return 2
    name = parts[-1]
    dest = BOARDS.joinpath(*parts)
    librel = "/".join([".."] * (len(parts) + 1)) + "/lib"   # boards/<parts...>/ -> repo root
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
        text = text.replace("{{NAME}}", name).replace("{{LIBREL}}", librel)
        text = UUID_RE.sub(swap, text)
        out.write_text(text, encoding="utf-8")
        print(f"  {out.relative_to(ROOT)}")

    print(f"\ncreated boards/{board_id}; open with: kicad boards/{board_id}/{name}.kicad_pro")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
