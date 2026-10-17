#!/usr/bin/env python3
"""Check the map of the practices of groundwork, `docs/practices.md` (ADR 0008).

The map has an entry `### NNNN. Title` for each ADR of `docs/adr/`, under `## Practices`, with
the lines `- Needs:` and `- Mentions:` (`none`, or ADRs such as `ADR 0001, ADR 0003`), the list
`- Files:` of the files that apply the ADR and the list `- Shared lines:` of the files that carry
lines of the ADR, each with `path`, then where. The section `## Shared files` names the files that
carry the lines of several ADRs and the section `## Not part of a practice` the other files.

It reports an ADR without an entry or an entry without an ADR, an ADR that needs itself, an ADR that
does not exist, an ADR both needed and mentioned or a cycle of needs, a file named in the map that is
not tracked by git or that two entries name, and a tracked file that the map does not name. The file
of an ADR is named by its entry. The lines of the shared files are not checked.

Usage: check_practices.py [ROOT]
"""

import os
import re
import subprocess
import sys

MAP = "docs/practices.md"
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
    return {int(match.group(1)) for name in os.listdir(directory) if (match := ADR_FILE.match(name))}


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
            entry = {"number": int(HEADING.match(line).group(1)), "line": number, "needs": None, "mentions": None, "files": [], "shared": []}
            entries.append(entry)
            list_name = None
        elif entry is not None and line.startswith("- "):
            head, _, value = line[2:].partition(":")
            list_name = {"Files": "files", "Shared lines": "shared"}.get(head)
            if head in ("Needs", "Mentions"):
                entry[head.lower()] = (value.strip(), number)
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
            problems.append((entry["line"], f"the ADR {number:04d} has an entry more than once, first at line {seen[number]}"))
        else:
            seen[number] = entry["line"]
        if number not in numbers:
            problems.append((entry["line"], f"the entry {number:04d} has no ADR in {ADR_DIRECTORY}"))
    for number in sorted(numbers - set(seen)):
        problems.append((1, f"the ADR {number:04d} has no entry"))
    needs = {}
    for entry in entries:
        number = entry["number"]
        for name in ("needs", "mentions"):
            if entry[name] is None:
                problems.append((entry["line"], f"the entry {number:04d} has no line '{name.capitalize()}'"))
        found = {}
        for name in ("needs", "mentions"):
            if entry[name] is None:
                continue
            value, line = entry[name]
            found[name], wrong = references(value)
            for part in wrong:
                problems.append((line, f"'{part}' is not 'none' or ADRs such as 'ADR 0001'"))
            for other in found[name]:
                if other == number:
                    problems.append((line, f"the ADR {number:04d} refers to itself"))
                elif other not in numbers:
                    problems.append((line, f"the ADR {other:04d} that the entry {number:04d} refers to does not exist"))
        both = set(found.get("needs", [])) & set(found.get("mentions", []))
        for other in sorted(both):
            problems.append((entry["mentions"][1], f"the ADR {other:04d} is both needed and mentioned by the entry {number:04d}"))
        needs[number] = [other for other in found.get("needs", []) if other in numbers and other != number]
    lines = {entry["number"]: entry["line"] for entry in entries}
    for number in cycles(needs):
        problems.append((lines[number], f"the ADR {number:04d} is on a cycle of needs"))


def check_files(root, entries, shared, apart, files, problems):
    named = {}
    listed = [(path, line, f"the entry {entry['number']:04d}") for entry in entries for path, line in entry["files"]]
    listed += [(path, line, "the shared files") for path, line in shared]
    listed += [(path, line, "the files that are not part of a practice") for path, line in apart]
    for path, line, owner in listed:
        if path in named:
            problems.append((line, f"the file {path} is named by {owner} and by {named[path]}"))
        else:
            named[path] = owner
        if path not in files:
            reason = "is not tracked by git" if os.path.exists(os.path.join(root, path)) else "does not exist"
            problems.append((line, f"the file {path} {reason}"))
    shared_files = {path for path, _ in shared}
    for entry in entries:
        for path, line in entry["shared"]:
            if path not in shared_files:
                problems.append((line, f"the file {path} of the shared lines of the entry {entry['number']:04d} is not in the shared files"))
    implicit = {path for path in files if path.startswith(ADR_DIRECTORY + "/") and ADR_FILE.match(path[len(ADR_DIRECTORY) + 1:])}
    for path in sorted(files - set(named) - implicit):
        problems.append((1, f"the file {path} is tracked and the map does not name it"))


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
    check_entries(entries, adrs_of(root), problems)
    check_files(root, entries, shared, apart, files, problems)
    return [f"{MAP}:{line}: {message}" for line, message in sorted(problems)]


def main():
    problems = check(sys.argv[1] if len(sys.argv) > 1 else ".")
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
