# 0003. Change workflow

**Status:** accepted

## Context

A repository that records decisions and conventions needs its own changes to be traceable: why something changed, what the change was meant to achieve, and when it was considered done. Working directly on `main` leaves no place to state the intent or review the result.

## Decision

We will make every change to the repository through an issue, a branch and a pull request. The only exception is the root commit.

- **Issues:** one issue per change. The title names the outcome. The body gives the context, the deliverables, the acceptance criteria and what is out of scope. Each issue belongs to a milestone.
- **Branches:** one branch per issue, created from `main` and named `<type>/<issue-number>-<issue-title-in-kebab-case>`, where `<type>` is a commit type defined in [ADR 0002](0002-conventional-commits.md), for example `docs/1-bootstrap-the-repository`.
- **Pull requests:** one pull request per issue, from that branch to `main`.
  - The title follows [ADR 0002](0002-conventional-commits.md).
  - The description contains `Closes #<issue-number>`.
  - It stays a draft until every acceptance criterion of the issue is met.
  - It is merged by squash, so that `main` stays linear with one commit per issue. The pull request title becomes the commit message.
  - The branch is deleted after the merge.

## Consequences

- Every change has a stated purpose and a point where it is considered done.
- `main` only contains finished issues, and its history is the list of issues in the order they were completed.
- A small change still needs an issue and a pull request, which is overhead for a one-line fix.
- The size of an issue sets the size of the pull request, so issues must be kept small enough to review in one pass.
- The commits on a branch are not kept on `main`. They remain visible in the pull request.
