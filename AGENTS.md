# Agent instructions

Rules for coding agents working on this repository. The rules for every contributor are in [`CONTRIBUTING.md`](CONTRIBUTING.md) and in the ADRs in [`docs/adr/`](docs/adr/).

## Before a change

- Read the ADRs that concern the change.
- Follow the workflow, the commit messages and the language rules of `CONTRIBUTING.md`.
- A significant decision is recorded as a new ADR, following [`docs/adr/template.md`](docs/adr/template.md). Propose it instead of deciding.
- For a change that is not trivial, propose a plan (files, tests, risks, open questions) and wait for the approval of a maintainer before you change any file. Record the approved plan in the "Plan" section of the pull request, and stop and report if the work departs from it ([ADR 0007](docs/adr/0007-ai-assisted-changes.md)).
- Write the test of a change of behaviour and see it fail for the expected reason before you write the code ([ADR 0009](docs/adr/0009-test-first-development.md)). Report a test that you could not write first, and why.

## Rules for agents

These rules come from [ADR 0007](docs/adr/0007-ai-assisted-changes.md).

- Commits you make end with a `Co-Authored-By` trailer naming you. Issues and pull requests you write end with a line stating that they were generated, with the name of the tool.
- Never include a link to, or an identifier of, your session or conversation.
- For a change that touches a trust boundary, name in your plan the rule of [ADR 0010](docs/adr/0010-security-of-the-code-of-an-application.md) that applies, and each new dependency.
- Never merge a pull request without the explicit approval of a maintainer for that pull request.
- Report the errors you corrected and the deviations from a rule. Do not report that you followed the rules.
- Check your work before presenting it, committing it or marking a pull request ready, against the [review checklist](CONTRIBUTING.md#review-checklist).
- Never bypass a check: do not skip hooks, disable a rule, or remove or weaken a test to make it pass. When a check fails, fix the cause or report it.
- You may commit, push your own branch, open a draft pull request, and update that pull request and its issue. Ask for explicit approval before any other action that is hard to reverse or reaches beyond them, such as changing repository settings or milestones, deleting a branch or rewriting history.
- Before stating a fact about an external tool or service, check its current documentation, or say that you did not.
- Record a decision taken during the work in the issue or the pull request, or as an ADR when it is significant, not only in the conversation.
- Write the shortest text that stays clear and precise.

## Project

This repository contains documentation, configuration and the scripts, with their tests. Run every check with `pre-commit run --all-files --hook-stage manual` and the tests with `python3 -m unittest discover -s .github/scripts -p 'test_*.py'` before committing. The scripts have dependencies, pinned in `.github/scripts/requirements.txt`: install them once in a virtual environment, with `python3 -m venv .venv && .venv/bin/pip install -r .github/scripts/requirements.txt`, and run the tests with `.venv/bin/python`. The same checks and tests run in CI on every pull request.
