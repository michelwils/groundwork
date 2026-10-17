#!/usr/bin/env python3
"""Check the map of the practices of groundwork, `docs/practices.md` (ADR 0008).

The map has an entry `### NNNN. Title` for each ADR of `docs/adr/`, under `## Practices`, with
the line `- Needs:` (`none`, or the ADRs that it cannot be applied without, such as `ADR 0001, ADR 0003`),
the list `- Files:` of the files that apply the ADR and the list `- Shared lines:` of the files that
carry lines of the ADR, each with `path`, then where. The section `## Shared files` names the files that
carry the lines of several ADRs and the section `## Not part of a practice` the other files.

It reports an ADR without an entry or an entry without an ADR, an ADR that needs itself, an ADR that
does not exist or a cycle of needs, an ADR whose text names or links an ADR that its entry does not
list as needed, a file named in the map that is not tracked by git or that two entries name, and a
tracked file that the map does not name. The file
of an ADR is named by its entry. The lines of the shared files are not checked.

The map describes groundwork: it has entries for the ADRs `0001` to `0999` only. In a project, which
has a `.groundwork-version`, the files of the project are not in the map, so the check leaves out the
tracked files that the map does not name and reports only what the map names and the project lacks.

Usage: check_practices.py [ROOT]
"""

import os
import re
import subprocess
import sys

MAP = "docs/practices.md"
VERSION_FILE = ".groundwork-version"
FIRST_OF_A_PROJECT = 1000
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
NAMED = re.compile(r"\bADRs? \d{4}(?:(?:,| and| or| to)? \d{4})*")
LINKED = re.compile(r"\]\((\d{4})-[a-z0-9-]+\.md")
STATUS = re.compile(r"^\*\*Status:\*\*")
ADR_DIRECTORY = "docs/adr"
ADR_FILE = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
HEADING = re.compile(r"^### (\d{4})\. \S")
PATH = re.compile(r"`([^`]+)`")
LIST_ITEM = re.compile(r"^  - (.+)$")
REFERENCE = re.compile(r"^ADR (\d{4})$")
SECTIONS = {"## Practices": "practices", "## Shared files": "shared", "## Not part of a practice": "apart"}


def tracked(root):
    result = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True)
    if result.returncode != 0:
        return None
    return {path for path in result.stdout.decode().split("\0") if path}


def adrs_of(root):
    directory = os.path.join(root, ADR_DIRECTORY)
    if not os.path.isdir(directory):
        return set()
    numbers = {int(match.group(1)) for name in os.listdir(directory) if (match := ADR_FILE.match(name))}
    return {number for number in numbers if number < FIRST_OF_A_PROJECT}


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


def check_entries(entries, numbers, problems):
    seen = {}
    for entry in entries:
        number = entry["number"]
        if number in seen:
            problems.append((MAP, entry["line"], f"the ADR {number:04d} has an entry more than once, first at line {seen[number]}"))
        else:
            seen[number] = entry["line"]
        if number not in numbers:
            problems.append((MAP, entry["line"], f"the entry {number:04d} has no ADR in {ADR_DIRECTORY}"))
    for number in sorted(numbers - set(seen)):
        problems.append((MAP, 1, f"the ADR {number:04d} has no entry"))
    needs = {}
    for entry in entries:
        number = entry["number"]
        if entry["needs"] is None:
            problems.append((MAP, entry["line"], f"the entry {number:04d} has no line 'Needs'"))
            continue
        value, line = entry["needs"]
        found, wrong = references(value)
        for part in wrong:
            problems.append((MAP, line, f"'{part}' is not 'none' or ADRs such as 'ADR 0001'"))
        for other in found:
            if other == number:
                problems.append((MAP, line, f"the ADR {number:04d} refers to itself"))
            elif other not in numbers:
                problems.append((MAP, line, f"the ADR {other:04d} that the entry {number:04d} refers to does not exist"))
        needs[number] = [other for other in found if other in numbers and other != number]
    lines = {entry["number"]: entry["line"] for entry in entries}
    for number in cycles(needs):
        problems.append((MAP, lines[number], f"the ADR {number:04d} is on a cycle of needs"))


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
            kept.append((number, line))
    return kept


def check_texts(root, entries, numbers, problems):
    """Report the ADR named or linked in the text of an ADR that its entry does not list as needed."""
    allowed = {}
    for entry in entries:
        if entry["needs"] is not None and entry["number"] in numbers:
            allowed[entry["number"]] = {entry["number"], *references(entry["needs"][0])[0]}
    directory = os.path.join(root, ADR_DIRECTORY)
    for name in sorted(os.listdir(directory)) if os.path.isdir(directory) else []:
        match = ADR_FILE.match(name)
        if not match or int(match.group(1)) not in allowed:
            continue
        number = int(match.group(1))
        with open(os.path.join(directory, name), encoding="utf-8-sig", errors="replace") as handle:
            lines = handle.read().split("\n")
        for line_number, line in outside_code(lines):
            if STATUS.match(line):
                continue
            named = {int(n) for found in NAMED.findall(line) for n in re.findall(r"\d{4}", found)}
            named |= {int(n) for n in LINKED.findall(line)}
            for other in sorted(named - allowed[number]):
                problems.append((f"{ADR_DIRECTORY}/{name}", line_number, f"the ADR {number:04d} refers to the ADR {other:04d}, which its entry in the map does not list as needed"))


def check_files(root, entries, shared, apart, files, problems):
    named = {}
    listed = [(path, line, f"the entry {entry['number']:04d}") for entry in entries for path, line in entry["files"]]
    listed += [(path, line, "the shared files") for path, line in shared]
    listed += [(path, line, "the files that are not part of a practice") for path, line in apart]
    for path, line, owner in listed:
        if path in named:
            problems.append((MAP, line, f"the file {path} is named by {owner} and by {named[path]}"))
        else:
            named[path] = owner
        if path not in files:
            reason = "is not tracked by git" if os.path.exists(os.path.join(root, path)) else "does not exist"
            problems.append((MAP, line, f"the file {path} {reason}"))
    shared_files = {path for path, _ in shared}
    for entry in entries:
        for path, line in entry["shared"]:
            if path not in shared_files:
                problems.append((MAP, line, f"the file {path} of the shared lines of the entry {entry['number']:04d} is not in the shared files"))
    implicit = {path for path in files if path.startswith(ADR_DIRECTORY + "/") and ADR_FILE.match(path[len(ADR_DIRECTORY) + 1:])}
    if os.path.exists(os.path.join(root, VERSION_FILE)):
        return
    for path in sorted(files - set(named) - implicit):
        problems.append((MAP, 1, f"the file {path} is tracked and the map does not name it"))


def check(root):
    """Return the problems of the map under the root, as 'file:line: message'."""
    path = os.path.join(root, MAP)
    if not os.path.isfile(path):
        return [f"{MAP}:1: the file does not exist"]
    files = tracked(root)
    if files is None:
        return [f"{root}: not a git repository, the tracked files are unknown"]
    with open(path, encoding="utf-8-sig", errors="replace") as handle:
        entries, shared, apart = parse(handle.read().split("\n"))
    problems = []
    numbers = adrs_of(root)
    check_entries(entries, numbers, problems)
    check_texts(root, entries, numbers, problems)
    check_files(root, entries, shared, apart, files, problems)
    return [f"{name}:{line}: {message}" for name, line, message in sorted(problems)]


def main():
    problems = check(sys.argv[1] if len(sys.argv) > 1 else ".")
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
