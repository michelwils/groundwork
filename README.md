# groundwork

Best-practice baseline for my projects: repository structure, conventions, automation, documentation and architecture decisions. Clone before pouring concrete.

> **Status:** work in progress. Nothing below is stable until `v1.0.0`.

## Who it is for

Me, as the starting point of my desktop and web applications. The repository is public, so anyone can read it or reuse it under the license below:

- a team that wants the same practices in a project adopts it as described in [Adopting groundwork](#adopting-groundwork), or [in an existing project](#adopting-in-an-existing-project), and chooses the ADRs it keeps;
- a community, such as the teams of an organisation, builds its own base of decisions from it, which its projects synchronise, as [the guide of the bases](.groundwork/community-base.md) tells.

## What it covers

- Recording architecture decisions, with the numbers `0001` to `0999` reserved for the ADRs of groundwork ([ADR 0001](docs/adr/0001-record-architecture-decisions.md))
- How changes are made: issues, branches and pull requests
- Commit messages
- Versioning and releases
- Rules for changes made with AI coding agents
- Test-first development
- Rules for the security of the code of an application ([ADR 0010](docs/adr/0010-security-of-the-code-of-an-application.md))
- Principles for the protection of confidential and personal data ([ADR 0011](docs/adr/0011-protection-of-confidential-and-personal-data.md))
- Principles for responding to an incident ([ADR 0012](docs/adr/0012-responding-to-an-incident.md))
- Principles for the logs and the diagnostic of an application ([ADR 0015](docs/adr/0015-logs-and-diagnostic-of-an-application.md))
- A rule for the licenses of the dependencies, which each project states for itself ([ADR 0013](docs/adr/0013-licenses-of-the-dependencies.md))
- How a user checks the origin of a release ([ADR 0005](docs/adr/0005-semantic-versioning-and-releases.md))
- Issue and pull request templates and a review checklist
- Shared editor and line-ending settings, in [`.editorconfig`](.editorconfig) and [`.gitattributes`](.gitattributes)
- Automated updates of pinned tool versions, proposed seven days after a release, in [`.github/dependabot.yml`](.github/dependabot.yml)
- A script that prepares a project's update to a later version of groundwork, in [`.groundwork/scripts/update_groundwork.py`](.groundwork/scripts/update_groundwork.py), which a project always synchronises, whatever it leaves out
- Where the files of groundwork live: those that have no conventional name, such as the scripts, their tests and the map of the practices, are in the directory `.groundwork/`, so that a project can tell them from its own ([ADR 1001](docs/adr/1001-naming-the-files-of-groundwork.md))
- The path to adopt groundwork in an existing project, one practice at a time, and the rule that records the gaps, in [Adopting in an existing project](#adopting-in-an-existing-project)
- A guide for a community that builds a base of its own from groundwork, in [`.groundwork/community-base.md`](.groundwork/community-base.md)
- The choice of the ADRs that a project synchronises, in a file `.groundwork-adrs`, and the ranges of ADR numbers that a community base reserves, in `.groundwork-ranges` ([ADR 1000](docs/adr/1000-choosing-the-adrs-a-project-synchronises.md))
- A weekly workflow that opens the pull request that moves a project to a later version of groundwork, in [`.github/workflows/update-groundwork.yml`](.github/workflows/update-groundwork.yml)
- A security policy, with the procedure to handle a vulnerability from its report to its disclosure, in [`SECURITY.md`](SECURITY.md)
- Protection of the default branch with a ruleset, in [`.groundwork/rulesets/main.json`](.groundwork/rulesets/main.json)
- A review by code owners of the files of groundwork in a project, which the project turns on, with a template of `CODEOWNERS` in [`.groundwork/CODEOWNERS.template`](.groundwork/CODEOWNERS.template) ([ADR 0014](docs/adr/0014-protecting-the-files-of-groundwork-in-a-project.md))
- A script that applies the repository settings, in [`.groundwork/scripts/apply_settings.py`](.groundwork/scripts/apply_settings.py)
- Pre-commit checks and baseline CI that do not depend on a language or technology stack, and the rule that a project audits the dependencies of its stack ([ADR 0008](docs/adr/0008-automated-checks.md))
- The platform's vulnerability alerts and security updates, turned on by the settings script

## What it does not cover

Anything specific to a language, technology stack or type of application: code formatting and linting, test frameworks, test commands and coverage, updates of a stack's dependencies, dev environment, publishing, reference architecture and operations, including the collection, the storage and the retention of the logs, the metrics and the tracing. That belongs in the projects that adopt groundwork.

## Decisions

Significant decisions are recorded as architecture decision records in [`docs/adr/`](docs/adr/).

## Versioning

groundwork follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html), as described in [ADR 0005](docs/adr/0005-semantic-versioning-and-releases.md).

**Public contract.** What adopting projects rely on:

- the rules in the Decision section of accepted ADRs
- the files groundwork provides for projects to use, such as hooks, workflows and templates: their names, locations and behaviour, and the directory `.groundwork/` with what it holds
- the file `.groundwork-version` that a project keeps, and which the update script reads: its name and its format
- the files `.groundwork-adrs`, `.groundwork-ranges` and `.groundwork-source`: their names and their formats
- for a project that keeps some of the ADRs only: the rules of the ADRs it keeps and of the ones they need, and the files that [`.groundwork/practices.md`](.groundwork/practices.md) gives for them
- the markers that delimit the lines of an ADR in a file that several ADRs share, `<!-- groundwork:NNNN -->` … `<!-- /groundwork -->` in Markdown and `# groundwork:NNNN` … `# /groundwork` in YAML

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

Check a release with `gh release verify <tag>`: it confirms, from the platform's attestation, that the release exists and is immutable. The source archives are not covered.

Only the latest release is maintained.

## Checks

Checks run before each commit and in CI, as described in [ADR 0008](docs/adr/0008-automated-checks.md). They are defined in [`.pre-commit-config.yaml`](.pre-commit-config.yaml) and use the [pre-commit](https://pre-commit.com) framework:

- the commit title follows [ADR 0002](docs/adr/0002-conventional-commits.md)
- the commit message refers to no agent session ([ADR 0007](docs/adr/0007-ai-assisted-changes.md))
- no secret is committed, detected by [gitleaks](https://github.com/gitleaks/gitleaks) in the staged changes before a commit and in the whole history on demand
- Markdown files follow the rules of [markdownlint](https://github.com/DavidAnson/markdownlint), configured in [`.markdownlint.yaml`](.markdownlint.yaml)
- files follow the settings of [`.editorconfig`](.editorconfig), checked by [editorconfig-checker](https://github.com/editorconfig-checker/editorconfig-checker), for which pre-commit downloads Go if it is not installed
- the ADRs have the title, the status, the sections and the numbering that [ADR 0001](docs/adr/0001-record-architecture-decisions.md) and its template define, checked by [`.groundwork/scripts/check_adrs.py`](.groundwork/scripts/check_adrs.py)
- the map of the practices names every ADR and every file of groundwork, and the ADRs that each ADR needs; the text of each ADR, and the blocks of the files that several ADRs share, name only the ADRs that they need; and the blocks are where the map says; checked by [`.groundwork/scripts/check_practices.py`](.groundwork/scripts/check_practices.py) against [`.groundwork/practices.md`](.groundwork/practices.md)
- the relative links and the anchors of the Markdown files resolve, checked offline by [`.groundwork/scripts/check_links.py`](.groundwork/scripts/check_links.py), which runs in an environment that [`.groundwork/scripts/run_with_requirements.py`](.groundwork/scripts/run_with_requirements.py) makes from the pinned [`requirements.txt`](.groundwork/scripts/requirements.txt) on the first run
- GitHub Actions workflows have no security mistake such as an expression injection, an unpinned action or excessive permissions, audited offline by [zizmor](https://docs.zizmor.sh) and configured in [`.github/zizmor.yml`](.github/zizmor.yml)
- the scripts' dependencies have no known vulnerability, audited by [pip-audit](https://github.com/pypa/pip-audit) when [`.groundwork/scripts/requirements.txt`](.groundwork/scripts/requirements.txt) changes and in the CI, since it needs the network ([ADR 0008](docs/adr/0008-automated-checks.md))

Install the hooks once with `pre-commit install`, and run every check on all files, including a scan of the whole history for secrets, with `pre-commit run --all-files --hook-stage manual`.

The [`checks` workflow](.github/workflows/checks.yml) runs that command on every pull request and on `main`. It checks that the pull request title follows [ADR 0002](docs/adr/0002-conventional-commits.md), since it becomes the commit title, except for Dependabot's pull requests. It checks that the branch is named `<type>/<issue-number>-<slug>` and that the description closes that issue ([ADR 0003](docs/adr/0003-change-workflow.md)). It also runs the tests of its scripts. It keeps the environments of the hooks of pre-commit in the [cache of GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching), which a change of `.pre-commit-config.yaml`, of the version of pre-commit or of the Python that it runs with renews. The first run that installs them saves them, even if a check fails: pre-commit installs again an environment that did not finish. Only a push to `main` writes the cache that the pull requests restore: the cache of a pull request stays in its own scope. When the CI gets slow, look at the cache of `main` in the Actions tab.

## Adopting groundwork

groundwork is a GitHub template repository.

1. **Create the repository.** On this page, choose "Use this template".
2. **Configure it.** A template copies files, not repository settings. Clone the repository, then run the script from it, logged in with `gh` and with admin rights on the repository:

   ```sh
   python3 .groundwork/scripts/apply_settings.py [<owner>/<repo>] [--dry-run] [--code-owner-review] [--last-push-approval] [--turn-off-reviews]
   ```

   It applies the merge settings that [ADR 0003](docs/adr/0003-change-workflow.md) relies on. It enables private vulnerability reporting, which [`SECURITY.md`](SECURITY.md) relies on, and makes published releases immutable, so that the tag of a release cannot be moved. That applies to the releases published afterwards. It also turns on the vulnerability alerts and the security updates for the dependencies. Last, it protects the default branch with this repository's ruleset, which rejects direct pushes and requires the `checks` job of the CI. Run it again and the repository stays in the same state. With `--dry-run`, it shows what it would apply and changes nothing. `--code-owner-review` and `--last-push-approval` require a review of the files of groundwork by their code owners, as [ADR 0014](docs/adr/0014-protecting-the-files-of-groundwork-in-a-project.md) tells. The script stops when a run would lower an approval setting that the ruleset already has, unless it gets `--turn-off-reviews`. Copy `.groundwork/CODEOWNERS.template` to `.github/CODEOWNERS` first, and merge it into the default branch.

   The jobs that the project adds to its CI go in [`.github/workflows/project-checks.yml`](.github/workflows/project-checks.yml), which the required job `checks` waits for ([ADR 0008](docs/adr/0008-automated-checks.md)): the ruleset needs no change, nor a new run of the script.

   Also create the secret `GROUNDWORK_UPDATE_TOKEN`, which the [automatic update](#automatic-update) of groundwork needs.
3. **Create** the first milestone, then the first issue, which adapts the template to the project.
4. **Adapt it** on a branch, in a pull request that closes that issue, since the default branch now rejects direct pushes:
   - **Replace** what is specific to groundwork: this README, with the project's own description and public contract ([ADR 0005](docs/adr/0005-semantic-versioning-and-releases.md)), and the license. The files of groundwork link to the project's README, never to one of its sections, so the README needs no particular heading. It holds the public contract when the project keeps ADR 0005.
   - **Choose** the ADRs of groundwork that the project follows, as [Choosing the ADRs](#choosing-the-adrs-a-project-synchronises) tells. Then run `python3 .groundwork/scripts/apply_choice.py [--source URL] [ADR …]` from a branch with a clean working tree, naming the ADRs to keep, for example `0001 0003 0006-0008` (`--dry-run` shows what it would do). It writes `.groundwork-adrs` and records the latest release of the source in `.groundwork-version` (and `--source` in `.groundwork-source`). It deletes the other ADRs with their files and the blocks of their lines, and the ADRs numbered `1000` or more, which are decisions of groundwork itself. The project numbers its own ADRs as [ADR 0001](docs/adr/0001-record-architecture-decisions.md) tells. Keep `CONTRIBUTING.md` and adjust it to the project. Keep `SECURITY.md` too when the project keeps ADR 0012, which owns it (`apply_choice.py` deletes it otherwise), and adjust its supported versions.
   - **Fill in** the Project section of `AGENTS.md` with the commands and layout of the project, including its test commands and, if it wants one, its coverage threshold. If you add a `CLAUDE.md` or a `CLAUDE.local.md`, import `AGENTS.md` from it with `@AGENTS.md`, because Claude Code then stops reading `AGENTS.md`.
   - **Install** [pre-commit](https://pre-commit.com), for example with `pipx install pre-commit`, then run `pre-commit install`. Add the checks of the project's stack to `.pre-commit-config.yaml`, which the CI runs, including the audit of its dependencies ([ADR 0008](docs/adr/0008-automated-checks.md)). Add the indentation rules of its languages to `.editorconfig`. If its stack has no audit tool, write the exception in its `AGENTS.md`. Add the ecosystems of its stack to `.github/dependabot.yml`.
   - **Record** the version of groundwork the project started from: create `.groundwork-version` at the project's root, with one line `X.Y.Z` holding the latest release without the leading `v`, for example `0.2.0`. The update script reads it. If the project follows a community base and not groundwork, record the address of that base too: create `.groundwork-source` at the project's root, with one line `https://host/path`, for example `https://github.com/team/base.git`. The update refuses an address that is not of that form, and a project without the file follows groundwork.
5. **Release** with the `release` workflow once the project has something to release. Its first version is computed from the project's commits, which start with the `Initial commit` of the template. That commit does not change the version.

### Choosing the ADRs a project synchronises

A project takes all the ADRs that its source reserves, or chooses ([ADR 1000](docs/adr/1000-choosing-the-adrs-a-project-synchronises.md)). The numbers fall in three zones:

- `0001` to `0999` are reserved for groundwork, and a project does not number an ADR of its own there. The checks fail if it does.
- A community base made from groundwork reserves more ranges, one `NNNN-NNNN` per line (bounds included, `#` for a comment) in a file `.groundwork-ranges`, which the update copies like any other file. A project reserves nothing and does not touch an ADR in a range that its source reserves.
- Every other number is the project's own. Choose the ranges of a base above the numbers that its projects already use, since a range cannot be reserved over an ADR that exists.

To choose, create `.groundwork-adrs` at the project's root: one number (`0003`) or one range (`0001-0999`) per line, `#` for a comment. A range adopts the ADRs that the source adds to it later. A number does not. Without the file, the project synchronises everything that the source reserves, as before. A number or a range that the source does not reserve, in the version the project moves to, stops the update, which says which line.

- ADR 0001 is always kept, and so are the ADRs that a listed ADR needs, according to the map [`.groundwork/practices.md`](.groundwork/practices.md). The update says which it adds (`added: 0002, 0003`) without changing the file.
- For an ADR that is left out, the update copies neither the ADR nor its files, and takes its blocks out of the files that several ADRs share before it merges. Delete them from the project's files with `apply_choice.py`, or by hand: a block of an ADR that is left out stays in place, and the update no longer changes it.
- For an ADR that enters the choice, because the project lists it or because an ADR it keeps needs it, the update applies it whole. The update recognises such an ADR when it is kept and the project has no file for its number: an ADR file that the project deletes while it keeps the ADR comes back at the next update.
- After it changes its choice, whether it adds ADRs or drops some, a project runs `python3 .groundwork/scripts/apply_choice.py` on a branch with a clean working tree. From the version that the project records, it brings the files and the blocks of the ADRs that entered, and the files that belong to no practice and that the project lacks (the scripts that the others need, the map `.groundwork/practices.md`, the update workflow). It deletes the files and the blocks of the ADRs that left. A file of that kind that the project already has is left as it is. A file or a block that the project changed is kept and listed, and the command exits with status 2. `--dry-run` shows the same list and changes no file of the working tree, nor the index or the branches. It refreshes the copy of the source's tags. Nothing is done without a `.groundwork-adrs`.
- A project writes its own lines outside the blocks of a shared file. Inside a block, a change by the project merges with a change in groundwork, as in any other file.
- The files of the update itself, `update_groundwork.py`, `apply_choice.py`, `open_update_pull_request.py` and the workflow, are always synchronised, together with `markers.py`, `practices_map.py` and `choice.py`, which the scripts use. The update never copies `README.md`, `LICENSE`, `.groundwork-version` or `.groundwork-adrs` from its source.

### Adopting in an existing project

A project that already exists has code that does not follow the rules, a history that may hold secrets, and checks that fail as soon as they are turned on. It adopts the practices one at a time, in the order of their dependencies, and records the gaps that remain so that the rules apply to the new code at once ([Recording the gaps](#recording-the-gaps)).

groundwork does not make a project compatible: the checks report what is not, and the project corrects it. The project has, before it starts:

- a branch of its own and a clean working tree, and [pre-commit](https://pre-commit.com) for the checks of ADR 0008;
- its own ADRs, if it has any, numbered from `1000` and following the template of [ADR 0001](docs/adr/0001-record-architecture-decisions.md), since `0001` to `0999` are reserved for groundwork. Once ADR 0001 is adopted, `check_adrs.py` lists each one that does not.

For each step:

1. **Record** the version once: create `.groundwork-version` with one line `X.Y.Z`, the latest release that has `apply_choice.py`, and `.groundwork-source` with one line `https://host/path` if the project follows a community base and not groundwork.
2. **List** the ADRs of the step in `.groundwork-adrs`, with those of the steps before, one number or range per line, and commit the files you wrote: the command needs a clean working tree.
3. **Run** `python3 .groundwork/scripts/apply_choice.py --dry-run`, then without `--dry-run`. The first time, the project has no script yet: run the script of a clone of groundwork at the tag `vX.Y.Z` that you recorded, from the project's directory: `python3 <clone>/.groundwork/scripts/apply_choice.py`. It brings the scripts that the others need, and the project then has its own. It also brings the update workflow, which fails every week until the secret `GROUNDWORK_UPDATE_TOKEN` exists (see [Adopting groundwork](#adopting-groundwork)).
4. **Read** the output. `add:` is a new file; `merge:` a file merged into yours; `conflict:` a file that could not be merged, which holds markers to resolve or, if it is not text, is left as it is for you to choose between the two versions; `keep:` a project file that has the name of a file of groundwork and is kept as it is, which is expected until the ADR that owns that file is adopted. The status is 2 while some remain.
5. **Check** what the step says to check, resolve the conflicts, commit through a pull request, and start again with the next step.

A project that has its own mechanism for a practice, such as the check of its branch names, its sign-off of commits or the scripts of its CI, chooses for each practice: adopt groundwork's and remove its own, or keep its own and leave the ADR out of `.groundwork-adrs`.

The order follows the dependencies in the map [`.groundwork/practices.md`](.groundwork/practices.md). In the first phase, the records and the names:

- **ADR 0001**, record architecture decisions. It brings the ADR template and `check_adrs.py`. Expect gaps in the project's ADRs: the number, the title `# NNNN. …` and the line `**Status:**`. Check with `python3 .groundwork/scripts/check_adrs.py`.
- **ADR 0002**, Conventional Commits. It brings its lines of `CONTRIBUTING.md`. The hook that checks the titles comes with ADR 0008. The history is not rewritten, and `release.py` counts a past title that does not follow it as no change. Check that the new commits follow it.
- **ADR 0004**, English. A rule with lines of `CONTRIBUTING.md` and no check. Documents already written in another language stay; the new content is in English. Check by review.

The second phase, the workflow:

- **ADR 0003**, change workflow. It brings the issue and pull request templates, the default branch's ruleset, `apply_settings.py` and `check_pull_request.py`. After `apply_settings.py` the default branch rejects direct pushes. Check that a pull request from a branch `<type>/<issue>-<slug>` that closes its issue passes `check_pull_request.py`.
- **ADR 0005**, versions and releases. It brings the `release` workflow and `release.py`. The first version is computed from the commits since the last tag reachable from `HEAD`. State the public contract in the README of the project. Check with `python3 .groundwork/scripts/release.py`, which prints the version it would publish and tags nothing.
- **ADR 0006**, trunk-based development. Lines of `CONTRIBUTING.md` and of the pull request template. A long-lived branch of the project is merged or split. Check by review.
- **ADR 0007**, changes made with an agent. It brings `AGENTS.md`. The project's `AGENTS.md` is kept until the ADR is adopted, then merged by hand. Check by review.

The third phase, the checks:

- **ADR 0008**, automated checks. It brings `.pre-commit-config.yaml`, the `checks` workflow and the tools of its checks. This is where the gaps appear: the checks run on all the files and fail on the code that exists, and the scan of the history may find secrets. Record the gaps before the pull request. Keep the project's hooks in its own lines of `.pre-commit-config.yaml` and its jobs in `.github/workflows/project-checks.yml`, and add groundwork's. Check with `pre-commit run --all-files --hook-stage manual`.

The fourth phase, the rules that no tool checks:

- **ADR 0009**, test-first development. Code that has no test stays so. New behaviour is tested first. Check by review.
- **ADR 0010**, security of the code. Code that breaks a rule is a gap to record. Check by review.
- **ADR 0012**, responding to an incident. It brings `SECURITY.md`. The project's own is merged by hand. Check that it names who leads the response.
- **ADR 0011**, confidential and personal data. The project classifies its data in its documentation. Check by review.
- **ADR 0013**, licenses of the dependencies. The project writes the licenses it accepts. Check by review.
- **ADR 0014**, protecting the files of groundwork. It brings `.groundwork/CODEOWNERS.template` and a line of `AGENTS.md`. Copy the template to `.github/CODEOWNERS`, replace `@OWNER` and merge it. When someone other than the maintainer can approve, run `apply_settings.py --code-owner-review`, and add `--last-push-approval` for several reviewers. Check with `python3 .groundwork/scripts/apply_settings.py --dry-run --code-owner-review`, which names the approvals the ruleset would require.
- **ADR 0015**, logs and diagnostic. The project states its fields and the meaning of its levels in its documentation. Check by review.

### Recording the gaps

When an adopted rule fails on code that already exists, the project records the gap and does not lower the rule.

1. **One ADR of the project**, "Known deviations from groundwork", numbered from `1000` and following the template. Its decision is to apply the adopted ADRs and to tolerate the gaps listed in its table until the issues that remove them are closed. The table has a row per gap: the ADR of groundwork, what deviates (the check and the files, or the rule), why, and the issue that removes it. A row that goes is a clarification in the sense of ADR 0001: the decision does not change.
2. **An exclusion for a check**, in the entry of its hook in `.pre-commit-config.yaml`, which is the one configuration ADR 0008 asks for. One pattern per file that exists, anchored at both ends, with its dots escaped, and a comment that names the row:

   ```yaml
   repos:
     - repo: https://github.com/igorshubovych/markdownlint-cli
       rev: v0.49.1
       hooks:
         - id: markdownlint
           # deviation: ADR 1001, issue #42
           exclude: '^docs/old-notes\.md$'
   ```

   pre-commit matches `exclude` with `re.search`, so a pattern that is not anchored also excludes a new file of the same name, and the new code would not be checked. Never exclude a class of files, only files that exist.
3. **Closing a gap** is one pull request: it brings the file in line, removes its exclusion and its row.
4. **A secret in the history** is not a gap. Treat it as an incident ([ADR 0012](https://github.com/michelwils/groundwork/blob/main/docs/adr/0012-responding-to-an-incident.md)): revoke it first. Then write the findings that remain into a baseline, `gitleaks git --redact --report-path .gitleaks-baseline.json`, which holds no secret since `--redact` replaces it, add `--baseline-path .gitleaks-baseline.json` to the entry of the hook that scans the history, and add a row. A new secret still fails the check.
5. **A rule that no tool checks** is recorded in the same table, and the review stands for the check: a reviewer rejects new code that breaks it.

### Moving to a later version

A copy shares no history with groundwork and does not receive later changes. To move to a later version:

1. Read the [release notes](https://github.com/michelwils/groundwork/releases) of the versions in between. A minor version adds a rule or a file without breaking anything. A breaking change requires the project to change something, which the notes describe under that change. It is a major version, or a minor one while the major version is `0`.
2. Open an issue for the update, then run the script from a clean working tree, with the number of that issue:

   ```sh
   python3 .groundwork/scripts/update_groundwork.py <issue-number> [--to X.Y.Z]
   ```

   The script:

   - reads `.groundwork-version` and fetches the tags of its source, under their own prefix `groundwork/` so that they do not collide with the project's tags. The source is the address in `.groundwork-source`, or else groundwork, and the script says which it used (`source:`);
   - creates the branch `chore/<issue-number>-update-groundwork-to-v<X-Y-Z>`, and applies on it what changed between the two versions, file by file, keeping the project's changes;
   - leaves out `README.md` and `LICENSE`, which concern groundwork itself, and sets the new version in `.groundwork-version`;
   - goes to the latest version unless `--to` names another;
   - does not commit, push or open a pull request.

   **A project at v0.5.0 or before** does its first update with the script of the release it moves to, whether it has a choice or not. Its own script leaves out only `README.md` and `LICENSE`, so it would bring the ADRs numbered `1000` or more, which are decisions of groundwork, next to the project's own ADRs numbered from 1000. Clone groundwork at the tag of that release and run its script from the project's directory, as step 3 of [Adopting in an existing project](#adopting-in-an-existing-project) does: `python3 <clone>/.groundwork/scripts/update_groundwork.py <issue-number>`. Do it before the weekly workflow runs, or start the workflow by hand only after that update, since the workflow runs the project's script. If an update has already brought those ADRs, delete them, and restore the project's ADR 1000 if they replaced it.

   It ends with status 0 when the project is updated or already up to date, 1 on an error, and 2 when files are in conflict. It names them and leaves markers in them for you to resolve.
3. Commit the result like any other change, through the issue and a pull request.

#### Automatic update

The [`update-groundwork` workflow](.github/workflows/update-groundwork.yml) does this every week, and when started by hand. It runs [`.groundwork/scripts/open_update_pull_request.py`](.groundwork/scripts/open_update_pull_request.py), which runs the script above without an issue, commits the result on the branch `groundwork/update-to-v<X-Y-Z>`, pushes it and opens the pull request `chore: update groundwork to v<X.Y.Z>`. Like Dependabot's pull requests, that pull request has no issue ([ADR 0003](docs/adr/0003-change-workflow.md)), and the check of the branch name and closing line skips the prefix `groundwork/`.

- It opens nothing when the project is up to date, when a pull request from a branch `groundwork/…` is already open, or when the pull request for that version was closed without being merged. Close the pull request to skip a version: a later version is proposed again.
- When files are in conflict, the pull request is a draft that lists them, with the markers left in the files. Resolve them, then mark it ready.
- It does nothing where there is no `.groundwork-version`, such as in groundwork itself.
- It needs the secret `GROUNDWORK_UPDATE_TOKEN`: a [fine-grained personal access token](https://github.com/settings/personal-access-tokens/new) limited to the repository, with write access to contents, pull requests and workflows. A project that follows a private base needs more than this, since the update fetches the base with the token too: see [In a project of the base](.groundwork/community-base.md#in-a-project-of-the-base). A workflow's token cannot push changes to workflow files, and does not start the checks of the pull request without an approval. Create the secret once, and renew the token before it expires:

  ```sh
  gh secret set GROUNDWORK_UPDATE_TOKEN --repo <owner>/<repo>
  ```

## Working on groundwork

This repository contains documentation, configuration and the scripts, with their tests. Run every check with `pre-commit run --all-files --hook-stage manual` and the tests with `python3 -m unittest discover -s .groundwork/scripts -p 'test_*.py'` before committing. The scripts have dependencies, pinned in `.groundwork/scripts/requirements.txt`: install them once in a virtual environment, with `python3 -m venv .venv && .venv/bin/pip install -r .groundwork/scripts/requirements.txt`, and run the tests with `.venv/bin/python`. The same checks and tests run in CI on every pull request.

The scripts must be covered by their tests, in the statements and the branches, at least at 95 % of the total. CI requires it of a source of ADRs, which is groundwork or a community base, on a push to `main` and on a pull request that changes `.groundwork/scripts/` or the workflow `checks.yml`. A project runs the plain tests: all of them on a push to `main` and on a pull request that changes the scripts or the workflow (the update pull request does), and otherwise only those that read the files of the repository, since the scripts come from the update and the source has already tested them. Measure it with these commands, run with `.venv/bin/python` in place of `python3`. The report fails below the threshold, which is written in `.groundwork/scripts/coveragerc`:

```sh
python3 -m coverage run --rcfile=.groundwork/scripts/coveragerc -m unittest discover -s .groundwork/scripts -p 'test_*.py'
python3 -m coverage combine --rcfile=.groundwork/scripts/coveragerc
python3 -m coverage report --rcfile=.groundwork/scripts/coveragerc
```

The licenses accepted for the scripts' dependencies are MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC and PSF-2.0.

## Contributing

Changes go through an issue, a branch and a pull request, and commit messages follow Conventional Commits. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Michel Wils
