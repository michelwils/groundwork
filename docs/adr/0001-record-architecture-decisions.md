# 0001. Record architecture decisions

**Status:** accepted

## Context

groundwork is a set of choices about how projects are structured and run. Without a written record, the reasons behind those choices are forgotten, and later changes either repeat past discussions or undo decisions by accident.

## Decision

We will record each significant decision as an Architecture Decision Record (ADR), using the format proposed by Michael Nygard: context, decision, consequences.

- **Location:** `docs/adr/`.
- **Naming:** `NNNN-title-in-kebab-case.md`, where `NNNN` is a four-digit sequence number. Numbers are never reused. The numbers `0001` to `0999` are reserved for the ADRs of groundwork, and the ADRs of a project start at `1000`: a number starting with `0` is a groundwork ADR, any other is the project's.
- **Template:** `docs/adr/template.md`.
- **Statuses:** `proposed`, `accepted`, `rejected`, and `superseded by NNNN`.
- **Changing a decision:** an accepted ADR may be clarified in place when its meaning does not change (wording, missing detail, broken links). A decision that is reversed or contradicted is replaced by a new ADR, and the old one is updated only to set its status to `superseded by NNNN`.
- **Writing:** ADRs are written in English, short, and describe one decision each.

## Consequences

- The reasons for every significant decision stay in the repository, next to the code and the history.
- Each decision costs a short document, which is overhead for small choices. Not every choice needs an ADR.
- The history of a decision is read by following the chain of superseded ADRs.
- An ADR added by groundwork never takes the number of an ADR of a project, so moving a project to a later version does not conflict on file names or references.
- A clarification and a replacement are told apart by one question: would someone relying on the old text be surprised by the new one?
