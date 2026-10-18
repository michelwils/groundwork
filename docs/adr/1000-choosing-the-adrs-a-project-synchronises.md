# 1000. Choosing the ADRs a project synchronises

**Status:** accepted

## Context

A project copies all of groundwork, and the update script merges, file by file, what changed between two versions. A project that does not want a practice has no clean way to leave it out: if it deletes a file that groundwork changes later, the script reports a conflict at each update that changes it. A team that adopts groundwork in an existing project, or a community that keeps some of its decisions and not others, needs to choose.

Two things make the choice possible. The map of the practices, `docs/practices.md`, gives for each ADR its files, its lines in the shared files and the ADRs it needs. The text of each ADR names only the ADRs it needs, so the ADRs a project keeps, with the ones they need, hold together with no reference to an ADR the project does not have.

This ADR is a decision of groundwork as a project, numbered from `1000` as [ADR 0001](0001-record-architecture-decisions.md) says, and it is not synchronised.

## Decision

We will let a project choose the ADRs of groundwork it synchronises, in a file, and have the update apply that choice.

- **The choice.** The file `.groundwork-adrs`, at the root of the project, lists the ADRs it keeps, one number of four digits, such as `0003`, or one range, such as `0001-0999`, per line. A number adopts one ADR. A range adopts every ADR it contains, including the ones that the source adds to it later. A line that starts with `#` is a comment. The update refuses a line that is neither, and a number or a range that does not lie wholly within a range that the source reserves ([ADR 0001](0001-record-architecture-decisions.md)), and says which. It accepts `0001`, which changes nothing. Without the file, everything that the source reserves is synchronised, as before. `.groundwork-version` keeps its name and its format. With the file, only the ADRs it lists are, and the ones they need.
- **What follows.** An ADR needs the ADRs that the map of the version the project moves to gives it, and so on in turn. An ADR of a community base may need an ADR of groundwork, and an ADR of groundwork never needs one of a community base. The update adds them to the choice it applies, without changing the file, and says which. The project does not have to list them.
- **ADR 0001.** It is always kept: it defines the ADRs, their numbers and the template that everything else relies on.
- **The files.** The update copies neither the ADR nor the files that the map gives for an ADR that is left out. The files that the map gives to no ADR, such as `docs/practices.md`, are always synchronised.
- **The files that several ADRs share.** A file that carries lines of several ADRs belongs to one of them in the map, and the lines of the other ADRs are delimited by markers per ADR. A file that belongs to no ADR has all its lines of an ADR in blocks. Before it merges, the update removes the blocks of the ADRs that are left out from both versions of groundwork, so that these blocks, removed or not by the project, raise no conflict. The project deletes them from its files.
- **Later ADRs.** An ADR that the source adds after the choice is not adopted unless a range or a number of the choice covers it. An ADR that enters the choice, whether the project lists it or an ADR it keeps now needs it, is applied whole, from nothing. An ADR that leaves the choice is no longer updated, and its files are not deleted: the project deletes them.
- **The numbers.** The check of the ADRs accepts a missing number of a range that the source reserves only when the choice of the project, with what it needs, leaves it out.
- **The reserved ranges.** Only the ADRs of the ranges that the source reserves are synchronised. groundwork reserves `0001` to `0999`, so its own decisions, numbered from `1000`, are not. A community base declares the ranges it adds in `.groundwork-ranges`, a file of the base that is synchronised like any other.
- **What a project can rely on.** When it keeps some of the ADRs: the `Decision` of the ADRs it keeps and the ones they need, the files that the map gives for them, `.groundwork-version`, and the name and the format of `.groundwork-adrs` and of `.groundwork-ranges`. A project that chooses nothing relies on the same as before.

## Consequences

- A project adopts practices one at a time and leaves out the others, and the update raises no conflict for what it left out.
- The unit of the choice is the ADR with its files and its lines. A practice cannot be kept in part.
- Keeping one ADR can bring others. The update says which, and the project can drop the first one rather than keep what it did not want.
- The map and the markers must stay true: the check of the map verifies the files, the texts of the ADRs, the markers and the blocks of the lines that several ADRs share.
- The shared files carry markers, which are comments, and which a project that chooses nothing can ignore.
- A project that lists ADRs does not receive the later ones by itself. It reads the release notes and adds what it wants.
- A community that builds its own base from groundwork reserves its ranges in `.groundwork-ranges`. A project takes the ADRs of its source whole, with a range for each range reserved, or chooses among them. It does not use a number of a reserved range for an ADR of its own.
- The choice is a file of the project, reviewed like any other change. What a project can rely on depends on it.

## Options considered

- **A list of ignored paths.** It is simple and needs no map. It does not see that an ADR needs another, it leaves the lines of the shared files that name what was left out, and each project has to find the paths.
- **A fork that deletes what it does not want.** It needs no tool, and every update that touches a deleted file is a conflict, which is the problem to solve.
