"""The ADRs that a project keeps, and what that makes of the files of groundwork.

The project lists the ADRs it keeps in `.groundwork-adrs`, one number of four digits (`0003`) or one
range (`0001-0999`) per line, with comments that start with `#`. A number adopts one ADR, a range adopts
every ADR it holds, including the ones that the source adds to it later. A number or a range must lie
within a range that the source reserves. Without the file, everything that the source reserves is kept.

`read` reads the file and reports what is wrong with it. `Kept` answers whether an ADR is kept: the ones
listed, the ones they need and the ones those need in turn, and ADR 0001. `included` and `content` say
what a tree of groundwork holds for a project: the files of an ADR that is left out are not taken, nor
an ADR that no range reserves, and the blocks of the ADRs that are left out are removed from the files
that several ADRs share (markers.py).
"""

import os
import re

import markers
from practices_map import ADR_DIRECTORY, ADR_FILE, closure, is_reserved

CHOICE_FILE = ".groundwork-adrs"
ALWAYS_KEPT = 1
NUMBER = re.compile(r"^[0-9]{4}$")
RANGE = re.compile(r"^([0-9]{4})-([0-9]{4})$")


def read(root, reserved):
    """Return the ranges that the file lists, or None without a file, and the problems as (line, message).

    A number is a range of one. A line that is refused adds nothing."""
    path = os.path.join(root, CHOICE_FILE)
    if not os.path.isfile(path):
        return None, []
    with open(path, "rb") as handle:
        lines = handle.read().decode("utf-8-sig", errors="replace").split("\n")
    adopted, problems = [], []
    for number, line in enumerate(lines, start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if NUMBER.match(line):
            start = end = int(line)
        elif RANGE.match(line):
            start, end = (int(part) for part in line.split("-"))
        else:
            problems.append((number, f"'{line}' is not a number such as 0003, a range such as 0001-0999, a comment or a blank line"))
            continue
        if start > end:
            problems.append((number, f"the first bound of the range {line} is above the second"))
        elif not any(first <= start and end <= last for first, last in reserved):
            problems.append((number, f"{line} does not lie within a range that the source reserves"))
        else:
            adopted.append((start, end))
    return adopted, problems


class Kept:
    """The ADRs that a project keeps.

    `adopted` is the list of ranges of the file, or None without a file. `needs` gives, by number, the
    numbers of the ADRs that each one needs. An ADR is kept when a range holds it, when a kept ADR needs
    it, or when it is ADR 0001."""

    def __init__(self, adopted, needs):
        self.adopted = adopted
        self.needed = None
        if adopted is not None:
            listed = {number for number in needs if self.listed(number)}
            self.needed = closure(listed | {ALWAYS_KEPT}, needs)

    def listed(self, number):
        return any(start <= number <= end for start, end in self.adopted)

    def __contains__(self, number):
        return self.adopted is None or number in self.needed or self.listed(number)

    def added(self):
        """Return the numbers of the ADRs that are kept because another needs them, and are not listed."""
        if self.adopted is None:
            return []
        return sorted(number for number in self.needed if number != ALWAYS_KEPT and not self.listed(number))


def included(path, owners, kept, reserved):
    """Tell whether a file of groundwork is taken for the project.

    The file of an ADR is taken when the ADR is in a range that the source reserves and is kept. A file
    that the map gives to an ADR is taken when the ADR is kept, and any other file is taken."""
    directory, _, name = path.rpartition("/")
    match = ADR_FILE.match(name) if directory == ADR_DIRECTORY else None
    if match:
        number = int(match.group(1))
        return is_reserved(number, reserved) and number in kept
    owner = owners.get(path)
    return owner is None or owner in kept


def content(path, text, kept):
    """Return the text of a file without the blocks of the ADRs that are not kept.

    A text whose markers are wrong is refused with a ValueError."""
    syntax = markers.kind(path)
    return text if syntax is None else markers.remove(text, syntax, kept)
