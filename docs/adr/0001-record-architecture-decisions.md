# 0001. Record architecture decisions

**Status:** accepted

## Context

groundwork is a set of choices about how projects are structured and run. Without a written record, the reasons behind those choices are forgotten, and later changes either repeat past discussions or undo decisions by accident.

## Decision

We will record each significant decision as an Architecture Decision Record (ADR), using the format proposed by Michael Nygard: context, decision, consequences.

- **Location:** `docs/adr/`.
- **Naming:** `NNNN-title-in-kebab-case.md`, where `NNNN` is a four-digit sequence number. Numbers are never reused.
- **Ranges:** a source of ADRs reserves a range of numbers by announcing it, and a project does not create an ADR in a range that its source reserves. groundwork reserves `0001` to `0999`. A community that creates its own base from groundwork may reserve other ranges, declared in the file `.groundwork-ranges` at its root. The file holds one range `NNNN-NNNN` per line, bounds included, the first not above the second, and a line that starts with `#` is a comment. A line that does not follow this format is refused, and a range overlaps neither `0001` to `0999` nor another range. Without the file, a source reserves `0001` to `0999` only. A project reads the reserved ranges from this file, which it receives from its source. In each range it reserves, a source numbers its ADRs from the first number of the range, without skipping any.
- **The project:** every number that no range reserves is free. A project numbers its own ADRs from the first number that no range reserves, which is `1000` when its source reserves `0001` to `0999` only, and skips only the numbers in a reserved range. groundwork is itself a project: its own decisions that do not apply to the projects that adopt it are numbered from `1000`, outside what it reserves, and are not synchronised.
- **Template:** `docs/adr/template.md`.
- **Statuses:** `proposed`, `accepted`, `rejected`, and `superseded by NNNN`.
- **Changing a decision:** an accepted ADR may be clarified in place when its meaning does not change (wording, missing detail, broken links). A decision that is reversed or contradicted is replaced by a new ADR, and the old one is updated only to set its status to `superseded by NNNN`.
- **Writing:** ADRs are written in English, short, and describe one decision each.

## Consequences

- The reasons for every significant decision stay in the repository, next to the code and the history.
- Each decision costs a short document, which is overhead for small choices. Not every choice needs an ADR.
- The history of a decision is read by following the chain of superseded ADRs.
- An ADR added by groundwork or by a community base never takes the number of a project's ADR, so moving a project to a later version does not conflict on file names or references.
- A community that reserves a range in which projects already have ADRs makes those projects renumber them. It reserves a range above the numbers its projects use.
- A clarification and a replacement are told apart by one question: would someone relying on the old text be surprised by the new one?
