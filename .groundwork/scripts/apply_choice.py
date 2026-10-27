#!/usr/bin/env python3
"""Make the files of a project agree with the ADRs of groundwork that it keeps.

The project lists the ADRs it keeps in `.groundwork-adrs` (choice.py). The map of the practices
(practices_map.py) says which files each ADR owns, and the files that several ADRs share have blocks
of lines per ADR (markers.py). This command deletes what the choice leaves out, and brings what has
entered it. It changes the working tree and leaves the index, the commits and the branches to the
project: review the result and commit it like any other change.

A new project, which has no `.groundwork-version` yet:

    apply_choice.py [--source URL] [--version X.Y.Z] [ADR …]

writes `.groundwork-adrs` from the ADRs named (a number such as `0003`, or a range such as
`0001-0999`; with none, the project keeps everything that its source reserves and no file is
written), records in `.groundwork-version` the latest release of the source or `--version`, records
`--source` in `.groundwork-source`, and deletes the files and the blocks of the ADRs left out and the
ADRs that no range reserves, which are decisions of groundwork itself.

A project that has a `.groundwork-version`, and that changed its choice in the file, whether it
narrowed it or widened it:

    apply_choice.py [--dry-run] [--source URL]

brings, from the version it records, the files and the blocks of the ADRs that entered the choice,
and deletes the files and the blocks of the ADRs that left it. A file, or a block, that differs from
its content in that version was changed by the project: it is kept and listed.

Only the ADRs of the ranges that the source reserves are concerned; an ADR of the project and its
blocks are left alone. Only files that git tracks are deleted, a path of the map that leaves the
repository or is in a directory .git is refused, and a refused choice stops everything before the first change. The command
refuses a working tree that is not clean and the default branch, except with `--dry-run`, which
changes no file of the working tree, nor the index or the branches, and refreshes the copy of the
tags of the source.

Output: the lines `add:`, `merge:`, `delete:`, `edit:`, `keep:`, `conflict:` and `write:`, `added:` for
the ADRs that enter and that the project does not list. Exit status: 0 when done, 1 on an error, 2
when the arguments are wrong, 3 when some files are kept or in conflict.
"""

import argparse
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import choice  # noqa: E402
import markers  # noqa: E402
import practices_map  # noqa: E402
import update_groundwork as update  # noqa: E402
from update_groundwork import Failure  # noqa: E402

TOKEN = re.compile(r"^(?:[0-9]{4}|[0-9]{4}-[0-9]{4})$")
BY_HAND = [
    "The steps that stay by hand:",
    "- apply the settings of the repository: python3 .groundwork/scripts/apply_settings.py [<owner>/<repo>]",
    "- create the secret GROUNDWORK_UPDATE_TOKEN",
    "- replace the README with the project's own, and the license",
]


class ReservedOnly:
    """The ADRs kept, and every number that no range reserves: the ADRs and the blocks of the project."""

    def __init__(self, kept, reserved):
        self.kept, self.reserved = kept, reserved

    def __contains__(self, number):
        return not practices_map.is_reserved(number, self.reserved) or number in self.kept


class Union:
    def __init__(self, first, second):
        self.first, self.second = first, second

    def __contains__(self, number):
        return number in self.first or number in self.second


def tracked():
    raw = update.git("ls-files", "-z").stdout
    return {path for path in raw.split("\0") if path}


def check_repository(root):
    if update.git("status", "--porcelain").stdout.strip():
        raise Failure("The working tree is not clean: commit or stash the changes first.")
    current = update.git("branch", "--show-current").stdout.strip()
    head = update.git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    named = head.stdout.strip().split("/", 1)[-1] if head.returncode == 0 and head.stdout.strip() else None
    if current and current in ({named} if named else {"main", "master"}):
        raise Failure(f"This is the default branch, {current}: work on a branch of its own.")


def refuse_paths_outside(root, side, kept):
    """Stop at a file of the map, for an ADR that is left out, that is not inside the repository or that is in a directory .git."""
    for path, owner in sorted(side.owners.items()):
        if owner not in kept and not update.inside(root, path):
            raise Failure(f"The map gives {path} to the ADR {owner:04d}, and it is outside the repository or in a directory .git: nothing is changed.")


def decoded(content):
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def blocks_of(text, syntax):
    """Return the lines of each block of the text, by ADR, in order."""
    lines = text.split("\n")
    found = {}
    for block in markers.parse(lines, syntax)[0]:
        found.setdefault(block["adr"], []).append(lines[block["start"]:block["end"] - 1])
    return found


class Changes:
    """What the command does: the lines of its output, and the writes that go with them."""

    def __init__(self):
        self.lines = []
        self.writes = []  # (path, content or None to delete, mode)
        self.attention = False

    def say(self, kind, path, reason=None):
        self.lines.append(f"{kind}: {path}" + (f" ({reason})" if reason else ""))
        if kind in ("keep", "conflict"):
            self.attention = True

    def delete(self, path):
        self.say("delete", path)
        self.writes.append((path, None, 0))

    def write(self, kind, path, content, file_mode=0o644, label=None):
        self.lines.append(f"{kind}: {label or path}")
        self.writes.append((path, content, file_mode))


def left_out(number, kept, reserved):
    return practices_map.is_reserved(number, reserved) and number not in kept


def removable_blocks(path, current, original, kept, reserved, changes):
    """Return the text without the blocks of the ADRs left out, keeping and saying the ones the project changed.

    `original` is the text of the version, or None when there is nothing to compare with."""
    syntax = markers.kind(path)
    text = decoded(current)
    if syntax is None or text is None:
        return current
    try:
        mine = blocks_of(text, syntax)
    except ValueError as error:
        raise Failure(f"{path}: {error}")
    theirs = blocks_of(decoded(original) or "", syntax) if original is not None else None
    changed = set()
    for number, found in mine.items():
        if left_out(number, kept, reserved) and theirs is not None and found != theirs.get(number):
            changed.add(number)
            changes.say("keep", path, f"block {number:04d} changed by the project")
    try:
        return markers.remove(text, syntax, Union(ReservedOnly(kept, reserved), changed)).encode("utf-8")
    except ValueError as error:
        raise Failure(f"{path}: {error}")


def new_project(args, root):
    side = update.Side(root=root)
    if side.problems:
        raise Failure("\n".join(f"{practices_map.RANGES_FILE}:{n}: {m}" for n, m in side.problems))
    if not side.has_map:
        raise Failure(f"{practices_map.MAP} is missing: this is not a repository created from groundwork.")
    if args.adrs:
        if os.path.exists(os.path.join(root, choice.CHOICE_FILE)):
            raise Failure(f"{choice.CHOICE_FILE} exists: list the ADRs in it, or remove it.")
        for token in args.adrs:
            if not TOKEN.match(token):
                raise Failure(f"'{token}' is not a number such as 0003 or a range such as 0001-0999.")
        text = "".join(f"{token}\n" for token in args.adrs)
        with tempfile.TemporaryDirectory() as directory:
            with open(os.path.join(directory, choice.CHOICE_FILE), "w", encoding="utf-8") as handle:
                handle.write(text)
            adopted, problems = choice.read(directory, side.reserved)
        if problems:
            raise Failure("\n".join(f"{choice.CHOICE_FILE}:{n}: {m}" for n, m in problems))
    else:
        text = None
        adopted, problems = choice.read(root, side.reserved)
        if problems:
            raise Failure("\n".join(f"{choice.CHOICE_FILE}:{n}: {m}" for n, m in problems))
    if args.source is not None and not update.is_address(args.source):
        raise Failure(
            f"{update.SOURCE_FILE} must hold one line with the address of the source, of the form https://host/path, "
            "with no user, password, space, query or fragment."
        )
    source = update.source_of(args.source)
    versions = update.fetch_releases(source)
    if not versions:
        raise Failure(f"The source {source} has no release.")
    if args.version:
        if not update.VERSION.match(args.version) or args.version not in versions:
            raise Failure(f"{args.version} is not a release of groundwork at {source}.")
        version = args.version
    else:
        version = versions[-1]

    kept = choice.Kept(adopted, side.needs)
    refuse_paths_outside(root, side, kept)
    changes = Changes()
    files = tracked()
    for path in sorted(files):
        if path in update.EXCLUDED:
            continue
        number = update.adr_number(path)
        owner = number if number is not None else side.owners.get(path)
        gone = (number is not None and (not practices_map.is_reserved(number, side.reserved) or number not in kept)) or (
            number is None and owner is not None and owner not in kept
        )
        if gone:
            if not update.inside(root, path):
                raise Failure(f"{path} leaves the repository or is in a directory .git: it is not deleted.")
            changes.delete(path)
            continue
        if markers.kind(path):
            current = update.read(path)
            if current is None:
                continue
            new = removable_blocks(path, current, None, kept, side.reserved, changes)
            if new != current:
                changes.write("edit", path, new, os.stat(path).st_mode)
    if text is not None:
        changes.write("write", choice.CHOICE_FILE, text.encode("utf-8"))
    changes.write("write", update.VERSION_FILE, f"{version}\n".encode("utf-8"), label=f"{update.VERSION_FILE} {version}")
    if args.source is not None:
        changes.write("write", update.SOURCE_FILE, f"{args.source}\n".encode("utf-8"))
    return changes, BY_HAND, kept.added()


def inherited(unknown):
    """Return a sentence for the project whose recorded version the source never published, which was perhaps
    created from the template of a base, else an empty string."""
    if not unknown:
        return ""
    names = [name for name in (update.VERSION_FILE, choice.CHOICE_FILE, update.SOURCE_FILE) if os.path.exists(name)]
    listed = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return f" If the project was created from the template of a base, these files are the base's: delete {listed}, then run the command again."


def existing_project(args, root):
    if args.version:
        raise Failure("--version is for a new project: the version is the one that .groundwork-version records.")
    old = update.recorded_version()
    source = update.source_of(args.source)
    versions = update.fetch_releases(source)
    unknown = old not in versions
    if args.adrs:
        raise Failure(
            f"The ADRs are listed in {choice.CHOICE_FILE}: edit that file, then run the command without a list.{inherited(unknown)}"
        )
    if unknown:
        raise Failure(f"The recorded version {old} is not a release of groundwork at {source}.{inherited(unknown)}")
    made = update.plan(old, old)
    changes = Changes()
    if made.kept.adopted is None:
        return changes, [f"There is no {choice.CHOICE_FILE}: the project keeps everything that its source reserves, nothing to apply."], []
    side, kept = made.side, made.kept
    refuse_paths_outside(root, side, kept)
    by_path = {path: (base, theirs) for path, base, theirs in made.steps}
    files = tracked()
    paths = set(by_path)
    deleted = set()
    for path in update.tree_paths(old):
        if path not in files:
            continue
        number = update.adr_number(path)
        owner = side.owners.get(path)
        if (number is not None and left_out(number, kept, side.reserved)) or (number is None and owner is not None and owner not in kept):
            if not update.inside(root, path):
                raise Failure(f"{path} leaves the repository or is in a directory .git: it is not deleted.")
            if update.read(path) == update.blob(old, path):
                deleted.add(path)
            else:
                changes.say("keep", path, "changed by the project")
        elif markers.kind(path):
            paths.add(path)
    for path in sorted(paths):
        if path in deleted:
            continue
        ours = update.read(path)
        text = ours
        if path in by_path:
            base, theirs = by_path[path]
            if ours is None:
                base = None  # the project lacks the file: it starts from nothing
            action = update.decide(base, theirs, ours)
            if action[0] == "conflict":
                changes.say("conflict", path)
                continue
            if action[0] == "none":
                text = ours
            else:
                text = action[1] if action[0] in ("write", "merged") else None
            if action[0] == "merged" and action[2]:
                changes.writes.append((path, text, update.mode(old, path)))
                changes.say("conflict", path)
                continue
        step_kind = None
        if path in by_path and text != ours:
            step_kind = "add" if ours is None else "merge"
        if text is not None and markers.kind(path):
            text = removable_blocks(path, text, update.blob(old, path), kept, side.reserved, changes)
        if step_kind and text != ours:
            changes.write(step_kind, path, text, update.mode(old, path))
        elif text != ours and text is not None:
            changes.write("edit", path, text, os.stat(path).st_mode)
    for path in sorted(update.tree_paths(old)):
        if path in by_path or os.path.lexists(path) or update.adr_number(path) is not None or side.owners.get(path) is not None:
            continue
        changes.write("add", path, update.text_of(path, update.blob(old, path), kept), update.mode(old, path))
    for path in sorted(deleted):
        changes.delete(path)
    return changes, [], made.said


def apply(changes):
    for path, content, file_mode in changes.writes:
        if content is None:
            update.remove(path)
        else:
            update.write(path, content, file_mode)


def run(args):
    root = os.path.realpath(update.git("rev-parse", "--show-toplevel").stdout.strip())
    os.chdir(root)
    if not args.dry_run:
        check_repository(root)
    if os.path.exists(update.VERSION_FILE):
        changes, notes, said = existing_project(args, root)
    else:
        changes, notes, said = new_project(args, root)
    for path, _, _ in changes.writes:
        if not update.inside(root, path):
            raise Failure(f"{path} leaves the repository or is in a directory .git: nothing is changed.")
    if not args.dry_run:
        apply(changes)
    for line in changes.lines:
        print(line)
    if said:
        print("added: " + ", ".join(f"{number:04d}" for number in said))
    for line in notes:
        print(line)
    if args.dry_run:
        print("dry run: no file of the working tree is changed.")
    return 3 if changes.attention else 0


def main():
    parser = argparse.ArgumentParser(description="Make the files of a project agree with the ADRs of groundwork that it keeps.")
    parser.add_argument("adrs", nargs="*", help="the ADRs to keep, for a new project: a number such as 0003 or a range such as 0001-0999")
    parser.add_argument("--dry-run", action="store_true", help="say what would be done and change no file")
    parser.add_argument("--source", help=f"repository of groundwork (default: the address in {update.SOURCE_FILE}, else {update.SOURCE})")
    parser.add_argument("--version", help="for a new project, the version to record (default: the latest release)")
    try:
        sys.exit(run(parser.parse_args()))
    except Failure as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
