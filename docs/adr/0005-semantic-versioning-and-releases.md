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
| --- | --- |
| any type with `!` or a `BREAKING CHANGE:` footer | major |
| `feat` | minor |
| `fix`, `perf` | patch |
| `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`, `revert` | none |

A `revert` that undoes released behaviour users rely on is marked as a breaking change with `!`. A `revert` of a change in the same release is ignored with it, as the Releases section says.

**Initial development.** While the major version is `0`, nothing is stable and versions start from `0.0.0`. A breaking change or a `feat` increments the minor version, and a `fix` or a `perf` increments the patch version. A first release that contains a `feat` is therefore `0.1.0`. The major version becomes `1` only when the maintainers decide, as described below.

**Version `1.0.0`.** It is tagged when the maintainers consider the public contract stable enough to be relied on. It may be tagged on a commit that has no change since the previous release, as a statement of confidence.

**Tags.** A version is tagged `vMAJOR.MINOR.PATCH` with an annotated tag, on `main`, or on the branch that maintains an older major version, for a fix to it. Pre-release identifiers are not used. The tag and the content of a published release are never changed. A defective release is corrected by the next version, and the immutable releases setting of the hosting platform enforces this.

**Origin.** With the immutable releases setting of the hosting platform, a published release carries an attestation, which records its tag, its commit and its assets. A user checks a release with `gh release verify <tag>`, and a downloaded asset with `gh release verify-asset <tag> <file>`. The source archives are not covered, since the platform creates them when they are requested. A project that publishes an artifact built by its workflow attests it where the platform allows it, so that a user can check it with `gh attestation verify`. A software bill of materials may be published, and is not required.

**Releases.** A release is made when the maintainers decide, not on every merge. Between releases, `main` carries no version. The maintainers start a workflow that makes the release in three steps:

1. It decides the version from the commits on `main`, or on the maintenance branch, since the previous tag. The version is incremented once, by the highest increment among those commits: ten `feat` commits and three `fix` commits give one minor increment. A change is undone when a later `revert` repeats its description in its title ([ADR 0002](0002-conventional-commits.md)), and it is then ignored together with that `revert`, even when the `revert` is marked with `!`, since the change it undoes was not released. The maintainers can give the version instead, for example to tag `1.0.0`. The workflow refuses a version that is not greater than the previous one, or whose tag already exists.
2. It tags `main`, or the maintenance branch, with `v<version>`.
3. It publishes a release for the tag on the hosting platform. Its notes list the changes since the previous release, grouped by commit type, from the commit titles, without the changes that were undone. A release made on a maintenance branch is not marked as the latest one.

The workflow can run without publishing, to show the version and the notes. The release notes are the changelog. There is no changelog file.

## Consequences

- A version number tells users whether they must act.
- The commit title decides the version, so choosing the right type matters and is part of reviewing a pull request.
- A project must state its public contract in its README. Until it does, the major and minor increments cannot be applied.
- A release is started by hand and made by a workflow, so that the version follows the rules above. A change undone in another way than by a `revert`, such as by switching a feature off, is not recognised: the maintainers give the version.
- A release is made from `main`, or from the branch that maintains an older major version, for a fix to it.
- The changelog depends on commit titles being accurate.
- A mistake in a published release cannot be corrected under the same version. The next version carries the fix, and the name of a deleted release's tag cannot be used again.
