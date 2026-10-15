# 0006. Trunk-based development

**Status:** accepted

## Context

Work comes in batches. Unfinished work sits next to urgent fixes, and a security fix may have to ship before the next batch is ready. A single `main` with version tags only works if `main` can be released at any time, and if a fix can be released without waiting for work that is not finished. Projects that others depend on may also have to fix versions that are no longer the latest.

## Decision

We will develop on a single long-lived branch, `main`. All other branches are short-lived and merged into it through pull requests.

**Releasable `main`.** Every commit on `main` is in a state that can be released. A pull request is merged only when its checks pass and the acceptance criteria of its issue are met. A change that is broken or half done is never merged.

**Short-lived branches.** A branch lives a few days at most. A change that takes longer is split into several issues, each merged when it is done.

**Unfinished work.** A feature too large for one pull request is split into several issues, each merged as soon as it is done. Until the feature is complete, its changes are dormant: users cannot reach them and they are not part of the public contract, for example because the code is not wired in, or is disabled by configuration. Dormant code is committed with the type `chore`, tests with `test` and documentation with `docs`, never `feat`, so that they do not change the version ([ADR 0005](0005-semantic-versioning-and-releases.md)). The last change, the one that makes the feature reachable, is the `feat` commit. When a feature is switched on by changing a setting at run time, the `feat` commit is the one that changes the default, or the release that switches it on, and the public contract is that of the default configuration. A release therefore only ever contains finished features, and shipping a batch means merging the commits that expose its features.

**Breaking changes.** A breaking change is made in steps whenever possible: the new behaviour is added next to the old one, users move to it, then the old behaviour is removed. Only the removal is a breaking commit, and it carries `!`. A change that cannot be made in steps, such as one forced by an external party, is released as a major version.

**Releasing a fix.** The project states in its README which versions it maintains. By default, only the latest release is maintained. A fix is made on `main` like any other change, with an issue and a pull request, and is released from `main`: as soon as it is merged when it is urgent, otherwise with the next release. If `main` holds a `feat` or a breaking change that must not ship with the fix, it is made dormant again first, by reverting it or by switching it off. A user of an older version updates to receive the fix, unless the project maintains that version.

**Maintained older versions.** A project that maintains an older major version does so on a maintenance branch. A minor increment does not break users ([ADR 0005](0005-semantic-versioning-and-releases.md)), so there is one branch per major version, not per minor version. None is used while the major version is `0`, where nothing is stable.

- The branch is created on demand, never in advance, from the latest tag of that major version, and is named `maintenance/v<major>`.
- The fix is made on `main` first. A backport pull request then applies the fix commit to the maintenance branch. Its branch is created from the maintenance branch and named like the original branch followed by `-v<major>`, for example `fix/12-handle-empty-input-v1`. Its title is the title of the original pull request, without its number, its description contains `Refs #<issue-number>` instead of `Closes`, and it has no checklist, since the issue is already closed. It is merged by squash.
- When the code to fix no longer exists on `main`, the fix is made directly on the maintenance branch, with an issue and a pull request that targets that branch.
- The branch receives fixes only, never a `feat`.
- Its patch version is tagged on the branch with an annotated tag `vMAJOR.MINOR.PATCH`. The release notes list the fixes since the previous tag on the branch, and the release is not marked as the latest one.
- The branch is never merged back into `main`.
- When the project stops maintaining the version, it releases the fixes still waiting, updates its README and deletes the branch. The tags remain.

## Consequences

- A release can be made from `main` at any time, and an urgent fix does not wait for a batch.
- Dormant code is merged before it is used, so `main` temporarily contains code that does nothing. A feature that cannot be kept dormant without a switch needs one, and choosing the switch is left to each project. Switches are removed once the feature is exposed, otherwise they accumulate.
- The commit type of every change matters more: a `feat` that is not the exposing commit makes unfinished work part of the next release. Reviewing the type is part of reviewing a pull request.
- Reviewing a feature is spread across several pull requests, and only the last one shows the feature as a whole.
- A revert does not undo changes already applied to data, and a revert of a released breaking change is itself breaking. Changes to data are therefore made in steps as well.
- Maintaining an older major version doubles the work of every fix, which is applied and released twice. A project should maintain as few as possible.
- With maintenance branches, the latest tag by date is not always the highest version.
- Coordinating a vulnerability fix before it is public is not covered. A rollback is a new fix or a `revert`, made like any other change.
- Nothing checks that `main` is releasable. Doing so automatically is left to later tooling.
