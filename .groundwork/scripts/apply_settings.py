#!/usr/bin/env python3
"""Apply the repository settings that groundwork relies on (ADR 0003).

A template copies files, not settings. The script applies, to a repository on GitHub:

- squash as the only merge method, with the pull request title as the commit title, an empty
  commit message, and the deletion of branches after a merge
- private vulnerability reporting, which SECURITY.md relies on. GitHub offers it on public repositories only, so on a
  private or internal repository the script skips it, says so, and applies the rest
- immutable releases, which apply to the releases published afterwards
- the vulnerability alerts, which also turn on the dependency graph, then the security updates of
  the dependencies, which open a pull request for a vulnerable dependency (ADR 0008)
- the ruleset of .groundwork/rulesets/main.json, last, since it rejects direct pushes: it is updated if
  a ruleset of that name exists and created otherwise. With --code-owner-review, it also requires at least one approval
  (never fewer than the ruleset already has), the approval of a code owner (CODEOWNERS) for the files that have one, and
  dismisses an approval when a commit is pushed after it; with --last-push-approval, the approval must come from someone
  other than the person who pushed last (ADR 0014). The options are not remembered: a run without them applies the ruleset
  of the file, which requires no approval, and stops when that would lower an approval setting of the ruleset of the
  repository, unless --turn-off-reviews is given. --code-owner-review needs a file of code owners, run from the directory
  of the project, and stops when the only owner is the person who runs the script, since nobody else could approve;
  --last-push-approval needs --code-owner-review

Run it again and the repository stays in the same state. It needs admin rights on the repository,
and the `gh` command, logged in.

Usage: apply_settings.py [OWNER/REPO] [--dry-run] [--code-owner-review] [--last-push-approval] [--turn-off-reviews]
"""

from __future__ import annotations

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


class Refused(Failure):
    """An answer of the platform, with the HTTP status that gh prints at the end of its error, or None."""

    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def gh(*args, input=None):
    try:
        result = subprocess.run(["gh", *args], capture_output=True, text=True, input=input)
    except FileNotFoundError:
        raise Failure("the gh command is not installed")
    if result.returncode != 0:
        message = result.stderr.strip() or f"gh {' '.join(args)} failed"
        statuses = re.findall(r"\(HTTP ([0-9]{3})\)", message)  # the last one: gh may add a hint after it
        raise Refused(message, int(statuses[-1]) if statuses else None)
    return result.stdout


def rights(failure):
    """Return the sentence about admin rights when the platform refused with HTTP 403, else nothing: any other answer is
    shown as it is, since it does not tell that the rights are missing. A 403 is not a proof either, since the platform
    also answers it for a token that lacks a scope, so the sentence names the token too."""
    if isinstance(failure, Refused) and failure.status == 403:
        return ". This needs admin rights on the repository, and a token that may use them."
    return ""


def current_repository():
    return gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner").strip()


def ruleset_name():
    with open(RULESET) as handle:
        return json.load(handle)["name"]


def check_owners():
    """Stop when the directory has no file of code owners, or one without an owner or with the owner of the template: the
    requirement would do nothing, or no one could approve. GitHub reads the first of these files that exists. Return the
    owners that the file names."""
    for path in (os.path.join(".github", "CODEOWNERS"), "CODEOWNERS", os.path.join("docs", "CODEOWNERS")):
        if os.path.exists(path):
            with open(path, errors="replace") as handle:
                rules = [line.split("#")[0].split() for line in handle]
            rules = [fields for fields in rules if fields]
            if not rules:
                raise Failure(
                    f"{path} names no owner: add the rules of the template, with the reviewers of the project."
                )
            if not any(len(fields) > 1 for fields in rules):
                raise Failure(f"{path} names no owner: a line gives a pattern and the reviewers of the project.")
            if any("@OWNER" in fields for fields in rules):
                raise Failure(
                    f"{path} still names @OWNER, the owner of the template: replace it with the reviewers of the project."
                )
            return {owner for fields in rules for owner in fields[1:]}
    raise Failure(
        "this directory has no file of code owners (.github/CODEOWNERS, CODEOWNERS or docs/CODEOWNERS): run the script from the clone of the project, "
        "after copying .groundwork/CODEOWNERS.template to .github/CODEOWNERS and replacing @OWNER."
    )


def check_not_alone(owners):
    """Stop when the only code owner is the person who runs the script: with an approval required, nobody else could
    approve their pull requests. A team, an address or any other owner leaves the choice to the project, and a login
    that cannot be read stops nothing, and the script says that it skipped the check."""
    try:
        login = gh("api", "user", "--jq", ".login").strip()
    except Failure as failure:
        print(f"skipped the check that you are not the only code owner: could not read your login: {failure}")
        return
    if login and {owner.lower() for owner in owners} == {"@" + login.lower()}:
        raise Failure(
            f"the only code owner is @{login}, who runs this script: nobody else could approve a pull request, and with an approval "
            "required none could be merged. Add a reviewer to the file of code owners, or do not turn the option on (ADR 0014, Single maintainer)."
        )


def protected(code_owner_review: bool, last_push_approval: bool, approvals: int = 0) -> tuple[dict, list[str]]:
    """Return the ruleset of the file with the approvals that the options ask for, and the words that tell them.
    `approvals` is the number of approvals that the ruleset of the repository requires: the options never lower it."""
    with open(RULESET) as handle:
        ruleset = json.load(handle)
    if not (code_owner_review or last_push_approval):
        return ruleset, []
    parameters = next((rule["parameters"] for rule in ruleset["rules"] if rule["type"] == "pull_request"), None)
    if parameters is None:
        raise Failure(f"{os.path.relpath(RULESET)} has no rule of type pull_request: the approvals cannot be required.")
    words = []
    if code_owner_review:
        count = max(1, approvals)
        parameters.update(
            required_approving_review_count=count, require_code_owner_review=True, dismiss_stale_reviews_on_push=True
        )
        words += [
            f"{count} approval{'s' if count > 1 else ''} required",
            "code owner review required",
            "stale approvals dismissed",
        ]
    if last_push_approval:
        parameters["require_last_push_approval"] = True
        words.append("last push approval required")
    return ruleset, words


APPROVALS = (
    ("require_code_owner_review", "code owner review"),
    ("require_last_push_approval", "last push approval"),
    ("dismiss_stale_reviews_on_push", "dismissal of stale approvals"),
    ("required_review_thread_resolution", "thread resolution"),
)


def pull_request_parameters(ruleset):
    return next(
        (rule.get("parameters") or {} for rule in ruleset.get("rules") or [] if rule.get("type") == "pull_request"), {}
    )


def lowered(detail, wanted):
    """Return the approval settings that the ruleset on the platform has and that the wanted ruleset would lower."""
    current, wanted = pull_request_parameters(detail), pull_request_parameters(wanted)
    names = [name for key, name in APPROVALS if current.get(key) and not wanted.get(key)]
    if (current.get("required_approving_review_count") or 0) > (wanted.get("required_approving_review_count") or 0):
        names.append("required approvals")
    return names


def ruleset_on_the_platform(api):
    """Return the id of the ruleset of the file's name on the platform, or None, and its detail, or {}."""
    ruleset_id = next((r["id"] for r in json.loads(gh("api", f"{api}/rulesets")) if r["name"] == ruleset_name()), None)
    if not ruleset_id:
        return None, {}
    try:
        return ruleset_id, json.loads(gh("api", f"{api}/rulesets/{ruleset_id}") or "{}")
    except ValueError as error:
        raise Failure(f"the platform answered something that is not JSON: {error}")


def reporting_step(api, visibility):
    """Return the step that enables private vulnerability reporting, or a skipped step, with no arguments, on a private
    or internal repository."""
    if visibility not in ("private", "internal"):
        return ("private vulnerability reporting: enabled", ("-X", "PUT", f"{api}/private-vulnerability-reporting"))
    return (
        f"private vulnerability reporting: GitHub offers it on public repositories only, and this one is {visibility}",
        None,
    )


def ruleset_step(api, ruleset_id, wanted, words, asks_reviews):
    """Return the step that creates or updates the ruleset: the file itself when no review option is given, else the
    ruleset that the options ask for, on the standard input."""
    target = ("-X", "PUT", f"{api}/rulesets/{ruleset_id}") if ruleset_id else ("-X", "POST", f"{api}/rulesets")
    if asks_reviews:
        file, text, stdin = "-", f" ({', '.join(words)})", json.dumps(wanted)
    else:
        file, text, stdin = os.path.abspath(RULESET), "", None
    return (
        f"ruleset '{ruleset_name()}': {'updated' if ruleset_id else 'created'}{text}",
        (*target, "--input", file),
        stdin,
    )


def settings(repository, code_owner_review=False, last_push_approval=False, visibility="public"):
    """Return the steps, in the order they are applied, as (description, arguments of gh api, standard input of gh),
    and the approval settings of the ruleset on the platform that this run would lower. A step without arguments is
    skipped. Private vulnerability reporting is one for a repository that is not public."""
    api = f"repos/{repository}"
    ruleset_id, detail = ruleset_on_the_platform(api)
    approvals = pull_request_parameters(detail).get("required_approving_review_count") or 0
    wanted, words = protected(code_owner_review, last_push_approval, approvals)
    turned_off = lowered(detail, wanted) if ruleset_id else []
    steps = [
        (
            "merge: squash only, pull request title as commit title, empty message, branches deleted after a merge",
            (
                "-X",
                "PATCH",
                api,
                "-F",
                "allow_squash_merge=true",
                "-F",
                "allow_merge_commit=false",
                "-F",
                "allow_rebase_merge=false",
                "-F",
                "delete_branch_on_merge=true",
                "-f",
                "squash_merge_commit_title=PR_TITLE",
                "-f",
                "squash_merge_commit_message=BLANK",
            ),
        ),
        reporting_step(api, visibility),
        ("immutable releases: enabled", ("-X", "PUT", f"{api}/immutable-releases")),
        ("vulnerability alerts: enabled", ("-X", "PUT", f"{api}/vulnerability-alerts")),
        ("security updates: enabled", ("-X", "PUT", f"{api}/automated-security-fixes")),
        ruleset_step(api, ruleset_id, wanted, words, code_owner_review or last_push_approval),
    ]
    return steps, turned_off


def check_options(args):
    """Stop, before any call that writes, on options that go wrong together or that the files of the project refuse."""
    if args.last_push_approval and not args.code_owner_review:
        raise Failure(
            "--last-push-approval goes with --code-owner-review: with no approval required, it enforces nothing."
        )
    protected(args.code_owner_review, args.last_push_approval)  # stops here when the file has no pull_request rule
    if args.code_owner_review:
        check_not_alone(check_owners())


def apply_steps(steps, repository, dry_run):
    for description, arguments, *stdin in steps:
        if arguments is None:
            print(f"{'would skip' if dry_run else 'skipped'} {description}")
            continue
        if dry_run:
            print(f"would apply {description}")
            continue
        try:
            gh("api", *arguments, input=stdin[0] if stdin else None)
        except Failure as failure:
            raise Failure(f"could not apply {description.split(':')[0]} to {repository}: {failure}{rights(failure)}")
        print(f"applied {description}")


def run(args: argparse.Namespace) -> None:
    repository = args.repository or current_repository()
    if not REPOSITORY.match(repository):
        raise Failure(f"'{repository}' is not of the form OWNER/REPO")
    check_options(args)
    print(f"repository: {repository}")
    try:
        visibility = gh("api", f"repos/{repository}", "--jq", ".visibility").strip()
    except Failure as failure:
        raise Failure(f"could not read {repository}: {failure}")
    try:
        steps, turned_off = settings(repository, args.code_owner_review, args.last_push_approval, visibility)
    except Failure as failure:
        raise Failure(f"could not read the rulesets of {repository}: {failure}{rights(failure)}")
    if turned_off and not args.turn_off_reviews:
        raise Failure(
            f"the ruleset '{ruleset_name()}' of {repository} has {' and '.join(turned_off)}, and this run would lower it. "
            "Give the same options to keep it, or --turn-off-reviews to lower it."
        )
    apply_steps(steps, repository, args.dry_run)


def main():
    parser = argparse.ArgumentParser(description="Apply the repository settings that groundwork relies on.")
    parser.add_argument("repository", nargs="?", help="OWNER/REPO (default: the repository of the current directory)")
    parser.add_argument("--dry-run", action="store_true", help="show what would be applied, change nothing")
    parser.add_argument(
        "--code-owner-review",
        action="store_true",
        help="require at least one approval, the approval of a code owner for the files that have one, and dismiss an approval when a commit is pushed after it (ADR 0014)",
    )
    parser.add_argument(
        "--turn-off-reviews",
        action="store_true",
        help="apply the ruleset even if it lowers an approval setting of the ruleset of the repository",
    )
    parser.add_argument(
        "--last-push-approval",
        action="store_true",
        help="with --code-owner-review, require that the approval comes from someone other than the person who pushed last (ADR 0014)",
    )
    try:
        run(parser.parse_args())
    except Failure as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
