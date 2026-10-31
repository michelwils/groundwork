"""Blocks of lines per ADR, in the files that several ADRs share.

A block starts with a marker line and ends with a closing marker line:

    <!-- groundwork:0010 -->   …   <!-- /groundwork -->     in Markdown
    # groundwork:0010          …   # /groundwork            in YAML

The block of the source is closed by its own marker, `<!-- /groundwork:source -->` or `# /groundwork:source`: a project
runs the scripts of its previous version on the files of the new one, and the patterns of those scripts, which
know no block of the source, must read both of its markers as ordinary text, or they refuse the file.

The markers are alone on their line, and their indentation is free. A block holds the lines of one
ADR, and blocks are neither nested nor split. A Markdown marker in a code block is not read.

A block can also be named `source`, as in `# groundwork:source` … `# /groundwork:source`: it holds lines that only a source of
ADRs needs, such as the entries of Dependabot for what the source owns. It is no ADR's, so `parse`
does not return it and the choice of the ADRs never takes it out. The update does not bring it to a
project, and a new project takes it out (`remove_source`).

`parse` reads the blocks and reports what is wrong with the markers. `remove` takes out the blocks of
the ADRs that a project did not keep, with their markers, and leaves no blank line in excess.
"""

from __future__ import annotations

import re
from collections.abc import Container
from typing import NamedTuple

PATTERNS = {
    "markdown": (
        re.compile(r"^[ \t]*<!-- groundwork:(\d{4}|source) -->[ \t]*$"),
        re.compile(r"^[ \t]*<!-- /groundwork(:source)? -->[ \t]*$"),
    ),
    "yaml": (
        re.compile(r"^[ \t]*# groundwork:(\d{4}|source)[ \t]*$"),
        re.compile(r"^[ \t]*# /groundwork(:source)?[ \t]*$"),
    ),
}
SOURCE = "source"
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


class Block(NamedTuple):
    """A block of the lines of an ADR: its number and the numbers, from 1, of its first and last lines."""

    adr: int
    start: int
    end: int


def kind(path: str) -> str | None:
    """Return the syntax of the markers of a file, from its extension, or None."""
    if path.endswith(".md"):
        return "markdown"
    if path.endswith((".yml", ".yaml")):
        return "yaml"
    return None


def label(opened: str) -> str:
    return "the source" if opened == SOURCE else f"the ADR {int(opened):04d}"


def scan(lines: list[str], syntax: str) -> tuple[list[Block], list[tuple[int, int]], list[tuple[int, str]]]:
    """Return the blocks of the ADRs, the first and last lines of the blocks of the source, and the problems."""
    opening, closing = PATTERNS[syntax]
    blocks, source, problems = [], [], []
    fence = None
    opened: str | None = None
    opened_at = 0
    for number, line in enumerate(lines, start=1):
        line = line.rstrip("\r")
        if syntax == "markdown":
            if fence:
                if line.strip() and set(line.strip()) == {fence[0]} and len(line.strip()) >= len(fence):
                    fence = None
                continue
            if fenced := FENCE.match(line):
                fence = fenced.group(1)
                continue
        start = opening.match(line)
        if start:
            if opened is not None:
                problems.append(
                    (number, f"a block is opened inside the block of {label(opened)} opened at line {opened_at}")
                )
                continue
            opened, opened_at = start.group(1), number
        elif ended := closing.match(line):
            if opened is None:
                problems.append((number, "a closing marker has no block to close"))
                continue
            if (ended.group(1) is not None) != (opened == SOURCE):
                problems.append(
                    (number, f"the block of {label(opened)} opened at line {opened_at} is closed by the wrong marker")
                )
                opened = None
                continue
            if opened == SOURCE:
                source.append((opened_at, number))
            else:
                blocks.append(Block(int(opened), opened_at, number))
            opened = None
    if opened is not None:
        problems.append((opened_at, f"the block of {label(opened)} is not closed"))
    return blocks, source, problems


def has_source(text: str, syntax: str) -> bool:
    """Tell whether the text has a block of the source."""
    return bool(scan(text.split("\n"), syntax)[1])


def parse(lines: list[str], syntax: str) -> tuple[list[Block], list[tuple[int, str]]]:
    """Return the blocks of the ADRs and the problems of the lines.

    A problem is a (line, message). The blocks of the source are checked, and not returned."""
    blocks, _, problems = scan(lines, syntax)
    return blocks, problems


def remove(text: str, syntax: str, kept: Container[int]) -> str:
    """Return the text without the blocks of the ADRs that are not kept.

    A blank line that follows a removed block goes with it when a blank line precedes it, and the
    blank lines at the end of the text that the removal leaves are taken out. The other blank lines
    stay. A text whose markers are wrong is refused with a ValueError."""
    return take_out(text, syntax, lambda blocks, source: [(b.start, b.end) for b in blocks if b.adr not in kept])


def remove_source(text: str, syntax: str) -> str:
    """Return the text without the blocks of the source, with the same care for the blank lines as `remove`."""
    return take_out(text, syntax, lambda blocks, source: source)


def take_out(text: str, syntax: str, chosen) -> str:
    """Return the text without the blocks that `chosen` returns, as (first line, last line), from the blocks of the
    ADRs and those of the source."""
    ends_with_newline = text.endswith("\n")
    lines = text.split("\n")
    if ends_with_newline:
        lines.pop()
    blocks, source, problems = scan(lines, syntax)
    if problems:
        raise ValueError("; ".join(f"line {line}: {message}" for line, message in problems))
    dropped = {start - 1: end - 1 for start, end in chosen(blocks, source)}
    out: list[str] = []
    junction, index = False, 0
    while index < len(lines):
        if index in dropped:
            index = dropped[index] + 1
            if index < len(lines) and not lines[index].strip() and (not out or not out[-1].strip()):
                index += 1
            junction = True
            continue
        line = lines[index]
        index += 1
        if junction and not line.strip() and (not out or not out[-1].strip()):
            continue
        out.append(line)
        junction = False
    if junction:
        while out and not out[-1].strip():
            out.pop()
    return "\n".join(out) + ("\n" if ends_with_newline and out else "")
