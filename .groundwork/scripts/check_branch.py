#!/usr/bin/env python3
"""Check the name of the current branch before a commit (ADR 0003).

The branch is named <type>/<issue-number>-<slug>, the rule that `check_pull_request.py` applies to the
pull request, so that a wrongly named branch is caught at its first commit and not once its pull request
is open. Nothing is checked on the default branch (`main`, `master` or the one that `origin/HEAD` names),
on a maintenance branch (`maintenance/v<major>`), on the branches of the bots, which
`check_pull_request.py` skips, when HEAD is detached (a rebase, the CI), or when the directory is not a
git repository, or git is not installed.

Usage: check_branch.py
"""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_pull_request  # noqa: E402

DEFAULT_BRANCHES = {"main", "master"}


def git(*arguments: str) -> str | None:
    """Return what a git command prints, None when it fails or git is not installed."""
    try:
        result = subprocess.run(["git", *arguments], capture_output=True, text=True)
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def current_branch() -> str | None:
    """Return the name of the current branch, None when HEAD is detached or this is not a repository."""
    return git("symbolic-ref", "--short", "-q", "HEAD") or None


def default_branches() -> set[str]:
    """Return the names of the default branch: the usual ones, and the one that the remote names."""
    remote = git("symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD") or ""
    return DEFAULT_BRANCHES | {remote.removeprefix("origin/")} - {""}


def problem(branch: str | None, defaults: set[str] = DEFAULT_BRANCHES) -> str | None:
    """Return what is wrong with the branch, None when nothing is to be checked or the name is right."""
    if branch is None or branch in defaults or check_pull_request.MAINTENANCE.match(branch):
        return None
    found = check_pull_request.name_problem(branch)
    if found:
        return f"{found} Rename it with `git branch -m <type>/<issue-number>-<slug>`."
    return None


def main() -> int:
    found = problem(current_branch(), default_branches())
    if found:
        print(f"error: {found}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
