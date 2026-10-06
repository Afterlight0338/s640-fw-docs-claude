#!/usr/bin/env python3
"""Render docs/src/*.md (joined in name order) into README.md.

Placeholders (each on its own line):
  {{lst NAME START END}}   lines of asm/NAME.lst with START <= address < END (hex), fenced
  {{file PATH}}            the file, verbatim
Listing excerpts are copied from the generated files, never typed by hand.
"""
import pathlib, re

root = pathlib.Path(__file__).resolve().parent.parent
src = "\n".join(p.read_text() for p in sorted((root / "docs/src").glob("*.md")))


def lst(name, start, end):
    s, e = int(start, 16), int(end, 16)
    out = []
    for line in (root / f"asm/{name}.lst").read_text().splitlines():
        m = re.match(r"([0-9a-f]{8}):", line)
        if m and s <= int(m.group(1), 16) < e:
            out.append(line)
    if not out:
        raise SystemExit(f"empty excerpt: {name} {start} {end}")
    return "\n".join(out)


def render(line):
    m = re.fullmatch(r"\{\{lst (\S+) (\S+) (\S+)\}\}", line.strip())
    if m:
        return "```\n" + lst(*m.groups()) + "\n```"
    m = re.fullmatch(r"\{\{file (\S+)\}\}", line.strip())
    if m:
        return (root / m.group(1)).read_text().rstrip("\n")
    return line


def link_paths(line):
    """`path` -> [`path`](path) when the path exists in this repository."""
    def sub(m):
        path = m.group(1)
        return f"[`{path}`]({path})" if (root / path).exists() and "/" in path else m.group(0)
    return re.sub(r"(?<!\[)`([A-Za-z0-9_./-]+)`(?!\])", sub, line)


out, fenced = [], False
for line in src.splitlines():
    if line.strip().startswith("```"):
        fenced = not fenced
        out.append(line)
        continue
    rendered = render(line)
    out.append(rendered if fenced or rendered != line else link_paths(line))
(root / "README.md").write_text("\n".join(out) + "\n")
print("README.md written")
