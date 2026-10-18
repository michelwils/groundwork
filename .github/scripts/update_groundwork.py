#!/usr/bin/env python3
"""Prepare the update of a project to a later version of groundwork.

The version of groundwork the project is based on is in `.groundwork-version`, at the root of
the project: one line `X.Y.Z`. The script fetches the tags of groundwork under `groundwork/`,
creates the branch `chore/<issue>-update-groundwork-to-v<X-Y-Z>`, or
`groundwork/update-to-v<X-Y-Z>` when no issue is given, and applies on it what changed
between the two versions, file by file, keeping the changes of the project. It leaves the result
in the working tree: it does not commit, push or open a pull request.

Files that concern groundwork itself, or that belong to the project, are left out, see EXCLUDED.

The project may list the ADRs it keeps in `.groundwork-adrs` (choice.py). The script then reads,
in the version it moves to, the ranges of ADR numbers that the source reserves and the map of the
practices (practices_map.py), and applies only what the choice keeps: the files of the other ADRs
are neither copied nor deleted, and the blocks of their lines are taken out of both versions of the
files that several ADRs share (markers.py) before the merge. What enters the choice starts from
nothing, so that its files are not taken for deletions: an ADR kept whose file the project lacks, a
file that no ADR left out owns any more, an ADR of a range that the source reserves from now on.
Everything is read before the branch is created, so a choice that is refused changes nothing.

Exit status: 0 when the project is updated or up to date, 1 on an error, 2 when some files are
in conflict. A conflict leaves markers in the file, and the script names the files. After the
lines `branch:`, `from:` and `to:`, the line `added: 0002, 0003` names the ADRs that enter the
choice and that the project does not list, and the lines `- path` name the files in conflict.

Usage: update_groundwork.py [ISSUE] [--to X.Y.Z] [--source URL]
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import choice  # noqa: E402
import markers  # noqa: E402
import practices_map  # noqa: E402

SOURCE = "https://github.com/michelwils/groundwork.git"
VERSION_FILE = ".groundwork-version"
EXCLUDED = ("README.md", "LICENSE", VERSION_FILE, choice.CHOICE_FILE)
PREFIX = "groundwork/"
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class Failure(Exception):
    pass


def git(*args, check=True, text=True):
    result = subprocess.run(["git", *args], capture_output=True, text=text)
    if check and result.returncode != 0:
        message = result.stderr if text else result.stderr.decode(errors="replace")
        raise Failure(f"git {' '.join(args)} failed: {message.strip()}")
    return result


def as_tuple(version):
    return tuple(int(part) for part in version.split("."))


def recorded_version():
    try:
        with open(VERSION_FILE) as handle:
            content = handle.read()
    except FileNotFoundError:
        raise Failure(f"{VERSION_FILE} is missing: create it with the version of groundwork the project is based on.")
    version = content.strip()
    if content != version + "\n" or not VERSION.match(version):
        raise Failure(f"{VERSION_FILE} must hold one line of the form X.Y.Z, without 'v'.")
    return version


def released_versions():
    tags = git("tag", "--list", f"{PREFIX}v[0-9]*").stdout.split()
    return sorted((tag[len(PREFIX) + 1:] for tag in tags if VERSION.match(tag[len(PREFIX) + 1:])), key=as_tuple)


def blob(version, path):
    """Return the content of the path in the version, or None when it does not exist there."""
    result = git("cat-file", "blob", f"refs/tags/{PREFIX}v{version}:{path}", check=False, text=False)
    return result.stdout if result.returncode == 0 else None


def mode(version, path):
    line = git("ls-tree", f"refs/tags/{PREFIX}v{version}", "--", path).stdout.split()
    return int(line[0], 8) if line else 0o100644


def tree_paths(version):
    raw = git("ls-tree", "-r", "--name-only", "-z", f"refs/tags/{PREFIX}v{version}").stdout
    return [path for path in raw.split("\0") if path and path not in EXCLUDED]


def changed_paths(old, new):
    raw = git("diff", "--no-renames", "--name-only", "-z", f"refs/tags/{PREFIX}v{old}", f"refs/tags/{PREFIX}v{new}").stdout
    return [path for path in raw.split("\0") if path and path not in EXCLUDED]


def read(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except FileNotFoundError:
        return None


def write(path, content, file_mode):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(content)
    os.chmod(path, 0o755 if file_mode & 0o111 else 0o644)


def remove(path):
    os.remove(path)
    try:
        os.removedirs(os.path.dirname(path) or ".")
    except OSError:
        pass


def merge(ours, base, theirs):
    """Return (content, conflict) of the three-way merge of three versions of a text file."""
    with tempfile.TemporaryDirectory() as directory:
        paths = []
        for name, content in (("ours", ours), ("base", base or b""), ("theirs", theirs)):
            paths.append(os.path.join(directory, name))
            with open(paths[-1], "wb") as handle:
                handle.write(content)
        result = subprocess.run(
            ["git", "merge-file", "-p", "-L", "project", "-L", "previous groundwork", "-L", "new groundwork", *paths],
            capture_output=True,
        )
    if result.returncode < 0 or result.returncode > 127:
        raise Failure("git merge-file failed: " + result.stderr.decode(errors="replace").strip())
    return result.stdout, result.returncode > 0


def apply_path(path, base, theirs, ours, file_mode):
    """Apply what changed in the path from the base to theirs. Return True when it is in conflict."""
    if theirs == ours:
        return False
    if ours == base:
        if theirs is None:
            remove(path)
        else:
            write(path, theirs, file_mode)
        return False
    if ours is None or theirs is None:
        return True
    if any(b"\0" in content for content in (ours, theirs, base or b"")):
        return True
    merged, conflict = merge(ours, base, theirs)
    write(path, merged, file_mode)
    return conflict


class Without:
    """The ADRs of a choice, except those that enter it."""

    def __init__(self, kept, entering):
        self.kept, self.entering = kept, entering

    def __contains__(self, number):
        return number in self.kept and number not in self.entering


class Side:
    """What a version of groundwork says about the ADRs: the ranges it reserves and the map of the practices."""

    def __init__(self, version):
        self.has_map = blob(version, practices_map.MAP) is not None
        with tempfile.TemporaryDirectory() as directory:
            for path in (practices_map.MAP, practices_map.RANGES_FILE):
                content = blob(version, path)
                if content is not None:
                    write(os.path.join(directory, path), content, 0o644)
            self.reserved, self.problems = practices_map.read_ranges(directory)
            entries = practices_map.read_map(directory)[0]
        self.needs = practices_map.needs_of(entries)
        self.owners = practices_map.owners(entries)


def adr_number(path):
    directory, _, name = path.rpartition("/")
    match = practices_map.ADR_FILE.match(name) if directory == practices_map.ADR_DIRECTORY else None
    return int(match.group(1)) if match else None


def text_of(path, content, kept):
    """Return the content without the blocks of the ADRs that are not kept, when it is a file with blocks."""
    if content is None or markers.kind(path) is None:
        return content
    try:
        return choice.content(path, content.decode("utf-8"), kept).encode("utf-8")
    except UnicodeDecodeError:
        return content
    except ValueError as error:
        raise Failure(f"{path}: {error}")


def plan(old, new):
    """Return the numbers of the ADRs to say as added, and the steps to apply.

    A step is (path, base, theirs): the contents are already filtered, and the base is None for a path
    that starts from nothing. It reads the project and the versions and writes nothing."""
    after, before = Side(new), Side(old)
    if after.problems:
        raise Failure("\n".join(f"{practices_map.RANGES_FILE}:{number}: {message}" for number, message in after.problems))
    adopted, problems = choice.read(".", after.reserved)
    if problems:
        raise Failure("\n".join(f"{choice.CHOICE_FILE}:{number}: {message}" for number, message in problems))
    if adopted is not None and not after.has_map:
        raise Failure(f"groundwork {new} has no {practices_map.MAP}: it cannot apply the choice of {choice.CHOICE_FILE}.")
    kept_after = choice.Kept(adopted, after.needs)
    kept_before = choice.Kept(adopted, before.needs) if before.has_map else kept_after

    new_paths = tree_paths(new)
    directory = practices_map.ADR_DIRECTORY
    held = {adr_number(f"{directory}/{name}") for name in os.listdir(directory)} if os.path.isdir(directory) else set()
    in_tree = {adr_number(path) for path in new_paths} - {None}
    entering = {
        number for number in in_tree
        if practices_map.is_reserved(number, after.reserved) and number in kept_after
        and (number not in kept_before or (adopted is not None and number not in held))
    }
    said = [number for number in sorted(entering) if adopted is not None and not kept_after.listed(number)]

    def wanted(path):
        if path in new_set:
            return choice.included(path, after.owners, kept_after, after.reserved)
        return not before.has_map or choice.included(path, before.owners, kept_before, before.reserved)

    def fresh(path):
        owner = adr_number(path) or after.owners.get(path)
        if owner in entering:
            return True
        return before.has_map and not choice.included(path, before.owners, kept_before, before.reserved)

    new_set = set(new_paths)
    candidates = set(changed_paths(old, new)) | {path for path in new_paths if fresh(path)}
    if entering:
        for path in new_paths:
            if path not in candidates and markers.kind(path):
                text = blob(new, path)
                try:
                    found = markers.parse(text.decode("utf-8").split("\n"), markers.kind(path))[0]
                except UnicodeDecodeError:
                    continue
                if any(block["adr"] in entering for block in found):
                    candidates.add(path)
    steps = []
    for path in sorted(candidates):
        if wanted(path):
            base = None if path in new_set and fresh(path) else blob(old, path)
            steps.append((path, text_of(path, base, Without(kept_after, entering)), text_of(path, blob(new, path), kept_after)))
    return said, steps


def run(args):
    if args.issue is not None and not args.issue.isdigit():
        raise Failure(f"'{args.issue}' is not an issue number.")
    os.chdir(git("rev-parse", "--show-toplevel").stdout.strip())
    old = recorded_version()
    if git("status", "--porcelain").stdout.strip():
        raise Failure("The working tree is not clean: commit or stash the changes first.")

    git("fetch", "--quiet", args.source, f"+refs/tags/*:refs/tags/{PREFIX}*")
    versions = released_versions()
    if old not in versions:
        raise Failure(f"The recorded version {old} is not a release of groundwork at {args.source}.")

    if args.to:
        if not VERSION.match(args.to):
            raise Failure(f"'{args.to}' is not a version of the form X.Y.Z.")
        if as_tuple(args.to) <= as_tuple(old):
            raise Failure(f"{args.to} is not a later version than the recorded {old}.")
        if args.to not in versions:
            raise Failure(f"{args.to} is not a release of groundwork at {args.source}.")
        new = args.to
    else:
        new = versions[-1]
        if as_tuple(new) <= as_tuple(old):
            print(f"The project is up to date with groundwork {old}.")
            return 0

    slug = f"update-groundwork-to-v{new.replace('.', '-')}"
    branch = f"chore/{args.issue}-{slug}" if args.issue else f"groundwork/update-to-v{new.replace('.', '-')}"
    if git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0:
        raise Failure(f"The branch {branch} already exists.")
    said, steps = plan(old, new)
    git("switch", "--quiet", "-c", branch)

    conflicts = [path for path, base, theirs in steps if apply_path(path, base, theirs, read(path), mode(new, path))]
    with open(VERSION_FILE, "w") as handle:
        handle.write(new + "\n")

    print(f"branch: {branch}")
    print(f"from: {old}")
    print(f"to: {new}")
    if said:
        print("added: " + ", ".join(f"{number:04d}" for number in said))
    if conflicts:
        print("Resolve the conflicts in these files:")
        for path in conflicts:
            print(f"- {path}")
        return 2
    return 0


def main():
    parser = argparse.ArgumentParser(description="Prepare the update of a project to a later version of groundwork.")
    parser.add_argument("issue", nargs="?", help="number of the issue of the update, used in the name of the branch")
    parser.add_argument("--to", help="version to update to, without the leading v (default: the latest)")
    parser.add_argument("--source", default=SOURCE, help="repository of groundwork (default: %(default)s)")
    try:
        sys.exit(run(parser.parse_args()))
    except Failure as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
