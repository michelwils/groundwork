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
- Rules for changes made with AI coding agents
- Test-first development
- Issue and pull request templates and a review checklist
- Shared editor and line-ending settings, in [`.editorconfig`](.editorconfig) and [`.gitattributes`](.gitattributes)
- Automated updates of pinned tool versions, in [`.github/dependabot.yml`](.github/dependabot.yml)
- Pre-commit checks and baseline CI that do not depend on a language or technology stack

## What it does not cover

Anything specific to a language, technology stack or type of application: code formatting and linting, test frameworks, test commands and coverage, updates of the dependencies of a stack, dev environment, publishing, reference architecture and operations. That belongs in the projects that adopt groundwork.

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
| --- | --- | --- |
| any type with `!` | A rule is reversed, or a file is removed, renamed or changed so that it no longer does what projects rely on | major |
| `feat` | A rule or a file is added | minor |
| `fix`, `perf` | A rule is clarified without changing its meaning, or a file is improved without changing what it does | patch |
| `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`, `revert` | Anything outside the contract: the README, the Context and Consequences sections of ADRs, wording | none |

A release increments the version once, by the highest increment among the changes since the previous release.

A release is made by the [`release` workflow](.github/workflows/release.yml), which a maintainer starts by hand: it computes the version from the commit titles, tags it and publishes the release notes.

Only the latest release is maintained.

While groundwork is at `0.y.z`, a breaking change or a `feat` increments the minor version, and a `fix` or a `perf` increments the patch version. The first release is `v0.1.0`, and `v1.0.0` is tagged when the contract is considered stable enough to rely on.

## Checks

Checks run before each commit and in CI, as described in [ADR 0008](docs/adr/0008-automated-checks.md). They are defined in [`.pre-commit-config.yaml`](.pre-commit-config.yaml) and use the [pre-commit](https://pre-commit.com) framework:

- the commit title follows [ADR 0002](docs/adr/0002-conventional-commits.md)
- the commit message refers to no agent session ([ADR 0007](docs/adr/0007-ai-assisted-changes.md))
- no secret is committed, detected by [gitleaks](https://github.com/gitleaks/gitleaks) in the staged changes before a commit and in the whole history on demand
- Markdown files follow the rules of [markdownlint](https://github.com/DavidAnson/markdownlint), configured in [`.markdownlint.yaml`](.markdownlint.yaml)
- files follow the settings of [`.editorconfig`](.editorconfig), checked by [editorconfig-checker](https://github.com/editorconfig-checker/editorconfig-checker), for which pre-commit downloads Go if it is not installed

Install the hooks once with `pre-commit install`, and run every check on all files, including a scan of the whole history for secrets, with `pre-commit run --all-files --hook-stage manual`.

The [`checks` workflow](.github/workflows/checks.yml) runs that command on every pull request and on `main`, and checks that the title of the pull request follows [ADR 0002](docs/adr/0002-conventional-commits.md), since it becomes the commit title. It also runs the tests of the release script.

## Adopting groundwork

groundwork is a GitHub template repository.

1. **Create the repository.** On this page, choose "Use this template".
2. **Configure it.** A template copies files, not repository settings. [ADR 0003](docs/adr/0003-change-workflow.md) relies on squash as the only merge method, with the pull request title as the commit title and an empty message, and on the automatic deletion of branches after a merge:

   ```sh
   gh repo edit --enable-squash-merge --enable-merge-commit=false \
     --enable-rebase-merge=false --delete-branch-on-merge
   gh api -X PATCH repos/<owner>/<repo> \
     -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=BLANK
   ```

3. **Replace** what is specific to groundwork: this README, with the project's own description and public contract ([ADR 0005](docs/adr/0005-semantic-versioning-and-releases.md)), and the license.
4. **Keep** the ADRs in [`docs/adr/`](docs/adr/): they remain accepted decisions of the project, and its own ADRs are numbered after them. Keep `CONTRIBUTING.md` and adjust it to the project.
5. **Fill in** the Project section of `AGENTS.md` with the commands and layout of the project, including its test commands and, if it wants one, its coverage threshold. If you add a `CLAUDE.md` or a `CLAUDE.local.md`, import `AGENTS.md` from it with `@AGENTS.md`, because Claude Code then stops reading `AGENTS.md`.
6. **Install** [pre-commit](https://pre-commit.com), for example with `pipx install pre-commit`, then run `pre-commit install`. Add the checks of the project's stack to `.pre-commit-config.yaml`, and the indentation rules of its languages to `.editorconfig`. Add the ecosystems of its stack to `.github/dependabot.yml`.
7. **Create** the first milestone, then the first issue.
8. **Record** the version of groundwork the project started from, for example "Based on groundwork v0.1.0" in the README.
9. **Release** with the `release` workflow once the project has something to release. Its first version is computed from the commits of the project, which start with the `Initial commit` of the template. That commit does not change the version.

### Moving to a later version

A copy shares no history with groundwork and does not receive later changes. To move from `v0.1.0` to a later version:

1. Read the [release notes](https://github.com/michelwils/groundwork/releases) of the versions in between. A minor version adds a rule or a file without breaking anything. A major version requires the project to change something, which its `BREAKING CHANGE:` notes describe.
2. Fetch the tags of groundwork under their own prefix, so that they do not collide with the tags of the project, and apply the difference between the two versions. Leave out the files that concern groundwork itself, such as its README, and resolve the conflicts on the files the project has changed:

   ```sh
   git remote add groundwork https://github.com/michelwils/groundwork.git
   git fetch groundwork 'refs/tags/*:refs/tags/groundwork/*'
   git diff groundwork/v0.1.0 groundwork/v0.2.0 -- . ':!README.md' | git apply --3way
   ```

3. Commit the result like any other change, through an issue and a pull request, and update the recorded version.

## Contributing

Changes go through an issue, a branch and a pull request, and commit messages follow Conventional Commits. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Michel Wils
