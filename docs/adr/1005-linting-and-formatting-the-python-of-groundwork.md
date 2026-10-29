# 1005. Linting and formatting the Python of groundwork

**Status:** accepted

## Context

groundwork is also a project. Its scripts and their tests, in `.groundwork/scripts/`, are Python, and no tool checks them: about 280 lines are longer than 120 columns, the layout is uneven, and nothing stops an import that is not used. groundwork leaves the tools of a language to the projects, since it covers no stack, so a check of its own Python is a decision of groundwork as a project, numbered from `1000` as [ADR 0001](0001-record-architecture-decisions.md) says, and it is not synchronised.

The files that a project receives are the scripts, `.pre-commit-config.yaml` and the workflow `checks.yml`, among others. A hook added to `.pre-commit-config.yaml` above the line of the project, or below it, reaches every project at the next update, and each project would lint scripts that it does not edit.

## Decision

We will lint and format the Python of `.groundwork/scripts/` with Ruff, in the CI of a source of ADRs.

- **The tool.** Ruff, under the MIT license, which the README lists among the licenses accepted for the dependencies of the scripts ([ADR 0013](0013-licenses-of-the-dependencies.md)). It lints (`ruff check`) and formats (`ruff format --check`) with one dependency. It is pinned at an exact version in `.groundwork/scripts/requirements.txt`, where Dependabot updates it and the audit of the dependencies reads it, as for coverage.py ([ADR 1002](1002-requiring-a-minimal-coverage-of-the-scripts.md)).
- **What is checked.** All the Python files of `.groundwork/scripts/`, tests included, with the configuration of `.groundwork/scripts/ruff.toml`: lines of 120 columns at most, the default rules of Ruff (the errors of pycodestyle and Pyflakes) and the order of the imports. A stricter set of rules is left out: it asks for changes of code, which this decision does not.
- **Where.** A step of the job `groundwork` of the workflow `checks.yml`, which runs in a source of ADRs (a repository without `.groundwork-version`, or one that sets the variable `GROUNDWORK_SOURCE` to `true`) and in no project. It runs at each run of the workflow, whatever changed, since it takes about a second. It is not a hook of `.pre-commit-config.yaml`.
- **Locally.** The README gives the two commands, which the contributor runs before presenting a change, with the other checks.
- **Updating the tool.** A new version of Ruff may change the layout. The pull request that brings it also brings the reformatting that the check then asks for.

## Consequences

- The Python of groundwork has one layout and no unused import, and a review reads the changes of a script and not those of its layout.
- The check is a step of the CI and not a hook, as is the measure of the coverage, so `pre-commit run` does not run it. A change that breaks it is seen when the contributor runs the commands of the README, or in the CI.
- A project receives Ruff with the other dependencies of the scripts, in the environment of the CI and in the one that `run_with_requirements.py` makes for the hook that checks the links, and does not run it. It receives `ruff.toml` too, which only applies to the folder of the scripts, so a project that uses Ruff for its own code is not affected.
- A community base is a source of ADRs, and gets the same check.
- The first application reformats most of the files of the scripts, and fixes the few errors of the rules. The reformatting is a commit of its own, so that `git blame` can skip it.
- The commands run from the root of the repository: `ruff.toml` names the folder of the scripts as the source root, so that the scripts, which import each other, are not taken for dependencies.

## Options considered

- **A hook of `.pre-commit-config.yaml`.** It runs before each commit, and it reaches every project at the next update, which then runs a check of files that it does not edit.
- **Black and a linter such as Flake8.** Two tools and two dependencies for what one does.
- **The default length of 88 columns.** It reformats many more lines, for scripts written for 120 columns.
- **No tool.** It leaves the layout to each author, which is the situation that this decision is meant to change.
