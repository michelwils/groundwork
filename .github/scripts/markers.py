"""Blocks of lines per ADR, in the files that several ADRs share.

A block starts with a marker line and ends with a closing marker line:

    <!-- groundwork:0010 -->   …   <!-- /groundwork -->     in Markdown
    # groundwork:0010          …   # /groundwork            in YAML

The markers are alone on their line, and their indentation is free. A block holds the lines of one
ADR, and blocks are neither nested nor split. A Markdown marker in a code block is not read.

`parse` reads the blocks and reports what is wrong with the markers. `remove` takes out the blocks of
the ADRs that a project did not keep, with their markers, and leaves no blank line in excess.
"""

import re

PATTERNS = {
    "markdown": (re.compile(r"^[ \t]*<!-- groundwork:(\d{4}) -->[ \t]*$"), re.compile(r"^[ \t]*<!-- /groundwork -->[ \t]*$")),
    "yaml": (re.compile(r"^[ \t]*# groundwork:(\d{4})[ \t]*$"), re.compile(r"^[ \t]*# /groundwork[ \t]*$")),
}
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def kind(path):
    """Return the syntax of the markers of a file, from its extension, or None."""
    if path.endswith(".md"):
        return "markdown"
    if path.endswith((".yml", ".yaml")):
        return "yaml"
    return None


def parse(lines, syntax):
    """Return the blocks and the problems of the lines.

    A block is a dict with its ADR number and the numbers, from 1, of its first and last lines.
    A problem is a (line, message)."""
    opening, closing = PATTERNS[syntax]
    blocks, problems = [], []
    current = fence = None
    for number, line in enumerate(lines, start=1):
        line = line.rstrip("\r")
        if syntax == "markdown":
            if fence:
                if line.strip() and set(line.strip()) == {fence[0]} and len(line.strip()) >= len(fence):
                    fence = None
                continue
            if FENCE.match(line):
                fence = FENCE.match(line).group(1)
                continue
        start = opening.match(line)
        if start:
            if current:
                problems.append((number, f"a block is opened inside the block of the ADR {current['adr']:04d} opened at line {current['start']}"))
                continue
            current = {"adr": int(start.group(1)), "start": number, "end": None}
        elif closing.match(line):
            if not current:
                problems.append((number, "a closing marker has no block to close"))
                continue
            current["end"] = number
            blocks.append(current)
            current = None
    if current:
        problems.append((current["start"], f"the block of the ADR {current['adr']:04d} is not closed"))
    return blocks, problems


def remove(text, syntax, kept):
    """Return the text without the blocks of the ADRs that are not kept.

    A blank line that follows a removed block goes with it when a blank line precedes it, and the
    blank lines at the end of the text that the removal leaves are taken out. The other blank lines
    stay. A text whose markers are wrong is refused with a ValueError."""
    ends_with_newline = text.endswith("\n")
    lines = text.split("\n")
    if ends_with_newline:
        lines.pop()
    blocks, problems = parse(lines, syntax)
    if problems:
        raise ValueError("; ".join(f"line {line}: {message}" for line, message in problems))
    dropped = {block["start"] - 1: block["end"] - 1 for block in blocks if block["adr"] not in kept}
    out, junction, index = [], False, 0
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
