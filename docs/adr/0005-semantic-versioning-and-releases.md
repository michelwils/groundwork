# 0005. Semantic Versioning and releases

**Status:** accepted

## Context

Users and maintainers of a project need to know what a new version means: whether they must change something, or can update freely. [ADR 0002](0002-conventional-commits.md) defines commit messages but does not say what they mean for the version.

## Decision

We will version the project with [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

**Public contract.** The project states in its README what its users rely on, such as an API, a file format, a command line or a configuration. This is its public contract, and the increments below are defined against it. Anything outside it can change without affecting the version.

**Version increments.**

- **Major:** the contract is broken. A user who followed the previous version must change something.
- **Minor:** something is added to the contract, and users of the previous version do not have to change anything.
- **Patch:** the project is corrected or improved without any change to the contract.

**Commit types.** The type of a commit sets the increment:

| Type | Version |
|---|---|
| any type with `!` or a `BREAKING CHANGE:` footer | major |
| `feat` | minor |
| `fix`, `perf` | patch |
| `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`, `revert` | none |

A `revert` that undoes released behaviour users rely on is marked as a breaking change with `!`.

**Initial development.** While the major version is `0`, nothing is stable and versions start from `0.0.0`. A breaking change or a `feat` increments the minor version, and a `fix` or a `perf` increments the patch version. A first release that contains a `feat` is therefore `0.1.0`. The major version becomes `1` only when the maintainers decide, as described below.

**Version `1.0.0`.** It is tagged when the maintainers consider the public contract stable enough to be relied on. It may be tagged on a commit that has no change since the previous release, as a statement of confidence.

**Tags.** A version is tagged `vMAJOR.MINOR.PATCH` on `main`, with an annotated tag. Pre-release identifiers are not used.

**Releases.** A release is made by hand, when the maintainers decide, not on every merge. Between releases, `main` carries no version. To make a release:

1. Decide the version from the commits on `main` since the previous tag. The version is incremented once, by the highest increment among those commits: ten `feat` commits and three `fix` commits give one minor increment.
2. Tag `main` with `v<version>`.
3. Publish a release for the tag on the hosting platform. Its notes list the changes since the previous release, grouped by commit type, from the commit titles.

The release notes are the changelog. There is no changelog file.

## Consequences

- A version number tells users whether they must act.
- The commit title decides the version, so choosing the right type matters and is part of reviewing a pull request.
- A project must state its public contract in its README. Until it does, the major and minor increments cannot be applied.
- Releases are made by hand until they are automated, which is the subject of a later decision.
- Every release is made from `main`. Releasing a fix for an older version while `main` holds unreleased changes is not covered.
- The changelog depends on commit titles being accurate.
