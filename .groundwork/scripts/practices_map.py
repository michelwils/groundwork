"""The map of the practices and the numbers of the ADRs that a source reserves (ADR 0001).

`parse` reads the map, `.groundwork/practices.md`: the entries with what each ADR needs, its files and its
shared lines, the shared files and the files that are not part of a practice. `needs_of` and `owners`
turn the entries into the needs of each ADR and the ADR that owns each file, and `closure` follows the
needs in turn.

A source reserves the range `0001` to `0999`, and the ranges that it declares in `.groundwork-ranges`,
one `NNNN-NNNN` per line (ADR 0001). `read_ranges` returns them, with what is wrong in the file.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import NamedTuple

MAP = ".groundwork/practices.md"
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


class Listed(NamedTuple):
    """A path that the map lists, and the line where it does."""

    path: str
    line: int


class Needs(NamedTuple):
    """The value of the line 'Needs' of an entry, as written, and the line where it is."""

    value: str
    line: int


@dataclass
class Entry:
    """The entry of an ADR in the map: its number, the line of its heading, its line 'Needs' if it has one, the
    files that it owns and the files whose lines it shares."""

    number: int
    line: int
    needs: Needs | None = None
    files: list[Listed] = field(default_factory=list)
    shared: list[Listed] = field(default_factory=list)


def parse(lines: list[str]) -> tuple[list[Entry], list[Listed], list[Listed]]:
    """Return the entries, the shared files and the files that are not part of a practice."""
    entries: list[Entry] = []
    shared: list[Listed] = []
    apart: list[Listed] = []
    section = list_name = entry = None
    for number, line in enumerate(lines, start=1):
        line = line.rstrip("\r")
        if line in SECTIONS:
            section, entry, list_name = SECTIONS[line], None, None
        elif line.startswith("## "):
            section, entry, list_name = None, None, None
        elif heading := HEADING.match(line):
            entry = Entry(number=int(heading.group(1)), line=number)
            entries.append(entry)
            list_name = None
        elif entry is not None and line.startswith("- "):
            head, _, value = line[2:].partition(":")
            list_name = {"Files": "files", "Shared lines": "shared"}.get(head)
            if head == "Needs":
                entry.needs = Needs(value.strip(), number)
        elif entry is not None and list_name and (listed := LIST_ITEM.match(line)):
            path = PATH.match(listed.group(1))
            if path:
                getattr(entry, list_name).append(Listed(path.group(1), number))
        elif section in ("shared", "apart") and line.startswith("- "):
            path = PATH.match(line[2:])
            if path:
                (shared if section == "shared" else apart).append(Listed(path.group(1), number))
    return entries, shared, apart


def references(value: str) -> tuple[list[int], list[str]]:
    """Return the numbers of the ADRs named by a value, and the parts that are not an ADR."""
    if value == "none":
        return [], []
    found: list[int] = []
    wrong: list[str] = []
    for part in (part.strip() for part in value.split(",")):
        match = REFERENCE.match(part)
        if match:
            found.append(int(match.group(1)))
        else:
            wrong.append(part)
    return found, wrong


def cycles(needs: Mapping[int, Iterable[int]]) -> list[int]:
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


def read_map(root: str) -> tuple[list[Entry], list[Listed], list[Listed]]:
    """Return what `parse` returns for the map under the root, or nothing for each if it does not exist."""
    path = os.path.join(root, MAP)
    if not os.path.isfile(path):
        return [], [], []
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        return parse(handle.read().split("\n"))


def needs_of(entries: list[Entry]) -> dict[int, set[int]]:
    """Return the numbers of the ADRs that each ADR needs, for the entries that have a line 'Needs'."""
    return {entry.number: set(references(entry.needs.value)[0]) for entry in entries if entry.needs is not None}


def owners(entries: list[Entry]) -> dict[str, int]:
    """Return the number of the ADR whose entry lists each file."""
    return {path: entry.number for entry in entries for path, _ in entry.files}


def closure(numbers: Iterable[int], needs: Mapping[int, Iterable[int]]) -> set[int]:
    """Return the numbers with the ADRs that they need, and those in turn."""
    found, stack = set(), list(numbers)
    while stack:
        current = stack.pop()
        if current not in found:
            found.add(current)
            stack.extend(needs.get(current, ()))
    return found


def is_reserved(number: int, reserved: Iterable[tuple[int, int]]) -> bool:
    return any(start <= number <= end for start, end in reserved)


def read_ranges(root: str) -> tuple[list[tuple[int, int]], list[tuple[int, str]]]:
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
                problems.append((number, f"'{line}' is not a range such as NNNN-NNNN, a comment or a blank line"))
                continue
            start, end = int(match.group(1)), int(match.group(2))
            if start > end:
                problems.append((number, f"the first bound of the range {line} is above the second"))
            elif start <= BASE[1]:
                problems.append(
                    (number, f"the range {line} overlaps {BASE[0]:04d}-{BASE[1]:04d}, which groundwork reserves")
                )
            elif any(start <= other_end and other_start <= end for other_start, other_end in reserved):
                problems.append((number, f"the range {line} overlaps another range"))
            else:
                reserved.append((start, end))
    return sorted(reserved), problems
