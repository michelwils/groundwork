# Agent instructions

Rules for coding agents working on this repository. The rules for every contributor are in [`CONTRIBUTING.md`](CONTRIBUTING.md) and in the ADRs in [`docs/adr/`](docs/adr/).

## Before a change

- Read the ADRs that concern the change.
- Follow the rules of `CONTRIBUTING.md`.
<!-- groundwork:0001 -->
- A significant decision is recorded as a new ADR, following [`docs/adr/template.md`](docs/adr/template.md). Propose it instead of deciding.
<!-- /groundwork -->
- For a change that is not trivial, propose a plan (files, tests, risks, open questions) and wait for a maintainer's approval before you change any file. Record the approved plan in the "Plan" section of the pull request, and stop and report if the work departs from it ([ADR 0007](docs/adr/0007-ai-assisted-changes.md)).
<!-- groundwork:0009 -->
- Write the test of a change of behaviour and see it fail for the expected reason before you write the code ([ADR 0009](docs/adr/0009-test-first-development.md)). Report a test that you could not write first, and why.
<!-- /groundwork -->

## Rules for agents

These rules come from [ADR 0007](docs/adr/0007-ai-assisted-changes.md).

- Commits you make end with a `Co-Authored-By` trailer naming you. Issues and pull requests you write end with a line stating that they were generated, with the name of the tool.
- Never include a link to, or an identifier of, your session or conversation.
- For a change that touches a trust boundary, name in your plan the security rule or principle that applies, and each new dependency with its license, in your plan and in the pull request.
<!-- groundwork:0010 -->
- The security rules for the code are in [ADR 0010](docs/adr/0010-security-of-the-code-of-an-application.md).
<!-- /groundwork -->
<!-- groundwork:0011 -->
- The principles for confidential and personal data are in [ADR 0011](docs/adr/0011-protection-of-confidential-and-personal-data.md).
<!-- /groundwork -->
<!-- groundwork:0015 -->
- The principles for the logs and the diagnostic of an application are in [ADR 0015](docs/adr/0015-logs-and-diagnostic-of-an-application.md).
<!-- /groundwork -->
<!-- groundwork:0013 -->
- The licenses accepted for the dependencies are those that the project states, as [ADR 0013](docs/adr/0013-licenses-of-the-dependencies.md) asks.
<!-- /groundwork -->
<!-- groundwork:0014 -->
- In a project with a `.groundwork-version`, change a file of groundwork only through the update, except the lines that belong to the project, which go where [ADR 0008](docs/adr/0008-automated-checks.md) says and outside the blocks of shared files. A protected file is not locked: a change to it needs the review of an owner ([ADR 0014](docs/adr/0014-protecting-the-files-of-groundwork-in-a-project.md)).
<!-- /groundwork -->
- Never merge a pull request without a maintainer's explicit approval for that pull request.
- Report the errors you corrected and the deviations from a rule. Do not report that you followed the rules.
- Check your work before presenting it, committing it or marking a pull request ready, against the [review checklist](CONTRIBUTING.md#review-checklist).
- Never bypass a check: do not skip hooks, disable a rule, or remove or weaken a test to make it pass. When a check fails, fix the cause or report it.
- You may commit, push your own branch, open a draft pull request, and update that pull request and its issue. Ask for explicit approval before any other action that is hard to reverse or reaches beyond them, such as changing repository settings or milestones, deleting a branch or rewriting history.
- Before stating a fact about an external tool or service, check its current documentation, or say that you did not.
- Record a decision taken during the work in the issue or the pull request, or as an ADR when it is significant, not only in the conversation.
- Write the shortest text that stays clear and precise.

## Project

The project's commands, layout and checks. The README of groundwork describes groundwork in its own section, and a project writes its own here.
