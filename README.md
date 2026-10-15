# groundwork

Best-practice baseline for my projects: repository structure, conventions, automation, documentation and architecture decisions. Clone before pouring concrete.

> **Status:** work in progress. Nothing below is stable until `v1.0.0`.

## Who it is for

Me, as the starting point of my desktop and web applications. The repository is public, so anyone can read it or reuse it under the license below.

## What it covers

- Recording architecture decisions
- How changes are made: issues, branches and pull requests
- Commit messages
- Versioning and releases
- Pre-commit checks and baseline CI that do not depend on a language or technology stack

## What it does not cover

Anything specific to a language, technology stack or type of application: code formatting and linting, tests, dependency updates, dev environment, publishing, reference architecture and operations. That belongs in the projects that adopt groundwork.

## Decisions

Significant decisions are recorded as architecture decision records in [`docs/adr/`](docs/adr/).

## Versioning

groundwork follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html), as described in [ADR 0005](docs/adr/0005-semantic-versioning-and-releases.md).

**Public contract.** What adopting projects rely on:

- the rules in the Decision section of accepted ADRs
- the files groundwork provides for projects to use, such as hooks, workflows and templates: their names, locations and behaviour

The README, the Context and Consequences sections of ADRs, and wording that does not change a rule are not part of it.

**Changes to the contract.**

| Commit type | Change to the contract | Version |
|---|---|---|
| any type with `!` | A rule is reversed, or a file is removed, renamed or changed so that it no longer does what projects rely on | major |
| `feat` | A rule or a file is added | minor |
| `fix`, `perf` | A rule is clarified without changing its meaning, or a file is improved without changing what it does | patch |
| `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`, `revert` | Anything outside the contract: the README, the Context and Consequences sections of ADRs, wording | none |

A release increments the version once, by the highest increment among the changes since the previous release.

Only the latest release is maintained.

While groundwork is at `0.y.z`, a breaking change or a `feat` increments the minor version, and a `fix` or a `perf` increments the patch version. The first release is `v0.1.0`, and `v1.0.0` is tagged when the contract is considered stable enough to rely on.

## Adopting groundwork

groundwork is a GitHub template repository.

1. **Create the repository.** On this page, choose "Use this template".
2. **Configure it.** A template copies files, not repository settings. [ADR 0003](docs/adr/0003-change-workflow.md) relies on squash as the only merge method, with the pull request title as the commit title and an empty message, and on the automatic deletion of branches after a merge:

   ```
   gh repo edit --enable-squash-merge --enable-merge-commit=false \
     --enable-rebase-merge=false --delete-branch-on-merge
   gh api -X PATCH repos/<owner>/<repo> \
     -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=BLANK
   ```

3. **Replace** what is specific to groundwork: this README, with the project's own description and public contract ([ADR 0005](docs/adr/0005-semantic-versioning-and-releases.md)), and the license.
4. **Keep** the ADRs in [`docs/adr/`](docs/adr/): they remain accepted decisions of the project, and its own ADRs are numbered after them. Keep `CONTRIBUTING.md` and adjust it to the project.
5. **Create** the first milestone, then the first issue.
6. **Record** the version of groundwork the project started from, for example "Based on groundwork v0.1.0" in the README.

### Moving to a later version

A copy shares no history with groundwork and does not receive later changes. To move from `v0.1.0` to a later version:

1. Read the [release notes](https://github.com/michelwils/groundwork/releases) of the versions in between. A minor version adds a rule or a file without breaking anything. A major version requires the project to change something, which its `BREAKING CHANGE:` notes describe.
2. Fetch the tags of groundwork and apply the difference between the two versions, then resolve the conflicts on the files the project has changed:

   ```
   git remote add groundwork https://github.com/michelwils/groundwork.git
   git fetch groundwork --tags
   git diff v0.1.0 v0.2.0 | git apply --3way
   ```

3. Commit the result like any other change, through an issue and a pull request, and update the recorded version.

## Contributing

Changes go through an issue, a branch and a pull request, and commit messages follow Conventional Commits. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Michel Wils
