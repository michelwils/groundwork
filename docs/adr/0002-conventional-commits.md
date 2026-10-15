# 0002. Conventional Commits

**Status:** accepted

## Context

Commit messages are the most detailed record of how the repository changed. Without a shared format they are inconsistent, hard to scan, and cannot be read by tools, for example to derive a version or a changelog.

## Decision

We will write every commit message following [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/):

    <type>[(scope)][!]: <description>

    [body]

    [footers]

- **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore` and `revert`, the set popularised by the Angular commit guidelines and used by most Conventional Commits tooling. No other type is used.
- **Scope:** optional. When used, it is a single lowercase word naming the part of the repository that changes, for example `docs(adr): …`. A change that spans several parts has no scope.
- **Description:** imperative mood, lowercase, no trailing period, short enough to read in one line.
- **Body:** optional, explains why the change was made rather than what it does.
- **Footers:** follow the git trailer format, for example `Refs #12` or `Co-Authored-By: …`.
- **Breaking changes:** a change that is not backward compatible is marked with `!` before the colon and has a `BREAKING CHANGE:` footer that describes what breaks and how to migrate.

## Consequences

- The history can be scanned by type and read by tools.
- Every commit needs a type, which takes a moment to choose. A commit that fits two types is usually a sign it should be split.
- What each type or a breaking change means for the version is not defined here. It is the subject of the versioning decision.
- Nothing enforces the format yet. Checking messages automatically is left to later tooling.
