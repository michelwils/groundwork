# 1002. Requiring a minimal coverage of the scripts

**Status:** accepted

## Context

groundwork is also a project. Its scripts, about 1 600 statements in `.groundwork/scripts/`, have about 500 unit tests, and nothing shows what those tests run. [ADR 0009](0009-test-first-development.md) leaves to each project the coverage it requires, if any, and groundwork does not synchronise a requirement of coverage with its practices. Removing the tests that overlap needs a measure that shows that the code is still run.

The tests run many of the scripts in a subprocess, so a measure of the process of the tests alone would miss most of `update_groundwork.py` and `apply_choice.py`. Measured with coverage.py 7.16.2 (`patch = subprocess`, then `coverage combine`) on the day of this decision, the scripts are covered at 96 % of their statements and branches, 97 % of their statements alone.

A project that left ADRs out has fewer scripts and fewer tests, and it runs the same workflow.

## Decision

We will require that the unit tests cover at least 95 % of the scripts, in the CI of a source of ADRs.

- **What is measured.** The statements and the branches of the scripts of `.groundwork/scripts/`, without the test files. The code that a test runs in a subprocess is counted.
- **The level.** 95 % of the total of the statements and the branches. The documentation of coverage.py describes a level for the total only (`fail_under`), not one per file. The threshold is written in `.groundwork/scripts/coveragerc` and in the Project section of `AGENTS.md`.
- **The tool.** coverage.py, under the license Apache-2.0, which `AGENTS.md` lists among the licenses accepted for the dependencies of the scripts. It is pinned at an exact version in `.groundwork/scripts/requirements.txt`, so that Dependabot updates it and the audit of the dependencies reads it.
- **Where.** In the CI of a source of ADRs, that is a repository without `.groundwork-version` or one that sets the variable `GROUNDWORK_SOURCE` to `true`. A project runs the plain tests.
- **When.** On a push to the main branch, and on a pull request that changes a file under `.groundwork/scripts/` or the workflow `checks.yml`. The coverage can change only with them, so any other pull request runs the plain tests. The decision is a step of the job, not a filter on the workflow, so that no required check is skipped.
- **Lowering it.** A change that brings the coverage under the level adds tests. The level is lowered only by a change of this ADR.

## Consequences

- The measure is about 45 seconds longer: 122 seconds against 75 without, on a developer machine, and more in the CI. It costs a source only on the pushes to the main branch and on the pull requests that change the scripts or the workflow.
- A pull request outside the scripts that lowers the coverage, because some tests read the real files, is seen at the next push to the main branch only.
- The margin is one point. An update of coverage.py can change how the branches are counted, and the pull request that brings it fixes the tests or the level.
- The least covered scripts are `apply_choice.py` (90 %) and `run_with_requirements.py` (88 %). The total is above the level, so no issue is opened for them.
- The environment that `run_with_requirements.py` makes for the hook that checks the links installs coverage.py too, since it takes all the requirements.
- A community base that sets the variable gets the same requirement, and the scripts it left out change its percentage.
- A project receives the configuration and the step of the workflow, and does not run the measure.

## Options considered

- **The statements alone.** It is simpler, and it does not see a branch that no test takes.
- **A level per file.** The documentation of coverage.py describes none, and a script written by hand to enforce one would be one more script to test.
- **The level for every project.** It would fail a project that left ADRs out for a reason that has nothing to do with it, and ADR 0009 leaves coverage to the projects.
- **A higher level, such as 96 % or 97 %.** It leaves no margin for the differences of a platform.
