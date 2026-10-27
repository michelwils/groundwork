#!/usr/bin/env python3
"""Open the pull request that moves a project to a later version of groundwork.

It runs update_groundwork.py without an issue, commits the result on the branch
`groundwork/update-to-v<X-Y-Z>`, pushes it and opens the pull request with `gh`. The pull request
has no issue, like those of Dependabot. When files are in conflict, it is a draft that lists them,
and the markers stay in the files for a maintainer to resolve.

It reads the result of the update from a JSON file that update_groundwork.py writes (ADR 1003), not from the text it prints.

It opens nothing when the project is up to date, when a pull request from a branch `groundwork/…`
is already open, when the pull request of that version was closed without being merged, or when the
project has no `.groundwork-version`. A later version is proposed again. The branch of an earlier
run that has no pull request is replaced.

Git runs no hook, neither in this script nor in the update: the files of the source are not reviewed yet,
and the job holds a token that can push.

Usage: open_update_pull_request.py [--source URL]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UPDATE = os.path.join(HERE, "update_groundwork.py")
VERSION_FILE = ".groundwork-version"
PREFIX = "groundwork/"
FIELDS = ("branch", "from", "to", "source", "added", "conflicts")
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
ADR_NUMBER = re.compile(r"[0-9]{4}")
IDENTITY = ["-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com"]


class Failure(Exception):
    pass


def without_hooks(environ):
    """Return the environment in which git runs no hook, with the configuration already given in it."""
    count = int(environ.get("GIT_CONFIG_COUNT", "0"))
    return {**environ, "GIT_CONFIG_COUNT": str(count + 1), f"GIT_CONFIG_KEY_{count}": "core.hooksPath", f"GIT_CONFIG_VALUE_{count}": os.devnull}


def run(*command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise Failure(f"{' '.join(command[:3])} failed: {result.stderr.strip()}")
    return result.stdout


def pull_requests(state):
    return json.loads(run("gh", "pr", "list", "--state", state, "--limit", "1000", "--json", "headRefName,mergedAt"))


def open_update_exists():
    return any(pull["headRefName"].startswith(PREFIX) for pull in pull_requests("open"))


def rejected(branch):
    """Return True when a pull request from the branch was closed without being merged."""
    return any(pull["headRefName"] == branch and not pull["mergedAt"] for pull in pull_requests("closed"))


def undo(branch, current, commit):
    """Leave the project as it was before the update script prepared the branch: on its branch, or detached."""
    run("git", "reset", "--hard", "-q")
    run("git", "clean", "-fdq")
    run("git", "switch", "-q", *([current] if current else ["--detach", commit]))
    run("git", "branch", "-q", "-D", branch)


def result(path):
    """Return the result that the update script wrote to the file, or None when it wrote none: the project is up to date.
    It holds the strings branch, from, to and source, the list added of numbers of four digits and the list conflicts of
    paths, and no other field. The branch is the one of the version."""
    try:
        with open(path) as handle:
            fields = json.load(handle)
    except FileNotFoundError:
        return None
    except ValueError as error:
        raise Failure(f"The update script wrote a result that is not JSON: {error}.")
    if not isinstance(fields, dict) or set(fields) != set(FIELDS):
        raise Failure(f"The update script wrote an unexpected result: {fields!r}.")
    for name in ("branch", "from", "to", "source"):
        if not isinstance(fields[name], str):
            raise Failure(f"The update script wrote an unexpected result: {name} is not a string.")
    for name in ("added", "conflicts"):
        if not isinstance(fields[name], list) or not all(isinstance(item, str) for item in fields[name]):
            raise Failure(f"The update script wrote an unexpected result: {name} is not a list of strings.")
    if (
        not all(VERSION.fullmatch(fields[name]) for name in ("from", "to"))
        or fields["branch"] != f"{PREFIX}update-to-v{fields['to'].replace('.', '-')}"
        or not all(ADR_NUMBER.fullmatch(number) for number in fields["added"])
    ):
        raise Failure(f"The update script wrote an unexpected result: {fields!r}.")
    return fields


def agree(status, fields):
    """Check that the status of the update says what its result says: 3 when files are in conflict, 0 when none is."""
    if status != (3 if fields["conflicts"] else 0):
        raise Failure(f"The update script ended with status {status} and a result with {len(fields['conflicts'])} files in conflict.")


def code(text):
    """Return the text as a code span that holds all of it: a fence of backticks longer than any run in the text, and a
    space on each side when the text starts or ends with a backtick or a space. Nothing in a code span is read as Markdown."""
    fence = "`" * (max(map(len, re.findall("`+", text)), default=0) + 1)
    pad = " " if text[:1] in ("`", " ") or text[-1:] in ("`", " ") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def body(old, new, conflicts, source, added=()):
    lines = [f"Moves the project from groundwork {old} to {new}."]
    if source.startswith("https://"):
        lines.append(f"Release notes: {source.removesuffix('.git')}/releases/tag/v{new}")
    if added:
        lines += ["", "These ADRs enter the choice of the project because an ADR it keeps needs them: " + ", ".join(f"ADR {number}" for number in added) + "."]
    if conflicts:
        lines += ["", "These files are in conflict. Resolve the markers, then mark the pull request ready:", ""]
        lines += [f"- {code(path)}" for path in conflicts]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Open the pull request that updates the project to a later groundwork.")
    parser.add_argument("--source", default=None, help="repository of groundwork, as for update_groundwork.py")
    args = parser.parse_args()
    os.environ.update(without_hooks(os.environ))
    if not os.path.exists(VERSION_FILE):
        print(f"No {VERSION_FILE} in this repository: nothing to update.")
        return 0
    if open_update_exists():
        print(f"An update pull request from a branch {PREFIX}… is already open.")
        return 0

    current = run("git", "branch", "--show-current").strip()
    commit = run("git", "rev-parse", "HEAD").strip()
    with tempfile.TemporaryDirectory() as directory:  # outside the working tree, so that the commit cannot hold it
        file = os.path.join(directory, "result.json")
        command = [sys.executable, UPDATE, "--result", file] + (["--source", args.source] if args.source else [])
        update = subprocess.run(command, capture_output=True, text=True)
        sys.stdout.write(update.stdout)
        sys.stderr.write(update.stderr)
        if update.returncode == 1:
            return 1
        fields = result(file)
    if fields is None:
        if update.returncode != 0:
            raise Failure(f"The update script ended with status {update.returncode} and wrote no result.")
        return 0  # up to date, the update script said so
    agree(update.returncode, fields)
    files = fields["conflicts"]

    branch, old, new = fields["branch"], fields["from"], fields["to"]
    if rejected(branch):
        undo(branch, current, commit)
        print(f"The pull request of groundwork {new} was closed without being merged: not proposed again.")
        return 0
    title = f"chore: update groundwork to v{new}"
    run("git", "add", "-A")
    run("git", *IDENTITY, "commit", "-q", "-m", title)
    run("git", "push", "--force", "-q", "origin", f"HEAD:refs/heads/{branch}")

    url = run(
        "gh", "pr", "create", "--head", branch, "--title", title,
        "--body", body(old, new, files, fields["source"], fields["added"]),
        *(["--draft"] if files else []),
    ).strip()
    print(url)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Failure as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(1)
