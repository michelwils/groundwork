#!/usr/bin/env python3
"""Prepare the update of a project to a later version of groundwork (ADR 0003, ADR 0005).

The version of groundwork the project is based on is in `.groundwork-version`, at the root of
the project: one line `X.Y.Z`. The script fetches the tags of groundwork under `groundwork/`,
creates the branch `chore/<issue>-update-groundwork-to-v<X-Y-Z>` and applies on it what changed
between the two versions, file by file, keeping the changes of the project. It leaves the result
in the working tree: it does not commit, push or open a pull request.

Files that concern groundwork itself are left out, see EXCLUDED.

Exit status: 0 when the project is updated or up to date, 1 on an error, 2 when some files are
in conflict. A conflict leaves markers in the file, and the script names the files.

Usage: update_groundwork.py ISSUE [--to X.Y.Z] [--source URL]
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile

SOURCE = "https://github.com/michelwils/groundwork.git"
VERSION_FILE = ".groundwork-version"
EXCLUDED = ("README.md", "LICENSE")
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


def apply_path(path, old, new):
    """Apply what changed in the path between the versions. Return True when it is in conflict."""
    base, theirs, ours = blob(old, path), blob(new, path), read(path)
    if theirs == ours:
        return False
    if ours == base:
        if theirs is None:
            remove(path)
        else:
            write(path, theirs, mode(new, path))
        return False
    if ours is None or theirs is None:
        return True
    if any(b"\0" in content for content in (ours, theirs, base or b"")):
        return True
    merged, conflict = merge(ours, base, theirs)
    write(path, merged, mode(new, path))
    return conflict


def run(args):
    if not args.issue.isdigit():
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

    branch = f"chore/{args.issue}-update-groundwork-to-v{new.replace('.', '-')}"
    if git("rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0:
        raise Failure(f"The branch {branch} already exists.")
    git("switch", "--quiet", "-c", branch)

    conflicts = [path for path in changed_paths(old, new) if apply_path(path, old, new)]
    with open(VERSION_FILE, "w") as handle:
        handle.write(new + "\n")

    print(f"branch: {branch}")
    print(f"from: {old}")
    print(f"to: {new}")
    if conflicts:
        print("Resolve the conflicts in these files:")
        for path in conflicts:
            print(f"- {path}")
        return 2
    return 0


def main():
    parser = argparse.ArgumentParser(description="Prepare the update of a project to a later version of groundwork.")
    parser.add_argument("issue", help="number of the issue of the update, used in the name of the branch")
    parser.add_argument("--to", help="version to update to, without the leading v (default: the latest)")
    parser.add_argument("--source", default=SOURCE, help="repository of groundwork (default: %(default)s)")
    try:
        sys.exit(run(parser.parse_args()))
    except Failure as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
