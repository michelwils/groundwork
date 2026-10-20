#!/usr/bin/env python3
"""Check the branch name, the closing line and the breaking change of a pull request (ADR 0003, ADR 0006).

The branch is named <type>/<issue-number>-<slug>. The description has `Closes #<issue-number>`.
A backport (base `maintenance/v<major>`, branch ending in `-v<major>`) has `Refs #<issue-number>`
instead, and no `Closes`. Branches of Dependabot (`dependabot/…`) and of the update of groundwork
(`groundwork/…`) are skipped: a project that uses another dependency update bot adds its branch
prefix to BOT_BRANCHES.

When the title has `!` before the colon, the description has a line `BREAKING CHANGE: <text>`: the
maintainer copies it into the body of the squash commit, and the release notes give it (ADR 0003).

Usage: check_pull_request.py BRANCH BASE BODY TITLE
"""

import re
import sys

TYPES = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"]
BRANCH = re.compile(r"^(?:" + "|".join(TYPES) + r")/(?P<issue>[0-9]+)-[a-z0-9]+(?:-[a-z0-9]+)*$")
MAINTENANCE = re.compile(r"^maintenance/v(?P<major>[0-9]+)$")
CLOSES = re.compile(r"\bCloses #([0-9]+)\b")
REFS = re.compile(r"\bRefs #([0-9]+)\b")
BOT_BRANCHES = ("dependabot/", "groundwork/")
BREAKING_TITLE = re.compile(r"^(?:" + "|".join(TYPES) + r")(?:\([a-z]+\))?!: ")
BREAKING_FOOTER = re.compile(r"^BREAKING[ -]CHANGE:[ \t]*\S", re.MULTILINE)


def check(branch, base, body, title):
    """Return the problems of the pull request, empty when it follows the rules."""
    if branch.startswith(BOT_BRANCHES):
        return []
    problems = branch_problems(branch, base, body)
    if BREAKING_TITLE.match(title) and not BREAKING_FOOTER.search(body or ""):
        problems.append("The title has `!`: the description has no line `BREAKING CHANGE: <what breaks and how to migrate>`.")
    return problems


def branch_problems(branch, base, body):
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
    if len(sys.argv) != 5:
        print(__doc__, file=sys.stderr)
        return 2
    problems = check(*sys.argv[1:])
    for problem in problems:
        print(f"error: {problem}", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
