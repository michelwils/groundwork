# Contributing

This file summarises how changes are made. The decisions behind it are recorded in [`docs/adr/`](docs/adr/).

## Language

All repository content is written in English ([ADR 0004](docs/adr/0004-repository-language-english.md)).

## Workflow

Every change goes through an issue, a branch and a pull request ([ADR 0003](docs/adr/0003-change-workflow.md)).

1. Open an issue that names the outcome and gives the context, deliverables, acceptance criteria (as a plain list) and what is out of scope. Assign it to a milestone.
2. Create a branch from `main` named `<type>/<issue-number>-<issue-title-in-kebab-case>`, for example `docs/1-bootstrap-the-repository`.
3. Commit your work on the branch.
4. Open a draft pull request titled like a commit message, with `Closes #<issue-number>` and the acceptance criteria of the issue as a checklist in its description.
5. Check each criterion as it is met, and mark the pull request ready for review once all are checked.
6. The pull request is merged by squash, and its title, followed by the pull request number, becomes the commit title on `main`. The branch is then deleted.

## Commit messages

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) ([ADR 0002](docs/adr/0002-conventional-commits.md)):

```
<type>[(scope)][!]: <description>

[body]

[footers]
```

The allowed types are `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore` and `revert`. The scope is optional and is a single lowercase word naming the part of the repository that changes.

Examples:

```
feat(auth): add password reset by email
```

```
fix(parser): handle empty input without crashing
```

```
docs(readme): describe the release process
```

```
ci: run secret detection on every pull request

Refs #12
```

A breaking change is marked with `!` before the colon and has a `BREAKING CHANGE:` footer that describes what breaks and how to migrate:

```
feat(api)!: rename the user field to account in responses

BREAKING CHANGE: clients must read `account` instead of `user`.
The `user` field is removed.
```

Work that is not finished is merged as it is done, but stays out of the version until it is reachable by users ([ADR 0006](docs/adr/0006-trunk-based-development.md)). Its code is committed as `chore`, its tests as `test` and its documentation as `docs`. The commit that makes it reachable is the `feat`:

```
chore(reset): add the password reset service
```

```
feat(reset): enable password reset by email
```

## Decisions

Significant decisions are recorded as ADRs, following the template in [`docs/adr/template.md`](docs/adr/template.md) ([ADR 0001](docs/adr/0001-record-architecture-decisions.md)).

## Releases

Versions follow Semantic Versioning ([ADR 0005](docs/adr/0005-semantic-versioning-and-releases.md)), and the type of a commit sets the increment. A release is made by hand: decide the version from the commits on `main` since the previous tag, tag `main` with `v<version>`, then publish a release for the tag whose notes list the changes since the previous release. A project that maintains an older major version fixes it on `main` first, then backports the fix to a `maintenance/v<major>` branch with a pull request and tags the release on that branch ([ADR 0006](docs/adr/0006-trunk-based-development.md)). The public contract is described in the [README](README.md#versioning).
