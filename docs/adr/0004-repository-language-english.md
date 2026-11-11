# 0004. Repository language is English

**Status:** accepted

## Context

The repository is public and meant to be reused, and its contents are read by people and tools. Mixing languages makes it harder to read, to search and to keep consistent. The language used in conversations about the repository is not necessarily the language of the repository itself.

## Decision

We will write all repository content in English.

- **Covered:** documentation, ADRs, issues, pull requests, commit messages, code comments and identifiers.
- **Not covered:** conversations held outside the repository, in any language.

## Consequences

- The repository reads as a single document, whoever wrote a given part.
- Contributors who are more comfortable in another language must write in English, which can slow them down or reduce precision.
- Content written elsewhere, for example in a discussion, has to be translated before it is added to the repository.

## Options considered

- **The language of each contributor or of the maintainers.** A mix of languages is harder to read, to search and to keep consistent, and the repository is meant to be reused.
- **Code in English and documentation in another language.** The same people read both, and identifiers and documents refer to each other, so a split makes the search and the consistency worse.
