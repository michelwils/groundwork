# Contributing

This file summarises how changes are made. The decisions behind it are recorded in [`docs/adr/`](docs/adr/).

A line of this file that belongs to an ADR goes in the block of that ADR, between its markers: see [`.groundwork/practices.md`](.groundwork/practices.md).

<!-- groundwork:0004 -->
## Language

All repository content is written in English ([ADR 0004](docs/adr/0004-repository-language-english.md)).
<!-- /groundwork -->

<!-- groundwork:0003 -->
## Workflow

Every change goes through an issue, a branch and a pull request ([ADR 0003](docs/adr/0003-change-workflow.md)).

1. Open an issue that names the outcome and gives the context, deliverables, acceptance criteria (as a plain list) and what is out of scope. Assign it to a milestone. The issue template has these sections.
2. Create a branch from `main` named `<type>/<issue-number>-<issue-title-in-kebab-case>`, for example `docs/1-bootstrap-the-repository`.
3. Commit your work on the branch.
4. Open a draft pull request titled like a commit message, with `Closes #<issue-number>` and the acceptance criteria of the issue as a checklist in its description. The pull request template has these sections.
5. Check each criterion as it is met, and mark the pull request ready for review once all are checked.
6. The pull request is merged by squash, and its title, followed by the pull request number, becomes the commit title on `main`. The branch is then deleted. For a breaking change, the maintainer who merges copies the `BREAKING CHANGE:` line from the description into the body of the squash commit, from which the release notes take it.

The pull requests that Dependabot opens to update pinned versions, and the one that the `update-groundwork` workflow opens to move to a later version of groundwork, have no issue. The title of Dependabot's pull requests, which starts with a capital letter, is not checked. A maintainer reviews and merges each one ([ADR 0003](docs/adr/0003-change-workflow.md)).
<!-- /groundwork -->

<!-- groundwork:0002 -->
## Commit messages

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) ([ADR 0002](docs/adr/0002-conventional-commits.md)):

```text
<type>[(scope)][!]: <description>

[body]

[footers]
```

The allowed types are `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore` and `revert`. The scope is optional and is a single lowercase word naming the part of the repository that changes.

Examples:

```text
feat(auth): add password reset by email
```

```text
fix(parser): handle empty input without crashing
```

```text
docs(readme): describe the release process
```

```text
ci: run secret detection on every pull request

Refs #12
```

A breaking change is marked with `!` before the colon and has a `BREAKING CHANGE:` footer that describes what breaks and how to migrate:

```text
feat(api)!: rename the user field to account in responses

BREAKING CHANGE: clients must read `account` instead of `user`.
The `user` field is removed.
```
<!-- /groundwork -->

<!-- groundwork:0006 -->
Work that is not finished is merged as it is done, but stays out of the version until it is reachable by users ([ADR 0006](docs/adr/0006-trunk-based-development.md)). Its code is committed as `chore`, its tests as `test` and its documentation as `docs`. The commit that makes it reachable is the `feat`:

```text
chore(reset): add the password reset service
```

```text
feat(reset): enable password reset by email
```
<!-- /groundwork -->

<!-- groundwork:0009 -->
## Tests

Write the test of a change of behaviour before the code that makes it pass, and see it fail ([ADR 0009](docs/adr/0009-test-first-development.md)). A bug is first reproduced by a test. A test changes only when the requirement changes, never to make code pass. A change of behaviour that has no new test says why in its pull request.
<!-- /groundwork -->

## Review checklist

A reviewer, and whoever checks their own work, check:

- each acceptance criterion of the issue against the diff, not against the pull request description
- contradictions with, and repetitions of, the ADRs, the README and this file
- the commands that the change documents, by running them
- the links, by following them
<!-- groundwork:0005 -->
- the type of the pull request title, against the public contract in the [README](README.md), since it sets the next version
<!-- /groundwork -->
<!-- groundwork:0010 -->
- the trust boundaries of the change, against the rules of [ADR 0010](docs/adr/0010-security-of-the-code-of-an-application.md)
<!-- /groundwork -->
<!-- groundwork:0011 -->
- the data that the change collects, keeps or sends, against the principles of [ADR 0011](docs/adr/0011-protection-of-confidential-and-personal-data.md)
<!-- /groundwork -->
- wording that can be read in two ways, or that leaves the reader to guess

<!-- groundwork:0008 -->
## Checks

Checks run before each commit and in CI on every pull request ([ADR 0008](docs/adr/0008-automated-checks.md)). Install the hooks once with `pre-commit install`, and run every check on all files, including a scan of the whole history for secrets, with `pre-commit run --all-files --hook-stage manual`. A failing check is fixed, not skipped. The checks cover the commit message, secrets, Markdown and the settings of `.editorconfig`, and, on a pull request, its title, its branch name and its closing line.
<!-- /groundwork -->

<!-- groundwork:0007 -->
## AI-assisted changes

A change made with a coding agent follows the same rules ([ADR 0007](docs/adr/0007-ai-assisted-changes.md)). Its commits have a `Co-Authored-By` trailer naming the agent, and an issue or a pull request it writes ends with a line stating that it was generated. Nothing refers to the agent's session, and a maintainer approves every merge. For a change that is not trivial, the agent proposes a plan first and records the approved plan in the pull request. The instructions given to agents are in [`AGENTS.md`](AGENTS.md).

```text
docs(readme): describe the release process

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
```

```text
🤖 Generated with [Claude Code](https://claude.com/claude-code)
```
<!-- /groundwork -->

<!-- groundwork:0001 -->
## Decisions

Significant decisions are recorded as ADRs, following the template in [`docs/adr/template.md`](docs/adr/template.md) ([ADR 0001](docs/adr/0001-record-architecture-decisions.md)).
<!-- /groundwork -->

<!-- groundwork:0005 -->
## Releases

Versions follow Semantic Versioning ([ADR 0005](docs/adr/0005-semantic-versioning-and-releases.md)), and the type of a commit sets the increment. A release is made when the maintainers decide, with the [`release` workflow](.github/workflows/release.yml), started by hand from the Actions tab on `main`:

1. Run it with `publish` unchecked and the version empty. It shows the version it computes and the release notes, and creates nothing.
2. Run it again with `publish` checked. It creates the annotated tag `v<version>` and publishes the release.

To open the notes with a text, for example how to migrate from a breaking change that no commit describes, give it in `notes`: `gh workflow run release.yml -f notes="$(cat <file>)"`. To release a version other than the computed one, for example `1.0.0` or after a change that was undone without a `revert`, give it in `version`. The workflow asks for one too when the description of a `revert` matches more than one change, released or not: it stops and names them. The public contract is described in the [README](README.md).
<!-- /groundwork -->

<!-- groundwork:0006 -->
A project that maintains an older major version fixes it on `main` first, then backports the fix to a `maintenance/v<major>` branch with a pull request and runs the workflow on that branch ([ADR 0006](docs/adr/0006-trunk-based-development.md)).
<!-- /groundwork -->
