# 0009. Test-first development

**Status:** accepted

## Context

A test written after the code tends to confirm what the code does, not what was required, and it is the first thing dropped when time is short. A test written first states the expected behaviour before any code exists, and it is seen to fail, which shows that it can. Coding agents fall into it often: they write tests that mirror their own code, or change a test until it passes. The practice does not depend on a language or a technology stack.

## Decision

We will write the test of a change of behaviour before the code that makes it pass.

- **Cycle.** The test is written and run, and it fails because the behaviour is missing, not because of a mistake in the test or in its setup. The code that makes it pass is then written, and the code is improved with the tests passing, without adding behaviour that has no test.
- **Bug fixes.** A bug is first reproduced by a test that fails. The test passes with the fix and stays as a regression test.
- **Changing a test.** A test changes only when the requirement changes, in the pull request that changes the requirement, which says so. A test is never changed to make code pass.
- **Exceptions.** A change that does not alter behaviour needs no new test: documentation, configuration, formatting, a dependency update, or a refactoring covered by existing tests. A change of behaviour that cannot be tested affordably says in the description of its pull request why, and how it was checked instead.
- **Merging.** The test and the code that makes it pass are in the same pull request, so `main` never holds a failing test ([ADR 0006](0006-trunk-based-development.md)).
- **Project choices.** Each project chooses and documents its test framework, its test commands, the kinds of tests it writes and the coverage it requires, if any.

## Consequences

- The tests state the expected behaviour before the code, and a reviewer can read them as the requirements of the change.
- Each fix leaves a regression test behind, and the suite grows with the project.
- A test that passes the first time it runs proves nothing, and is a sign that the behaviour already existed or that the test is wrong.
- Code that is hard to test first has to be designed differently, which costs time at the start of a change.
- No tool can check that the test was written first. It shows in the order of the commits of the pull request, which squash removes from `main`, and it relies on review and on the report of the agent when it could not follow the practice ([ADR 0007](0007-ai-assisted-changes.md)).
- Writing the test first does not make it a good test, and it sets no level of coverage.
