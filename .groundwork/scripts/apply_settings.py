#!/usr/bin/env python3
"""Apply the repository settings that groundwork relies on (ADR 0003).

A template copies files, not settings. The script applies, to a repository on GitHub:

- squash as the only merge method, with the pull request title as the commit title, an empty
  commit message, and the deletion of branches after a merge
- private vulnerability reporting, which SECURITY.md relies on
- immutable releases, which apply to the releases published afterwards
- the vulnerability alerts, which also turn on the dependency graph, then the security updates of
  the dependencies, which open a pull request for a vulnerable dependency (ADR 0008)
- the ruleset of .groundwork/rulesets/main.json, last, since it rejects direct pushes: it is updated if
  a ruleset of that name exists and created otherwise

Run it again and the repository stays in the same state. It needs admin rights on the repository,
and the `gh` command, logged in.

Usage: apply_settings.py [OWNER/REPO] [--dry-run]
"""

import argparse
import json
import os
import re
import subprocess
import sys

RULESET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rulesets", "main.json")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class Failure(Exception):
    pass


def gh(*args):
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True)
    except FileNotFoundError:
        raise Failure("the gh command is not installed")
    if result.returncode != 0:
        raise Failure(result.stderr.strip() or f"gh {' '.join(args)} failed")
    return result.stdout


def current_repository():
    return gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner").strip()


def ruleset_name():
    with open(RULESET) as handle:
        return json.load(handle)["name"]


def settings(repository):
    """Return the steps, in the order they are applied, as (description, arguments of gh api)."""
    api = f"repos/{repository}"
    ruleset_id = next((r["id"] for r in json.loads(gh("api", f"{api}/rulesets")) if r["name"] == ruleset_name()), None)
    ruleset = ("-X", "PUT", f"{api}/rulesets/{ruleset_id}") if ruleset_id else ("-X", "POST", f"{api}/rulesets")
    return [
        (
            "merge: squash only, pull request title as commit title, empty message, branches deleted after a merge",
            ("-X", "PATCH", api,
             "-F", "allow_squash_merge=true", "-F", "allow_merge_commit=false", "-F", "allow_rebase_merge=false",
             "-F", "delete_branch_on_merge=true",
             "-f", "squash_merge_commit_title=PR_TITLE", "-f", "squash_merge_commit_message=BLANK"),
        ),
        ("private vulnerability reporting: enabled", ("-X", "PUT", f"{api}/private-vulnerability-reporting")),
        ("immutable releases: enabled", ("-X", "PUT", f"{api}/immutable-releases")),
        ("vulnerability alerts: enabled", ("-X", "PUT", f"{api}/vulnerability-alerts")),
        ("security updates: enabled", ("-X", "PUT", f"{api}/automated-security-fixes")),
        (
            f"ruleset '{ruleset_name()}': {'updated' if ruleset_id else 'created'}",
            (*ruleset, "--input", os.path.abspath(RULESET)),
        ),
    ]


def run(args):
    repository = args.repository or current_repository()
    if not REPOSITORY.match(repository):
        raise Failure(f"'{repository}' is not of the form OWNER/REPO")
    print(f"repository: {repository}")
    try:
        steps = settings(repository)
    except Failure as failure:
        raise Failure(f"could not read the rulesets of {repository}: {failure}. This needs admin rights on the repository.")
    for description, arguments in steps:
        if args.dry_run:
            print(f"would apply {description}")
            continue
        try:
            gh("api", *arguments)
        except Failure as failure:
            raise Failure(
                f"could not apply {description.split(':')[0]} to {repository}: {failure}. "
                "This needs admin rights on the repository."
            )
        print(f"applied {description}")


def main():
    parser = argparse.ArgumentParser(description="Apply the repository settings that groundwork relies on.")
    parser.add_argument("repository", nargs="?", help="OWNER/REPO (default: the repository of the current directory)")
    parser.add_argument("--dry-run", action="store_true", help="show what would be applied, change nothing")
    try:
        run(parser.parse_args())
    except Failure as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
