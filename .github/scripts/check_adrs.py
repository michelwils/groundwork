#!/usr/bin/env python3
"""Check that the ADRs follow their template and their numbering (ADR 0001).

Every Markdown file of docs/adr/ except template.md is named `NNNN-title-in-kebab-case.md`. It starts with
`# NNNN. Title`, with the number of its name, and has a line `**Status:**` with `proposed`,
`accepted`, `rejected` or `superseded by NNNN`, which refers to a more recent ADR that exists,
alone or as the link of the template. It has the sections Context, Decision and Consequences, each
once, in that order and not empty. Other sections may follow.

The numbers `0001` to `0999` are reserved for the ADRs of groundwork, and those of a project start
at `1000`. In each range there is no duplicate and no skipped number, since a number is never
reused. template.md has the title `# NNNN. …` and the three sections.

Usage: check_adrs.py [DIR]
"""

import os
import re
import sys

DIRECTORY = os.path.join("docs", "adr")
TEMPLATE = "template.md"
NAME = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
TITLE = re.compile(r"^# (\d{4})\. \S")
STATUS = re.compile(r"^\*\*Status:\*\* ?(.*)$")
SUPERSEDED = re.compile(r"^superseded by (?:\[(\d{4})\]\((\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md\)|(\d{4}))$")
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
STATUSES = ("proposed", "accepted", "rejected")
SECTIONS = ("Context", "Decision", "Consequences")
FIRST_OF_A_PROJECT = 1000


def read(path):
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        return handle.read().split("\n")


def outside_code(lines):
    """Return the (number, line) of the lines that are not in a code block, nor its fences."""
    kept, fence = [], None
    for number, line in enumerate(lines, start=1):
        opening = FENCE.match(line)
        if fence:
            if line.strip() and set(line.strip()) == {fence[0]} and len(line.strip()) >= len(fence):
                fence = None
        elif opening:
            fence = opening.group(1)
        else:
            kept.append((number, line.rstrip("\r")))
    return kept


def sections(lines):
    """Return the (name, line, empty) of the level 2 headings that are not in a code block."""
    found = []
    for number, line in outside_code(lines):
        if line.startswith("## "):
            found.append([re.sub(r"[ \t]+#+$", "", line[3:].strip()), number, True])
        elif found and line.strip():
            found[-1][2] = False
    return found


def check_sections(name, lines, problems):
    found = sections(lines)
    names = [heading[0] for heading in found]
    for required in SECTIONS:
        if required not in names:
            problems.append(f"{name}:1: the section '{required}' is missing")
        elif names.count(required) > 1:
            problems.append(f"{name}:{found[names.index(required)][1]}: the section '{required}' is repeated")
    once = [heading for heading in names if heading in SECTIONS and names.count(heading) == 1]
    if once != [required for required in SECTIONS if required in once]:
        problems.append(f"{name}:1: the sections must come in the order of the template: {', '.join(SECTIONS)}")
    for heading, number, empty in found:
        if heading in SECTIONS and empty and names.count(heading) == 1:
            problems.append(f"{name}:{number}: the section '{heading}' is empty")


def check_adr(name, number, lines, numbers, problems):
    title = TITLE.match(lines[0]) if lines else None
    if not title or int(title.group(1)) != number:
        problems.append(f"{name}:1: the title must be '# {number:04d}. …', with the number of the file")
    statuses = [(index, STATUS.match(line)) for index, line in outside_code(lines) if STATUS.match(line)]
    if not statuses:
        problems.append(f"{name}:1: the line '**Status:**' is missing")
    elif len(statuses) > 1:
        problems.append(f"{name}:{statuses[1][0]}: the line '**Status:**' is given more than once")
    else:
        index, match = statuses[0]
        value = match.group(1).strip()
        superseded = SUPERSEDED.match(value)
        if value in STATUSES:
            pass
        elif not superseded:
            problems.append(f"{name}:{index}: the status '{value}' is not proposed, accepted, rejected or superseded by NNNN")
        else:
            text, target, plain = superseded.groups()
            referred = int(plain or text)
            if target is not None and int(target) != referred:
                problems.append(f"{name}:{index}: the link of the status leads to {target}, not to {text}")
            elif referred not in numbers:
                problems.append(f"{name}:{index}: the ADR {referred:04d} that supersedes this one does not exist")
            elif referred <= number:
                problems.append(f"{name}:{index}: the ADR that supersedes this one must be more recent")
    check_sections(name, lines, problems)


def check_numbers(numbers, problems):
    groundwork = sorted(n for n in numbers if n < FIRST_OF_A_PROJECT)
    project = sorted(n for n in numbers if n >= FIRST_OF_A_PROJECT)
    for start, found in ((1, groundwork), (FIRST_OF_A_PROJECT, project)):
        if found and found[0] == 0:
            problems.append(f"{DIRECTORY}: the numbers start at 0001, not at 0000")
            continue
        if found:
            for missing in sorted(set(range(start, found[-1] + 1)) - set(found)):
                kind = "groundwork" if start == 1 else "project"
                problems.append(f"{DIRECTORY}: the number {missing:04d} of the {kind} ADRs is skipped")


def check(root):
    """Return the problems of the ADRs under the root, as 'file:line: message'."""
    directory = os.path.join(root, DIRECTORY)
    if not os.path.isdir(directory):
        return [f"{DIRECTORY}: the directory does not exist"]
    problems, files = [], {}
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if os.path.isdir(path) or not name.endswith(".md"):
            continue
        relative = f"{DIRECTORY}/{name}".replace(os.sep, "/")
        match = NAME.match(name)
        if name == TEMPLATE:
            lines = read(path)
            if not re.match(r"^# NNNN\. \S", lines[0]):
                problems.append(f"{relative}:1: the title must be '# NNNN. …'")
            check_sections(relative, lines, problems)
        elif match:
            files.setdefault(int(match.group(1)), []).append((relative, path))
        else:
            problems.append(f"{relative}: not named NNNN-title-in-kebab-case.md")
    for number, entries in files.items():
        if len(entries) > 1:
            problems.append(f"{DIRECTORY}: the number {number:04d} is used by {len(entries)} files: " + ", ".join(e[0] for e in entries))
    for number, entries in files.items():
        for relative, path in entries:
            check_adr(relative, number, read(path), set(files), problems)
    check_numbers(set(files), problems)
    return sorted(problems)


def main():
    problems = check(sys.argv[1] if len(sys.argv) > 1 else ".")
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
