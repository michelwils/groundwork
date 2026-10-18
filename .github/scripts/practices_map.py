"""The map of the practices and the numbers of the ADRs that a source reserves (ADR 0001).

`parse` reads the map, `docs/practices.md`: the entries with what each ADR needs, its files and its
shared lines, the shared files and the files that are not part of a practice. `needs_of` and `owners`
turn the entries into the needs of each ADR and the ADR that owns each file, and `closure` follows the
needs in turn.

A source reserves the range `0001` to `0999`, and the ranges that it declares in `.groundwork-ranges`,
one `NNNN-NNNN` per line (ADR 0001). `read_ranges` returns them, with what is wrong in the file.
"""

import os
import re

MAP = "docs/practices.md"
BASE = (1, 999)
RANGES_FILE = ".groundwork-ranges"
ADR_DIRECTORY = "docs/adr"
ADR_FILE = re.compile(r"^([0-9]{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
RANGE = re.compile(r"^([0-9]{4})-([0-9]{4})$")
HEADING = re.compile(r"^### (\d{4})\. \S")
PATH = re.compile(r"`([^`]+)`")
LIST_ITEM = re.compile(r"^  - (.+)$")
REFERENCE = re.compile(r"^ADR (\d{4})$")
SECTIONS = {"## Practices": "practices", "## Shared files": "shared", "## Not part of a practice": "apart"}


def parse(lines):
    """Return the entries, the shared files and the files that are not part of a practice.

    An entry is a dict with its number, its line and the (value, line) of what it holds."""
    entries, shared, apart = [], [], []
    section = list_name = entry = None
    for number, line in enumerate(lines, start=1):
        line = line.rstrip("\r")
        if line in SECTIONS:
            section, entry, list_name = SECTIONS[line], None, None
        elif line.startswith("## "):
            section, entry, list_name = None, None, None
        elif HEADING.match(line):
            entry = {"number": int(HEADING.match(line).group(1)), "line": number, "needs": None, "files": [], "shared": []}
            entries.append(entry)
            list_name = None
        elif entry is not None and line.startswith("- "):
            head, _, value = line[2:].partition(":")
            list_name = {"Files": "files", "Shared lines": "shared"}.get(head)
            if head == "Needs":
                entry["needs"] = (value.strip(), number)
        elif entry is not None and list_name and LIST_ITEM.match(line):
            item = LIST_ITEM.match(line).group(1)
            path = PATH.match(item)
            if path:
                entry[list_name].append((path.group(1), number))
        elif section in ("shared", "apart") and line.startswith("- "):
            path = PATH.match(line[2:])
            if path:
                (shared if section == "shared" else apart).append((path.group(1), number))
    return entries, shared, apart


def references(value):
    """Return the numbers of the ADRs named by a value, and the parts that are not an ADR."""
    if value == "none":
        return [], []
    found, wrong = [], []
    for part in (part.strip() for part in value.split(",")):
        match = REFERENCE.match(part)
        (found if match else wrong).append(int(match.group(1)) if match else part)
    return found, wrong


def cycles(needs):
    """Return the numbers of the ADRs that are on a cycle of needs."""
    found = set()
    for start in needs:
        stack, seen = list(needs[start]), set()
        while stack:
            current = stack.pop()
            if current == start:
                found.add(start)
                break
            if current not in seen:
                seen.add(current)
                stack.extend(needs.get(current, []))
    return sorted(found)


def read_map(root):
    """Return what `parse` returns for the map under the root, or nothing for each if it does not exist."""
    path = os.path.join(root, MAP)
    if not os.path.isfile(path):
        return [], [], []
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        return parse(handle.read().split("\n"))


def needs_of(entries):
    """Return the numbers of the ADRs that each ADR needs, for the entries that have a line 'Needs'."""
    return {entry["number"]: set(references(entry["needs"][0])[0]) for entry in entries if entry["needs"] is not None}


def owners(entries):
    """Return the number of the ADR whose entry lists each file."""
    return {path: entry["number"] for entry in entries for path, _ in entry["files"]}


def closure(numbers, needs):
    """Return the numbers with the ADRs that they need, and those in turn."""
    found, stack = set(), list(numbers)
    while stack:
        current = stack.pop()
        if current not in found:
            found.add(current)
            stack.extend(needs.get(current, ()))
    return found


def is_reserved(number, reserved):
    return any(start <= number <= end for start, end in reserved)


def read_ranges(root):
    """Return the ranges that the source reserves, sorted, and the problems of the file as (line, message).

    The base comes first. A line of `.groundwork-ranges` that is refused adds no range."""
    reserved, problems = [BASE], []
    path = os.path.join(root, RANGES_FILE)
    if os.path.isfile(path):
        with open(path, "rb") as handle:
            lines = handle.read().decode("utf-8-sig", errors="replace").split("\n")
        for number, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = RANGE.match(line)
            if not match:
                problems.append((number, f"'{line}' is not a range such as 9000-9999, a comment or a blank line"))
                continue
            start, end = int(match.group(1)), int(match.group(2))
            if start > end:
                problems.append((number, f"the first bound of the range {line} is above the second"))
            elif start <= BASE[1]:
                problems.append((number, f"the range {line} overlaps {BASE[0]:04d}-{BASE[1]:04d}, which groundwork reserves"))
            elif any(start <= other_end and other_start <= end for other_start, other_end in reserved):
                problems.append((number, f"the range {line} overlaps another range"))
            else:
                reserved.append((start, end))
    return sorted(reserved), problems
