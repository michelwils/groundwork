#!/usr/bin/env python3
"""Open the pull request that moves a project to a later version of groundwork.

It runs update_groundwork.py without an issue, commits the result on the branch
`groundwork/update-to-v<X-Y-Z>`, pushes it and opens the pull request with `gh`. The pull request
has no issue, like those of Dependabot. When files are in conflict, it is a draft that lists them,
and the markers stay in the files for a maintainer to resolve.

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

HERE = os.path.dirname(os.path.abspath(__file__))
UPDATE = os.path.join(HERE, "update_groundwork.py")
VERSION_FILE = ".groundwork-version"
PREFIX = "groundwork/"
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


def added(output):
    """Return the numbers of the ADRs that the update script says it added to the choice."""
    match = re.search(r"^added: (.+)$", output, re.MULTILINE)
    return [number.strip() for number in match.group(1).split(",")] if match else []


def conflicts(output):
    """Return the files that the update script names as in conflict."""
    return re.findall(r"^- (.+)$", output, re.MULTILINE)


def body(old, new, conflicts, source, added=()):
    lines = [f"Moves the project from groundwork {old} to {new}."]
    if source.startswith("https://"):
        lines.append(f"Release notes: {source.removesuffix('.git')}/releases/tag/v{new}")
    if added:
        lines += ["", "These ADRs enter the choice of the project because an ADR it keeps needs them: " + ", ".join(f"ADR {number}" for number in added) + "."]
    if conflicts:
        lines += ["", "These files are in conflict. Resolve the markers, then mark the pull request ready:", ""]
        lines += [f"- `{path}`" for path in conflicts]
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
    command = [sys.executable, UPDATE] + (["--source", args.source] if args.source else [])
    update = subprocess.run(command, capture_output=True, text=True)
    sys.stdout.write(update.stdout)
    if update.returncode == 1:
        sys.stderr.write(update.stderr)
        return 1
    fields = dict(re.findall(r"^(branch|from|to|source): (.+)$", update.stdout, re.MULTILINE))
    if "branch" not in fields:
        return 0  # up to date, the update script said so
    files = conflicts(update.stdout) if update.returncode == 2 else []

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
        "--body", body(old, new, files, fields.get("source", ""), added(update.stdout)),
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
