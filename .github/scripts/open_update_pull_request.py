#!/usr/bin/env python3
"""Open the pull request that moves a project to a later version of groundwork (ADR 0003).

It runs update_groundwork.py without an issue, commits the result on the branch
`groundwork/update-to-v<X-Y-Z>`, pushes it and opens the pull request with `gh`. The pull request
has no issue, like those of Dependabot. When files are in conflict, it is a draft that lists them,
and the markers stay in the files for a maintainer to resolve.

It opens nothing when the project is up to date, when a pull request from a branch `groundwork/…`
is already open, or when the project has no `.groundwork-version`. The branch of an earlier run that
has no pull request is replaced.

Usage: open_update_pull_request.py [--source URL]
"""

import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from update_groundwork import SOURCE  # noqa: E402

UPDATE = os.path.join(HERE, "update_groundwork.py")
VERSION_FILE = ".groundwork-version"
PREFIX = "groundwork/"
IDENTITY = ["-c", "user.name=github-actions[bot]", "-c", "user.email=41898282+github-actions[bot]@users.noreply.github.com"]


class Failure(Exception):
    pass


def run(*command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise Failure(f"{' '.join(command[:3])} failed: {result.stderr.strip()}")
    return result.stdout


def open_update_exists():
    pulls = json.loads(run("gh", "pr", "list", "--state", "open", "--limit", "1000", "--json", "headRefName"))
    return any(pull["headRefName"].startswith(PREFIX) for pull in pulls)


def body(old, new, conflicts, source):
    lines = [f"Moves the project from groundwork {old} to {new}."]
    if source.startswith("https://"):
        lines.append(f"Release notes: {source.removesuffix('.git')}/releases/tag/v{new}")
    if conflicts:
        lines += ["", "These files are in conflict. Resolve the markers, then mark the pull request ready:", ""]
        lines += [f"- `{path}`" for path in conflicts]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Open the pull request that updates the project to a later groundwork.")
    parser.add_argument("--source", default=None, help="repository of groundwork, as for update_groundwork.py")
    args = parser.parse_args()
    if not os.path.exists(VERSION_FILE):
        print(f"No {VERSION_FILE} in this repository: nothing to update.")
        return 0
    if open_update_exists():
        print(f"An update pull request from a branch {PREFIX}… is already open.")
        return 0

    command = [sys.executable, UPDATE] + (["--source", args.source] if args.source else [])
    update = subprocess.run(command, capture_output=True, text=True)
    sys.stdout.write(update.stdout)
    if update.returncode == 1:
        sys.stderr.write(update.stderr)
        return 1
    fields = dict(re.findall(r"^(branch|from|to): (.+)$", update.stdout, re.MULTILINE))
    if "branch" not in fields:
        return 0  # up to date, the update script said so
    conflicts = re.findall(r"^- (.+)$", update.stdout, re.MULTILINE) if update.returncode == 2 else []

    branch, old, new = fields["branch"], fields["from"], fields["to"]
    title = f"chore: update groundwork to v{new}"
    run("git", "add", "-A")
    run("git", *IDENTITY, "commit", "-q", "-m", title)
    run("git", "push", "--force", "-q", "origin", f"HEAD:refs/heads/{branch}")

    url = run(
        "gh", "pr", "create", "--head", branch, "--title", title,
        "--body", body(old, new, conflicts, args.source or SOURCE),
        *(["--draft"] if conflicts else []),
    ).strip()
    print(url)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Failure as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(1)
