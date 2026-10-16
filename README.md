# groundwork

Best-practice baseline for my projects: repository structure, conventions, automation, documentation and architecture decisions. Clone before pouring concrete.

> **Status:** work in progress. Nothing below is stable until `v1.0.0`.

## Who it is for

Me, as the starting point of my desktop and web applications. The repository is public, so anyone can read it or reuse it under the license below.

## What it covers

- Recording architecture decisions, with the numbers `0001` to `0999` reserved for the ADRs of groundwork ([ADR 0001](docs/adr/0001-record-architecture-decisions.md))
- How changes are made: issues, branches and pull requests
- Commit messages
- Versioning and releases
- Rules for changes made with AI coding agents
- Test-first development
- Issue and pull request templates and a review checklist
- Shared editor and line-ending settings, in [`.editorconfig`](.editorconfig) and [`.gitattributes`](.gitattributes)
- Automated updates of pinned tool versions, proposed seven days after a release, in [`.github/dependabot.yml`](.github/dependabot.yml)
- A script that prepares the update of a project to a later version of groundwork, in [`.github/scripts/update_groundwork.py`](.github/scripts/update_groundwork.py)
- A workflow that opens every week the pull request that moves a project to a later version of groundwork, in [`.github/workflows/update-groundwork.yml`](.github/workflows/update-groundwork.yml)
- A security policy, in [`SECURITY.md`](SECURITY.md)
- Protection of the default branch with a ruleset, in [`.github/rulesets/main.json`](.github/rulesets/main.json)
- A script that applies the repository settings, in [`.github/scripts/apply_settings.py`](.github/scripts/apply_settings.py)
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
- the file `.groundwork-version` that a project keeps, and which the update script reads: its name and its format

The README, the Context and Consequences sections of ADRs, and wording that does not change a rule are not part of it.

**Changes to the contract.**

| Commit type | Change to the contract | Version |
| --- | --- | --- |
| any type with `!` | A rule is reversed, or a file is removed, renamed or changed so that it no longer does what projects rely on | major |
| `feat` | A rule or a file is added | minor |
| `fix`, `perf` | A rule is clarified without changing its meaning, or a file is improved without changing what it does | patch |
| `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`, `revert` | Anything outside the contract: the README, the Context and Consequences sections of ADRs, wording | none |

A release increments the version once, by the highest increment among the changes since the previous release.

A release is made by the [`release` workflow](.github/workflows/release.yml), which a maintainer starts by hand: it computes the version from the commit titles, tags it and publishes the release notes. The tag and the content of a published release are never changed.

Only the latest release is maintained.

While groundwork is at `0.y.z`, a breaking change or a `feat` increments the minor version, and a `fix` or a `perf` increments the patch version. The first release is `v0.1.0`, and `v1.0.0` is tagged when the contract is considered stable enough to rely on.

## Checks

Checks run before each commit and in CI, as described in [ADR 0008](docs/adr/0008-automated-checks.md). They are defined in [`.pre-commit-config.yaml`](.pre-commit-config.yaml) and use the [pre-commit](https://pre-commit.com) framework:

- the commit title follows [ADR 0002](docs/adr/0002-conventional-commits.md)
- the commit message refers to no agent session ([ADR 0007](docs/adr/0007-ai-assisted-changes.md))
- no secret is committed, detected by [gitleaks](https://github.com/gitleaks/gitleaks) in the staged changes before a commit and in the whole history on demand
- Markdown files follow the rules of [markdownlint](https://github.com/DavidAnson/markdownlint), configured in [`.markdownlint.yaml`](.markdownlint.yaml)
- files follow the settings of [`.editorconfig`](.editorconfig), checked by [editorconfig-checker](https://github.com/editorconfig-checker/editorconfig-checker), for which pre-commit downloads Go if it is not installed
- the ADRs have the title, the status, the sections and the numbering that [ADR 0001](docs/adr/0001-record-architecture-decisions.md) and its template define, checked by [`.github/scripts/check_adrs.py`](.github/scripts/check_adrs.py)
- the relative links and the anchors of the Markdown files resolve, checked offline by [`.github/scripts/check_links.py`](.github/scripts/check_links.py)
- GitHub Actions workflows have no security mistake such as an expression injection, an unpinned action or excessive permissions, audited offline by [zizmor](https://docs.zizmor.sh) and configured in [`.github/zizmor.yml`](.github/zizmor.yml)

Install the hooks once with `pre-commit install`, and run every check on all files, including a scan of the whole history for secrets, with `pre-commit run --all-files --hook-stage manual`.

The [`checks` workflow](.github/workflows/checks.yml) runs that command on every pull request and on `main`, and checks that the title of the pull request follows [ADR 0002](docs/adr/0002-conventional-commits.md), since it becomes the commit title, and that its branch is named `<type>/<issue-number>-<slug>` and its description closes that issue ([ADR 0003](docs/adr/0003-change-workflow.md)). It also runs the tests of its scripts.

## Adopting groundwork

groundwork is a GitHub template repository.

1. **Create the repository.** On this page, choose "Use this template".
2. **Configure it.** A template copies files, not repository settings. Clone the repository, then run the script from it, logged in with `gh` and with admin rights on the repository:

   ```sh
   python3 .github/scripts/apply_settings.py [<owner>/<repo>] [--dry-run]
   ```

   It applies what [ADR 0003](docs/adr/0003-change-workflow.md) relies on: squash as the only merge method, with the pull request title as the commit title and an empty message, and the automatic deletion of branches after a merge. It enables private vulnerability reporting, which [`SECURITY.md`](SECURITY.md) relies on, and makes published releases immutable, so that the tag of a release cannot be moved. That applies to the releases published afterwards. Last, it protects the default branch with the ruleset of this repository, which rejects direct pushes and requires the `checks` job of the CI. Run it again and the repository stays in the same state. With `--dry-run`, it shows what it would apply and changes nothing.

   If the project adds jobs to its CI, it requires one job that waits for all the others and fails if one failed, changes the `context` of [`.github/rulesets/main.json`](.github/rulesets/main.json) and runs the script again.

   Create the secret `GROUNDWORK_UPDATE_TOKEN` too, which the [automatic update](#automatic-update) of groundwork needs.
3. **Create** the first milestone, then the first issue, which adapts the template to the project.
4. **Adapt it** on a branch, in a pull request that closes that issue, since the default branch now rejects direct pushes:
   - **Replace** what is specific to groundwork: this README, with the project's own description and public contract ([ADR 0005](docs/adr/0005-semantic-versioning-and-releases.md)), and the license.
   - **Keep** the ADRs in [`docs/adr/`](docs/adr/): they remain accepted decisions of the project, and its own ADRs are numbered from `1000`, since the numbers below are reserved for groundwork ([ADR 0001](docs/adr/0001-record-architecture-decisions.md)). Keep `CONTRIBUTING.md` and `SECURITY.md` and adjust them to the project: the supported versions, for `SECURITY.md`.
   - **Fill in** the Project section of `AGENTS.md` with the commands and layout of the project, including its test commands and, if it wants one, its coverage threshold. If you add a `CLAUDE.md` or a `CLAUDE.local.md`, import `AGENTS.md` from it with `@AGENTS.md`, because Claude Code then stops reading `AGENTS.md`.
   - **Install** [pre-commit](https://pre-commit.com), for example with `pipx install pre-commit`, then run `pre-commit install`. Add the checks of the project's stack to `.pre-commit-config.yaml`, and the indentation rules of its languages to `.editorconfig`. Add the ecosystems of its stack to `.github/dependabot.yml`.
   - **Record** the version of groundwork the project started from: create `.groundwork-version` at the root of the project, with one line `X.Y.Z` holding the latest release without the leading `v`, for example `0.2.0`. The update script reads it.
5. **Release** with the `release` workflow once the project has something to release. Its first version is computed from the commits of the project, which start with the `Initial commit` of the template. That commit does not change the version.

### Moving to a later version

A copy shares no history with groundwork and does not receive later changes. To move to a later version:

1. Read the [release notes](https://github.com/michelwils/groundwork/releases) of the versions in between. A minor version adds a rule or a file without breaking anything. A major version requires the project to change something, which its `BREAKING CHANGE:` notes describe.
2. Open an issue for the update, then run the script from a clean working tree, with the number of that issue:

   ```sh
   python3 .github/scripts/update_groundwork.py <issue-number> [--to X.Y.Z]
   ```

   It reads `.groundwork-version`, fetches the tags of groundwork under their own prefix `groundwork/`, so that they do not collide with the tags of the project, and creates the branch `chore/<issue-number>-update-groundwork-to-v<X-Y-Z>`. On that branch it applies what changed between the two versions, file by file, and keeps the changes of the project. It leaves out `README.md` and `LICENSE`, which concern groundwork itself, and sets the new version in `.groundwork-version`. It goes to the latest version unless `--to` names another. It does not commit, push or open a pull request. A project whose copy of groundwork predates the script takes `.github/scripts/update_groundwork.py` from the release it moves to.

   It ends with status 0 when the project is updated or already up to date, 1 on an error, and 2 when files are in conflict. It names them and leaves markers in them for you to resolve.
3. Commit the result like any other change, through the issue and a pull request.

#### Automatic update

The [`update-groundwork` workflow](.github/workflows/update-groundwork.yml) does this every week, and when started by hand. It runs [`.github/scripts/open_update_pull_request.py`](.github/scripts/open_update_pull_request.py), which runs the script above without an issue, commits the result on the branch `groundwork/update-to-v<X-Y-Z>`, pushes it and opens the pull request `chore: update groundwork to v<X.Y.Z>`. Like those of Dependabot, that pull request has no issue ([ADR 0003](docs/adr/0003-change-workflow.md)), and the check of the branch name and closing line skips the prefix `groundwork/`.

- It opens nothing when the project is up to date, when a pull request from a branch `groundwork/…` is already open, or when the pull request of that version was closed without being merged. Close the pull request to skip a version: a later version is proposed again.
- When files are in conflict, the pull request is a draft that lists them, with the markers left in the files. Resolve them, then mark it ready.
- It does nothing where there is no `.groundwork-version`, such as in groundwork itself.
- It needs the secret `GROUNDWORK_UPDATE_TOKEN`: a [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new) limited to the repository, with write access to contents, pull requests and workflows. The token of a workflow cannot push changes to workflow files, and does not start the checks of the pull request without an approval. Create the secret once, and renew the token before it expires:

  ```sh
  gh secret set GROUNDWORK_UPDATE_TOKEN --repo <owner>/<repo>
  ```

## Contributing

Changes go through an issue, a branch and a pull request, and commit messages follow Conventional Commits. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Michel Wils
