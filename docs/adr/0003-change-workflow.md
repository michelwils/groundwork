# 0003. Change workflow

**Status:** accepted

## Context

A repository that records decisions and conventions needs its own changes to be traceable: why something changed, what the change was meant to achieve, and when it was considered done. Working directly on `main` leaves no place to state the intent or review the result.

## Decision

We will make every change to the repository through an issue, a branch and a pull request. The only exception is the root commit.

- **Issues:** one issue per change. The title names the outcome. The body gives the context, the deliverables, the acceptance criteria as a plain list, and what is out of scope. Each issue belongs to a milestone.
- **Branches:** one branch per issue, created from `main` and named `<type>/<issue-number>-<issue-title-in-kebab-case>`, where `<type>` is a commit type defined in [ADR 0002](0002-conventional-commits.md), for example `docs/1-bootstrap-the-repository`.
- **Pull requests:** one pull request per issue, from that branch to `main`. The only exception is the backport of a fix to a maintained older version, described in [ADR 0006](0006-trunk-based-development.md).
  - The title follows [ADR 0002](0002-conventional-commits.md).
  - The description contains `Closes #<issue-number>` and the acceptance criteria of the issue as a checklist.
  - It stays a draft until every item of the checklist is checked.
  - It is merged by squash, so that `main` stays linear with one commit per issue. The pull request title, followed by the pull request number, becomes the commit title.
  - The branch is deleted after the merge.
- **Backports:** a fix for a maintained older version follows these rules with the exceptions defined in [ADR 0006](0006-trunk-based-development.md): its pull request targets a maintenance branch, refers to the issue instead of closing it, and has no checklist.
- **Repository settings:** these rules rely on settings of the hosting platform, which a repository adopting this workflow must configure. Squash is the only enabled merge method. It uses the pull request title as the commit title and an empty commit body. The platform appends the pull request number to the title, which links each commit on `main` to its pull request, and adds the co-author trailers of the squashed commits. Head branches are deleted automatically after the merge.

## Consequences

- Every change has a stated purpose and a point where it is considered done.
- Acceptance criteria are stated once, in the issue, and checked in the pull request.
- `main` only contains finished issues, and its history is the list of issues in the order they were completed.
- A small change still needs an issue and a pull request, which is overhead for a one-line fix.
- The size of an issue sets the size of the pull request, so issues must be kept small enough to review in one pass.
- The commits on a branch are not kept on `main`. They remain visible in the pull request.
- The merge settings live in the hosting platform, not in the repository, so each repository that adopts the workflow must configure them and nothing in the repository checks them.
