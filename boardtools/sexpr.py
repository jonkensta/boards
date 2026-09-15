"""Minimal s-expression tokenizer/parser for KiCad files.

Quoted strings (with backslash escapes) are opaque atoms, so parentheses in
user text (silkscreen legends, layer names, titles) are never read as syntax.
"""

from __future__ import annotations

# Structural delimiters are sentinel objects so a quoted "(" or ")" atom can
# never be mistaken for syntax.
OPEN, CLOSE = object(), object()

Node = list  # a parsed element: [head_atom, *children], children are str | Node


class Quoted(str):
    """An atom that was written as a quoted string; `dumps` re-quotes it.

    Bare atoms (numbers, keywords) stay plain `str`. Round-tripping a file keeps
    each atom in its original form, and generated content can force quoting by
    wrapping a value in `Quoted(...)`.
    """


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
            yield Quoted("".join(buf))
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in "()\"":
                j += 1
            yield text[i:j]
            i = j


def parse(text: str) -> Node:
    """Parse a whole file and return its single root element."""
    stack: list[list] = [[]]
    for tok in tokenize(text):
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
    roots = [n for n in stack[0] if isinstance(n, list)]
    if len(roots) != 1:
        raise ValueError(f"expected one root element, found {len(roots)}")
    return roots[0]


def children(node: Node, head: str):
    """Yield child elements of `node` whose head atom is `head`."""
    for child in node[1:]:
        if isinstance(child, list) and child and child[0] == head:
            yield child


def child(node: Node, head: str) -> Node | None:
    return next(children(node, head), None)


def _atom(tok: str) -> str:
    if isinstance(tok, Quoted) or tok == "" or any(c.isspace() or c in '()"' for c in tok):
        return '"' + tok.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return tok


def dumps(node: Node, indent: int = 0, _inline: bool = False) -> str:
    """Serialize a node in KiCad's style: one element per line, tab-indented.

    Elements whose children are all atoms are written on one line, which matches
    how KiCad writes short elements such as `(at 10 20 90)` or `(uuid "...")`.
    """
    if not isinstance(node, list):
        return _atom(node)
    if all(not isinstance(c, list) for c in node):
        return "(" + " ".join(_atom(c) for c in node) + ")"
    pad = "\t" * (indent + 1)
    head = [_atom(c) for c in node[1:] if not isinstance(c, list)]
    # KiCad writes leading atoms on the head line, then nested elements.
    lines = ["(" + " ".join([_atom(node[0])] + head)]
    for c in node[1:]:
        if isinstance(c, list):
            lines.append(pad + dumps(c, indent + 1))
    return "\n".join(lines) + "\n" + "\t" * indent + ")"
