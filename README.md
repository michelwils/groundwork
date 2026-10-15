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
- Pre-commit checks and baseline CI that do not depend on a language or technology stack

## What it does not cover

Anything specific to a language, technology stack or type of application: code formatting and linting, tests, dependency updates, dev environment, publishing, reference architecture and operations. That belongs in the projects that adopt groundwork.

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
|---|---|---|
| any type with `!` | A rule is reversed, or a file is removed, renamed or changed so that it no longer does what projects rely on | major |
| `feat` | A rule or a file is added | minor |
| `fix`, `perf` | A rule is clarified without changing its meaning, or a file is improved without changing what it does | patch |
| `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore`, `revert` | Anything outside the contract: the README, the Context and Consequences sections of ADRs, wording | none |

While groundwork is at `0.y.z`, a breaking change increments the minor version and the other changes increment the patch version.

## Contributing

Changes go through an issue, a branch and a pull request, and commit messages follow Conventional Commits. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © 2026 Michel Wils
