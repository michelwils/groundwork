#!/usr/bin/env python3
"""Check the branch name and the closing line of a pull request (ADR 0003, ADR 0006).

The branch is named <type>/<issue-number>-<slug>. The description has `Closes #<issue-number>`.
A backport (base `maintenance/v<major>`, branch ending in `-v<major>`) has `Refs #<issue-number>`
instead, and no `Closes`. Branches of dependency update bots are skipped.

Usage: check_pull_request.py BRANCH BASE BODY
"""

import re
import sys

TYPES = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"]
BRANCH = re.compile(r"^(?:" + "|".join(TYPES) + r")/(?P<issue>[0-9]+)-[a-z0-9]+(?:-[a-z0-9]+)*$")
MAINTENANCE = re.compile(r"^maintenance/v(?P<major>[0-9]+)$")
CLOSES = re.compile(r"\bCloses #([0-9]+)\b")
REFS = re.compile(r"\bRefs #([0-9]+)\b")
BOT_BRANCH = "dependabot/"


def check(branch, base, body):
    """Return the problems of the pull request, empty when it follows the rules."""
    if branch.startswith(BOT_BRANCH):
        return []
    match = BRANCH.match(branch)
    if not match:
        return [f"The branch '{branch}' is not named <type>/<issue-number>-<slug>, with a type of ADR 0002 and a slug in kebab case."]
    issue = match.group("issue")
    closes = CLOSES.findall(body or "")
    refs = REFS.findall(body or "")
    maintenance = MAINTENANCE.match(base)
    if maintenance and branch.endswith(f"-v{maintenance.group('major')}"):
        problems = []
        if closes:
            problems.append("A backport has `Refs #<issue-number>` instead of `Closes`.")
        if issue not in refs:
            problems.append(f"The description of a backport has no `Refs #{issue}`, the issue of the branch.")
        return problems
    if not closes:
        return [f"The description has no `Closes #{issue}`, the issue of the branch."]
    if any(number != issue for number in closes):
        return [f"The description closes an issue other than #{issue}, the issue of the branch."]
    return []


def main():
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    problems = check(*sys.argv[1:])
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
