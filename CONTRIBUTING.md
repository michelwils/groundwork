# Contributing

This file summarises how changes are made. The decisions behind it are recorded in [`docs/adr/`](docs/adr/).

## Workflow

Every change goes through an issue, a branch and a pull request ([ADR 0003](docs/adr/0003-change-workflow.md)).

1. Open an issue that names the outcome and gives the context, deliverables, acceptance criteria and what is out of scope. Assign it to a milestone.
2. Create a branch from `main` named `<type>/<issue-number>-<issue-title-in-kebab-case>`, for example `docs/1-bootstrap-the-repository`.
3. Commit your work on the branch.
4. Open a draft pull request titled like a commit message, with `Closes #<issue-number>` in its description.
5. Mark it ready for review once every acceptance criterion of the issue is met.
6. The pull request is merged by squash, and its title becomes the commit message on `main`. The branch is then deleted.

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
docs(adr): clarify when an ADR is superseded
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

## Language

All repository content is written in English ([ADR 0004](docs/adr/0004-repository-language-english.md)).

## Decisions

Significant decisions are recorded as ADRs, following the template in [`docs/adr/template.md`](docs/adr/template.md) ([ADR 0001](docs/adr/0001-record-architecture-decisions.md)).
