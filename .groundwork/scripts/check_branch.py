#!/usr/bin/env python3
"""Check the name of the current branch before a commit (ADR 0003).

The branch is named <type>/<issue-number>-<slug>, the rule that `check_pull_request.py` applies to the
pull request, so that a wrongly named branch is caught at its first commit and not once its pull request
is open. Nothing is checked on `main`, on a maintenance branch (`maintenance/v<major>`), on the branches
of the bots, which `check_pull_request.py` skips, when HEAD is detached (a rebase, the CI), or when the
directory is not a git repository.

Usage: check_branch.py
"""

from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_pull_request  # noqa: E402

DEFAULT_BRANCH = "main"


def current_branch() -> str | None:
    """Return the name of the current branch, None when HEAD is detached or this is not a repository."""
    result = subprocess.run(["git", "symbolic-ref", "--short", "-q", "HEAD"], capture_output=True, text=True)
    return result.stdout.strip() or None if result.returncode == 0 else None


def problem(branch: str | None) -> str | None:
    """Return what is wrong with the branch, None when nothing is to be checked or the name is right."""
    if branch is None or branch == DEFAULT_BRANCH or check_pull_request.MAINTENANCE.match(branch):
        return None
    found = check_pull_request.name_problem(branch)
    if found:
        return f"{found} Rename it with `git branch -m <type>/<issue-number>-<slug>`."
    return None


def main() -> int:
    found = problem(current_branch())
    if found:
        print(f"error: {found}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
