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
of an ADR is named by its entry.

The lines that several ADRs share are in blocks (markers.py). A file belongs to the ADR whose entry
lists it in `Files`, or to none: it is then in `## Shared files`. In a file with an owner, only the
lines of the other ADRs are in blocks. The check reports a block that is badly formed, for an ADR
that does not exist or for the owner of the file, a block or a line that names an ADR other than its
own and the ones it needs (a line outside the blocks of a file with no owner names none; the files of
an ADR that have no block, and that no `Shared lines` lists, are not read), and a
`Shared lines` list that is not the list of the files that have a block of the ADR. In a project, which
has a `.groundwork-version`, the lines outside the blocks are its own and may name any ADR.

The map describes the ADRs of the ranges that the source reserves, `0001` to `0999` and the ranges of
`.groundwork-ranges`, and only those: an ADR of one of these ranges without an entry is reported, and
an ADR of groundwork may not need one of a community base. In a project, which has a `.groundwork-version`,
the files of the project are not in the map, so the check leaves out the tracked files that the map does
not name and reports only what the map names and the project lacks. When the project keeps some of the
ADRs (`.groundwork-adrs`), the entries of the others and their files are left out, and the lines that
are refused in the two files are reported by check_adrs.py.

Usage: check_practices.py [ROOT]
"""

import os
import re
import subprocess
import sys

import choice
import markers
from practices_map import ADR_DIRECTORY, ADR_FILE, BASE, MAP, RANGES_FILE, cycles, is_reserved, needs_of, parse, read_ranges, references

VERSION_FILE = ".groundwork-version"
FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})")
NAMED = re.compile(r"\bADRs? \d{4}(?:(?:,| and| or| to)? \d{4})*")
LINKED = re.compile(r"\]\((?:[^)\s]*/)?(\d{4})-[a-z0-9-]+\.md")
STATUS = re.compile(r"^\*\*Status:\*\*")


def tracked(root):
    result = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True)
    if result.returncode != 0:
        return None
    return {path for path in result.stdout.decode().split("\0") if path}


def adrs_of(root, reserved, kept):
    """Return the numbers of the ADRs in docs/adr that the source reserves and the project keeps."""
    directory = os.path.join(root, ADR_DIRECTORY)
    if not os.path.isdir(directory):
        return set()
    numbers = {int(match.group(1)) for name in os.listdir(directory) if (match := ADR_FILE.match(name))}
    return {number for number in numbers if is_reserved(number, reserved) and number in kept}


def check_entries(entries, numbers, reserved, problems):
    seen = {}
    for entry in entries:
        number = entry["number"]
        if number in seen:
            problems.append((MAP, entry["line"], f"the ADR {number:04d} has an entry more than once, first at line {seen[number]}"))
        else:
            seen[number] = entry["line"]
        if not is_reserved(number, reserved):
            problems.append((MAP, entry["line"], f"the entry {number:04d} is for an ADR outside the ranges that the source reserves"))
        elif number not in numbers:
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
            elif BASE[0] <= number <= BASE[1] and not BASE[0] <= other <= BASE[1]:
                problems.append((MAP, line, f"the ADR {number:04d} of groundwork needs the ADR {other:04d}, which is not of groundwork"))
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


def named_adrs(line, reserved=(BASE,)):
    """Return the numbers of the ADRs of the ranges that the source reserves that a line names or links."""
    named = {int(number) for found in NAMED.findall(line) for number in re.findall(r"\d{4}", found)}
    named |= {int(number) for number in LINKED.findall(line)}
    return {number for number in named if is_reserved(number, reserved)}


def check_blocks(root, entries, owned, reserved, shared, files, numbers, problems):
    """Check the blocks of the files that several ADRs share, and the lines outside them."""
    needs = {}
    for entry in entries:
        if entry["needs"] is not None:
            needs[entry["number"]] = set(references(entry["needs"][0])[0])
    owner = {path: entry["number"] for entry in owned for path, _ in entry["files"]}
    shared_files = {path for path, _ in shared}
    listed_anywhere = {path for entry in entries for path, _ in entry["shared"]}
    project = os.path.exists(os.path.join(root, VERSION_FILE))
    having = {}
    for path in sorted(shared_files | set(owner)):
        syntax = markers.kind(path)
        full = os.path.join(root, path)
        if syntax is None or path not in files or not os.path.isfile(full):
            continue
        with open(full, encoding="utf-8-sig", errors="replace") as handle:
            lines = handle.read().split("\n")
        blocks, found = markers.parse(lines, syntax)
        problems.extend((path, line, message) for line, message in found)
        if path in owner and not blocks and path not in listed_anywhere:
            continue
        belonging = {}
        for block in blocks:
            having.setdefault(block["adr"], {}).setdefault(path, block["start"])
            if block["adr"] not in numbers:
                problems.append((path, block["start"], f"the block is for the ADR {block['adr']:04d}, which does not exist"))
            elif block["adr"] == owner.get(path):
                problems.append((path, block["start"], f"the lines of the ADR {block['adr']:04d}, which owns the file, are not marked"))
            for line in range(block["start"], block["end"] + 1):
                belonging[line] = block["adr"]
        for number, line in outside_code(lines) if syntax == "markdown" else enumerate(lines, start=1):
            adr = belonging.get(number)
            if adr is not None:
                allowed, who = {adr} | needs.get(adr, set()), f"the block of the ADR {adr:04d}"
            elif project:
                continue
            elif path in owner:
                allowed, who = {owner[path]} | needs.get(owner[path], set()), f"a line of the ADR {owner[path]:04d}"
            else:
                allowed, who = set(), "a line outside the blocks"
            for other in sorted(named_adrs(line, reserved) - allowed):
                problems.append((path, number, f"{who} names the ADR {other:04d}, which it does not need"))
    for entry in entries:
        number = entry["number"]
        listed = {path: line for path, line in entry["shared"]}
        for path, line in listed.items():
            if path not in shared_files and path not in owner:
                problems.append((MAP, line, f"the file {path} of the shared lines of the entry {number:04d} is neither a shared file nor the file of an ADR"))
            elif path not in having.get(number, {}) and path in files:
                problems.append((MAP, line, f"the entry {number:04d} lists {path} in 'Shared lines', and the file has no block of the ADR {number:04d}"))
        for path, line in having.get(number, {}).items():
            if path not in listed:
                problems.append((path, line, f"the file has a block of the ADR {number:04d} that its entry in the map does not list in 'Shared lines'"))


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
    implicit = {path for path in files if path.startswith(ADR_DIRECTORY + "/") and ADR_FILE.match(path[len(ADR_DIRECTORY) + 1:])}
    implicit |= {RANGES_FILE} & files
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
    reserved = read_ranges(root)[0]
    kept = choice.Kept(choice.read(root, reserved)[0], needs_of(entries))
    owned, entries = entries, [entry for entry in entries if entry["number"] in kept]
    numbers = adrs_of(root, reserved, kept)
    check_entries(entries, numbers, reserved, problems)
    check_texts(root, entries, numbers, problems)
    check_files(root, entries, shared, apart, files, problems)
    check_blocks(root, entries, owned, reserved, shared, files, numbers, problems)
    return [f"{name}:{line}: {message}" for name, line, message in sorted(problems)]


def main():
    problems = check(sys.argv[1] if len(sys.argv) > 1 else ".")
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
