# 0008. Automated checks

**Status:** accepted

## Context

The conventions of a project, such as the format of commit messages or the rules for changes made with an agent, are only checked by review. Mechanical mistakes are found late and take the time of the reviewer. A check that runs on the contributor's machine can be skipped or missing, so the same checks must also run where nobody can skip them.

## Decision

We will check the repository automatically, in two places, from one configuration.

- **Before each commit.** Checks run on the commit's files and message, on the contributor's machine, through hooks installed from the repository's configuration.
- **In CI.** The same checks run on all files for every pull request and for the main branch. Checks of the pull request are added: its title, since it becomes the commit title on the main branch, and its branch name and closing line, which tie it to its issue.
- **One configuration.** The checks are defined once, in a file of the repository, and each tool is used at a pinned version. Both places therefore run the same checks.
- **A failing check blocks the change.** A commit whose check fails is not made, and a pull request whose check fails is not merged.
- **No bypass.** A check is never skipped or disabled to get a change through, except for the merge of the fix of a vulnerability that is not public yet, which no check can reach. A check that is wrong or too strict is changed or removed in a pull request that explains why.
- **Baseline checks.** Whatever its stack, a project checks the format of its commit messages, the presence of secrets and the format of its documentation. It adds the checks of its own stack to the same configuration.
- **Audit of the dependencies.** A project configures, for its stack, a check that fails when a dependency has a known vulnerability, in the same configuration and in the CI. A project whose stack has no such tool writes the exception and its reason in its `AGENTS.md`.

## Consequences

- Mechanical mistakes are found before the review, which can concentrate on the content.
- Contributors need the tool that runs the hooks. One who does not install it is caught later, by the CI.
- The pinned versions age and are updated by hand, as any other change.
- A check that rejects valid work costs time until it is fixed.
- Rules that need judgement, such as whether the type of a commit is right, stay with the review.
- The condition that a pull request's checks pass before it is merged can be verified.
- A new advisory fails the audit of every pull request until the dependency is updated, which is the intent.
- The audit sees a vulnerability only when a pull request runs it. The platform's alerts and security updates, which the settings script turns on, tell when one is found after the merge.
