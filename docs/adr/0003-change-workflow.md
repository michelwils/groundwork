# 0003. Change workflow

**Status:** accepted

## Context

A repository that records decisions and conventions needs its own changes to be traceable: why something changed, what the change was meant to achieve, and when it was considered done. Working directly on `main` leaves no place to state the intent or review the result.

## Decision

We will make every change to the repository through an issue, a branch and a pull request. The only exceptions are the root commit, the fix of a vulnerability that is not public yet, and the pull requests that a bot opens to update dependencies. Those pull requests, such as the ones that update the pinned versions of the tools or the version of groundwork, have no issue and no checklist, they pass the same checks as other pull requests, except that the title of those of Dependabot is not checked, since Dependabot starts it with a capital letter, and a maintainer approves each merge. The fix of a vulnerability that is not public yet is made in the temporary private fork of its security advisory, without a public issue or pull request, as `SECURITY.md` says: the advisory is its record, its test is written first as usual, and its checks run on the machine of the maintainer, since none runs in the fork.

- **Issues:** one issue per change. The title names the outcome. The body gives the context, the deliverables, the acceptance criteria as a plain list, and what is out of scope. Each issue belongs to a milestone.
- **Branches:** one branch per issue, created from `main` and named `<type>/<issue-number>-<issue-title-in-kebab-case>`, where `<type>` is a commit type defined in [ADR 0002](0002-conventional-commits.md), for example `docs/1-bootstrap-the-repository`.
- **Pull requests:** one pull request per issue, from that branch to `main`.
  - The title follows [ADR 0002](0002-conventional-commits.md).
  - The description contains `Closes #<issue-number>` and the acceptance criteria of the issue as a checklist.
  - It stays a draft until every item of the checklist is checked.
  - It is merged by squash, so that `main` stays linear with one commit per issue. The pull request title, followed by the pull request number, becomes the commit title.
  - The branch is deleted after the merge.
- **Repository settings:** these rules rely on settings of the hosting platform, which a repository adopting this workflow must configure. Squash is the only enabled merge method. It uses the pull request title as the commit title and an empty commit body, and the platform appends the pull request number, which links each commit on `main` to its pull request, and the co-author trailers of the squashed commits. Head branches are deleted automatically after the merge. The default branch also has a ruleset, defined in `.github/rulesets/main.json`: changes go through a pull request, the checks of the CI must pass before merging, forced pushes and deletion are blocked, history stays linear, and nobody bypasses it, except for the merge of the fix of a vulnerability that is not public yet, for which the maintainer disables the ruleset and enables it again at once, since the check that it requires cannot run in the temporary private fork. It requires no approving review, since a project may have a single maintainer: the merge by a maintainer is the approval. The script `.github/scripts/apply_settings.py` applies these settings.

## Consequences

- Every change has a stated purpose and a point where it is considered done.
- Acceptance criteria are stated once, in the issue, and checked in the pull request.
- `main` only contains finished issues and dependency updates, and its history is the list of them in the order they were completed.
- A small change still needs an issue and a pull request, which is overhead for a one-line fix.
- The size of an issue sets the size of the pull request, so issues must be kept small enough to review in one pass.
- The commits on a branch are not kept on `main`. They remain visible in the pull request.
- The merge settings and the ruleset live in the hosting platform, not in the repository, even though a file of the repository describes the ruleset. Each repository that adopts the workflow must configure them, and nothing in the repository checks them.
- The fix of a vulnerability that is not public yet reaches `main` while the ruleset is disabled, with checks run on the machine of the maintainer and then on `main`. That window is the cost of keeping the fault private until the fix is merged, and the commit that the platform makes for that merge does not follow [ADR 0002](0002-conventional-commits.md), so the release is given its version.
