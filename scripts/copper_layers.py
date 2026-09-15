#!/usr/bin/env python3
"""Print the comma-separated copper layer names from a .kicad_pcb layer table.

Tokenizes the s-expression properly (quoted strings with backslash escapes are
opaque), then reads the root-level `(layers ...)` element, so neither
indentation nor parentheses inside user-visible text can confuse it. Exits 1
(printing nothing) if no copper layers are found, so a Makefile recipe using
`$(python3 ...)` inside `&&` aborts instead of exporting a board with no copper.
"""

import re
import sys

COPPER = re.compile(r"^(?:F|B|In\d+)\.Cu$")

# Structural delimiters are distinct sentinel objects so a quoted "(" or ")"
# atom (e.g. silkscreen text) can never be mistaken for syntax.
OPEN, CLOSE = object(), object()


def tokenize(text: str):
    """Yield OPEN, CLOSE, or atom tokens (strings yielded unquoted)."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
        elif c in "()":
            yield OPEN if c == "(" else CLOSE
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    j += 1
                buf.append(text[j])
                j += 1
            yield "".join(buf)
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()\"":
                j += 1
            yield text[i:j]
            i = j


def parse(tokens):
    """Build nested lists from the token stream (first element = root list)."""
    stack = [[]]
    for tok in tokens:
        if tok is OPEN:
            stack.append([])
        elif tok is CLOSE:
            if len(stack) < 2:
                raise ValueError("unbalanced ')'")
            node = stack.pop()
            stack[-1].append(node)
        else:
            stack[-1].append(tok)
    if len(stack) != 1:
        raise ValueError("unbalanced '('")
    return stack[0]


def copper_layers(text: str) -> list[str]:
    root = parse(tokenize(text))
    if not root or not isinstance(root[0], list) or root[0][:1] != ["kicad_pcb"]:
        return []
    for node in root[0]:
        if isinstance(node, list) and node[:1] == ["layers"]:
            names = [e[1] for e in node[1:] if isinstance(e, list) and len(e) >= 2]
            return list(dict.fromkeys(n for n in names if COPPER.match(n)))
    return []


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: copper_layers.py <board.kicad_pcb>", file=sys.stderr)
        return 2
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            layers = copper_layers(f.read())
    except (OSError, ValueError) as e:
        print(f"error: {sys.argv[1]}: {e}", file=sys.stderr)
        return 1
    if not layers:
        print(f"error: no copper layers found in {sys.argv[1]}", file=sys.stderr)
        return 1
    print(",".join(layers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
