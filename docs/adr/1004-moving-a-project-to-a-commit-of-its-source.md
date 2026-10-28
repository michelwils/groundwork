# 1004. Moving a project to a commit of its source

**Status:** accepted

## Context

`update_groundwork.py` moves a project to a release. It reads the versions from the tags `v*` of the source, `.groundwork-version` holds one line `X.Y.Z`, the files are merged three ways from the tag of the recorded version to the tag of the new one, and the branch is named after the new version.

A project sometimes needs a change of groundwork before it is released, to try it. Copying the files by hand loses the merge and the record of what the project is based on.

Recording only the latest release that the commit contains would keep the format, but the next update would merge from that release: what the project applied from the commit would count as changes of the project, and they conflict with the same lines in the next release.

## Decision

We will let a person move a project to the head of its source with `update_groundwork.py --to head`, and let `.groundwork-version` name the commit.

- **Option.** `--to head` is the head of the source, which is its default branch. It is never the default of the script, and `open_update_pull_request.py`, and therefore the weekly workflow, never uses it. `--to X.Y.Z` and the default do not change.
- **Record.** The file holds one line, `X.Y.Z` or `X.Y.Z+<commit>`. `X.Y.Z` is the latest release in the history of the commit, and `<commit>` is its identifier of 40 or 64 lowercase hexadecimal characters, as build metadata of [Semantic Versioning](https://semver.org/spec/v2.0.0.html). When the head is that release, the file holds `X.Y.Z` alone. Any other form is refused before anything changes.
- **Base.** The next update merges from the commit, not from the release. The commit must be in the source: the script fetches its head, and refuses a head that does not contain the commit, since the source was rewritten, and a commit that the source does not have.
- **Next update.** Without `--to`, the project goes to the latest release if that release contains the commit, and is up to date while none does. `--to X.Y.Z` is refused for a release that does not contain the commit. `--to head` is up to date when the head is the commit.
- **Branch.** The branch of the update to a commit is named after its first 12 characters instead of the version: `chore/<issue>-update-groundwork-to-<commit>` and `groundwork/update-to-<commit>`.
- **Result.** The result for the pull request script ([ADR 1003](1003-giving-the-result-of-the-update-to-the-pull-request-script.md)) has the recorded form in `to` and in `from`. `open_update_pull_request.py` accepts a commit in `from` and refuses a result that moves the project to a commit.
- **The choice of the ADRs.** `apply_choice.py` reads a project that is based on a commit from that commit. `--version` of a new project stays a release.

## Consequences

- The next update has no conflict on what the project applied from the commit.
- A project on a commit does not receive the update of a release until a release contains its commit, and the weekly workflow opens nothing in the meantime.
- Every reader of `.groundwork-version` must accept the second form: the scripts of groundwork do, and a script of a project that reads the file must do the same.
- The format of `.groundwork-version` is part of the public contract: the second form is a new form, and an old form stays valid.
- A source that rewrites its history leaves the project with a commit it cannot find. The project puts `X.Y.Z` back in the file by hand.
- A branch other than the default branch of the source is not covered.
