#!/usr/bin/env python3
"""Compute the next version and the release notes (ADR 0005, ADR 0006).

The version is decided from the commit titles since the previous tag reachable
from HEAD, by the highest increment among them. A change undone by a `revert`
before the release is ignored together with its revert.

Usage: release.py [--version X.Y.Z] [--notes FILE]
"""

import argparse
import os
import re
import subprocess
import sys

TYPES = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"]
TITLE = re.compile(
    r"^(?P<type>" + "|".join(TYPES) + r")(\((?P<scope>[a-z]+)\))?(?P<bang>!)?: (?P<description>.+)$"
)
PULL_REQUEST = re.compile(r" \(#\d+\)$")
BREAKING_FOOTER = re.compile(r"^BREAKING[ -]CHANGE:", re.MULTILINE)
VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
TAG = re.compile(r"^v(\d+\.\d+\.\d+)$")
LEVELS = {"none": 0, "patch": 1, "minor": 2, "major": 3}
SECTIONS = ["feat", "fix", "perf", "docs", "style", "refactor", "test", "build", "ci", "chore", "revert"]


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def previous_version():
    """Return the version of the latest tag reachable from HEAD, or None."""
    try:
        tag = git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*.[0-9]*.[0-9]*").strip()
    except subprocess.CalledProcessError:
        return None
    match = TAG.match(tag)
    return match.group(1) if match else None


def commits_since(version):
    """Return the commits since the version, oldest first, as dicts."""
    span = f"v{version}..HEAD" if version else "HEAD"
    raw = git("log", "--reverse", "--format=%H%x1f%B%x1e", span)
    commits = []
    for entry in raw.split("\x1e"):
        entry = entry.strip("\n")
        if not entry:
            continue
        sha, _, message = entry.partition("\x1f")
        title = message.strip().split("\n", 1)[0]
        match = TITLE.match(title)
        commit = {"sha": sha, "title": title, "message": message, "undone": False}
        if match:
            commit.update(
                type=match.group("type"),
                scope=match.group("scope"),
                description=match.group("description"),
                breaking=bool(match.group("bang")) or bool(BREAKING_FOOTER.search(message)),
            )
        else:
            commit.update(type=None, scope=None, description=title, breaking=False)
        commits.append(commit)
    return commits


def key(description):
    return PULL_REQUEST.sub("", description).strip()


def cancel_reverts(commits):
    """Mark a reverted commit and its revert as undone, when both are in the range."""
    for index, commit in enumerate(commits):
        if commit["type"] != "revert" or commit["breaking"]:
            continue
        for earlier in commits[:index]:
            if (
                not earlier["undone"]
                and earlier["type"] not in (None, "revert")
                and key(earlier["description"]) == key(commit["description"])
            ):
                earlier["undone"] = commit["undone"] = True
                break


def increment(commit, major):
    if commit["undone"] or commit["type"] is None:
        return "none"
    if commit["breaking"]:
        return "major" if major >= 1 else "minor"
    return {"feat": "minor", "fix": "patch", "perf": "patch"}.get(commit["type"], "none")


def bump(version, level):
    major, minor, patch = (int(part) for part in (version or "0.0.0").split("."))
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def notes(commits):
    groups = {}
    for commit in commits:
        if commit["undone"]:
            continue
        name = "Breaking changes" if commit["breaking"] else commit["type"] or "Other"
        groups.setdefault(name, []).append(commit)
    lines = []
    for name in ["Breaking changes", *SECTIONS, "Other"]:
        if name not in groups:
            continue
        lines += [f"## {name}", ""]
        for commit in groups[name]:
            scope = f"**{commit['scope']}:** " if commit["scope"] else ""
            lines.append(f"- {scope}{commit['description']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="version to release, without the leading v")
    parser.add_argument("--notes", help="file that receives the release notes")
    args = parser.parse_args()

    previous = previous_version()
    commits = commits_since(previous)
    cancel_reverts(commits)
    major = int((previous or "0.0.0").split(".")[0])
    level = max((increment(c, major) for c in commits), key=LEVELS.get, default="none")

    if args.version:
        if not VERSION.match(args.version):
            sys.exit(f"error: '{args.version}' is not a version of the form X.Y.Z")
        version = args.version
        if previous and tuple(map(int, version.split("."))) <= tuple(map(int, previous.split("."))):
            sys.exit(f"error: {version} is not greater than the previous version {previous}")
    elif level == "none":
        print(f"previous: {previous or 'none'}")
        print("version: none (no change since the previous version affects it)")
        return
    else:
        version = bump(previous, level)

    if git("tag", "--list", f"v{version}").strip():
        sys.exit(f"error: the tag v{version} already exists")

    text = notes(commits)
    if args.notes:
        with open(args.notes, "w") as handle:
            handle.write(text)
    print(f"previous: {previous or 'none'}")
    print(f"increment: {level}")
    print(f"version: {version}")
    print()
    print(text, end="")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as handle:
            handle.write(f"version={version}\n")


if __name__ == "__main__":
    main()
