# 0008. Automated checks

**Status:** accepted

## Context

The conventions of a project, such as the format of commit messages or the rules for changes made with an agent, are only checked by review. Mechanical mistakes are found late and take the time of the reviewer. A check that runs on the contributor's machine can be skipped or missing, so the same checks must also run where nobody can skip them.

## Decision

We will check the repository automatically, in two places, from one configuration.

- **Before each commit.** Checks run on the commit's files and message, on the contributor's machine, through hooks installed from the repository's configuration.
- **In CI.** The same checks run on all files for every pull request and for the main branch. Checks of the pull request are added: its title, since it becomes the commit title on the main branch, and its branch name and closing line, which tie it to its issue.
- **Locally.** Before a change is presented, committed or marked ready, the contributor runs the checks as the CI runs them: on all the files, with the hooks of every stage, and with the tests of the project. A plain `pre-commit run --all-files` leaves out the hooks of the `manual` stage, such as the scan of the history for secrets, and no hook runs the tests. The checks of the pull request exist once it is open and are left to the CI.
- **One configuration.** The checks are defined once, in a file of the repository, and each tool is used at a pinned version. Both places therefore run the same checks.
- **A failing check blocks the change.** A commit whose check fails is not made, and a pull request whose check fails is not merged.
- **No bypass.** A check is never skipped or disabled to get a change through, except for the merge of the fix of a vulnerability that is not public yet, which no check can reach. A check that is wrong or too strict is changed or removed in a pull request that explains why.
- **Checks of the project.** A project writes its hooks below the comment that ends the configuration of groundwork, in repositories of its own with a `repo: local` of its own for its local hooks, and its jobs in `.github/workflows/project-checks.yml`, which groundwork brings with one job that does nothing and does not change afterwards.
  - The job `checks`, the one that the ruleset of the repository requires, waits for the jobs of groundwork and for those of the project, so a job of the project is required with no change to the ruleset.
  - The entries for the ecosystems of its stack go in `.github/dependabot.yml`, below the comment that ends the entries of groundwork, and take the delay, the commit prefix and a group that those have, so that the title of an update follows the format of the commits.
  - **One pull request per dependency.** What groundwork owns, the hooks of `.pre-commit-config.yaml`, the workflows other than `project-checks.yml` and `.groundwork/scripts`, is updated by Dependabot in the source of ADRs only, and a project gets the change through the update of groundwork. The entries for it are in a block `# groundwork:source` of `.github/dependabot.yml` that the update does not bring and that a new project takes out. A base puts the entries of its own in a block of the same name, below the comment of the project.
  - **An entry stays outside the block.** Dependabot refuses a file with no entry and two entries for the same ecosystem and directory (measured on a test repository, #236), so a project with no entry of its own keeps one for `github-actions` on `/.groundwork`, with `open-pull-requests-limit: 0`. It opens no pull request and does not collide with an entry of the project on `/`.
  - **A project that follows its own workflows and hooks** adds entries below the comment and excludes what groundwork owns. For `github-actions` on `/`, `exclude-paths` lists `.github/workflows/checks.yml`, `.github/workflows/release.yml` and `.github/workflows/update-groundwork.yml`. For `pre-commit`, `ignore` gives the full address of each repository of groundwork's hooks, since the short name does not match: `https://github.com/gitleaks/gitleaks`, `https://github.com/igorshubovych/markdownlint-cli`, `https://github.com/editorconfig-checker/editorconfig-checker`, `https://github.com/zizmorcore/zizmor-pre-commit` and `https://github.com/pypa/pip-audit`. A test fails when a workflow or a repository of groundwork is missing from this list, so a change of groundwork brings the list with it.
  - A check that needs more permissions than `checks.yml` gives, or that does not gate a merge, goes in a workflow of its own.
- **Baseline checks.** Whatever its stack, a project checks the format of its commit messages, the presence of secrets and the format of its documentation. It adds the checks of its own stack to the same configuration.
- **Audit of the dependencies.** A project configures, for its stack, a check that fails when a dependency has a known vulnerability, in the same configuration and in the CI. A project whose stack has no such tool writes the exception and its reason in its `AGENTS.md`.

## Consequences

- Mechanical mistakes are found before the review, which can concentrate on the content.
- Contributors need the tool that runs the hooks. One who does not install it is caught later, by the CI.
- The pinned versions age and are updated by hand, as any other change.
- The CI keeps the environments of the hooks in a cache, since installing them is most of its time. The key follows the configuration, the version of pre-commit and the Python that it runs with, with no fallback to another key.
  - The first run that installs them saves them, even when a check fails. A cache entry is never overwritten, so a run that stopped in the middle of the installation leaves an entry with fewer environments, which pre-commit completes at each run until the key changes or the entry is evicted.
  - A pull request restores the cache that a push to the main branch saved and writes only in its own scope, so it cannot change what the main branch restores.
  - GitHub evicts an entry that nobody reads for some days (seven when this was written), and the next run installs the environments again: when the CI gets slow, look at the cache of the main branch.
- An edit of the title or of the description of a pull request starts a run of its own, in a concurrency group of its own, so that it does not cancel the run of a push and is not cancelled by it. The run that the platform shows is the last one created, as it was seen when an edit cancelled the run of a push and left a cancelled run as the last one. An edit runs all the checks again, on the same code as the push, so that the last run created never hides a failure of the push. It costs a second run of the tests per edit.
- The job `checks` waits for two others, which is one more job per run. It runs even when they fail or are skipped, since the platform counts a skipped job as a success, but not when the run is cancelled, and it fails unless both succeeded.
- A project that changed `checks.yml` to add its jobs merges its change with the update, and moves them to `project-checks.yml`.
- There is no single command that runs everything. A hook of the `manual` stage for the tests would run them twice in the CI, where the step of the hooks also runs that stage, and the steps of the tests cannot go: they depend on the kind of repository and on what changed. In a project it would run the tests that its CI skips when the scripts did not change. A script that copied the conditions of the workflow would drift from it, and one that only wrapped the two commands would add a file to keep for the saving of one line. The contributor runs the hooks and the tests with two commands, which `CONTRIBUTING.md` gives.
- A project that already added entries at the end of `.github/dependabot.yml` or hooks at the end of `.pre-commit-config.yaml` has one conflict per file, when the update brings the comment that ends the entries of groundwork, and moves them below it.
- A project that changed an entry of groundwork in `.github/dependabot.yml` has a conflict at the first update that takes the entries out. A project that had Dependabot propose the updates of its own workflows or hooks through the entries of groundwork receives none until it adds the entries above.
- The alerts of security of Dependabot are set in the settings of the repository, not in `.github/dependabot.yml`: each repository keeps its own.
- A check that rejects valid work costs time until it is fixed.
- Rules that need judgement, such as whether the type of a commit is right, stay with the review.
- The condition that a pull request's checks pass before it is merged can be verified.
- A new advisory fails the audit of every pull request until the dependency is updated, which is the intent.
- The audit sees a vulnerability only when a pull request runs it. The platform's alerts and security updates, which the settings script turns on, tell when one is found after the merge.
