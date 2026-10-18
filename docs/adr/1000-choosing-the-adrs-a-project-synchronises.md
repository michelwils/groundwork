# 1000. Choosing the ADRs a project synchronises

**Status:** accepted

## Context

A project copies all of groundwork, and the update script merges, file by file, what changed between two versions. A project that does not want a practice has no clean way to leave it out: if it deletes a file that groundwork changes later, the script reports a conflict at each update that changes it. A team that adopts groundwork in an existing project, or a community that keeps some of its decisions and not others, needs to choose.

Two things make the choice possible. The map of the practices, `docs/practices.md`, gives for each ADR its files, its lines in the shared files and the ADRs it needs. The text of each ADR names only the ADRs it needs, so the ADRs a project keeps, with the ones they need, hold together with no reference to an ADR the project does not have.

This ADR is a decision of groundwork as a project, numbered from `1000` as [ADR 0001](0001-record-architecture-decisions.md) says, and it is not synchronised.

## Decision

We will let a project choose the ADRs of groundwork it synchronises, in a file, and have the update apply that choice.

- **The choice.** The file `.groundwork-adrs`, at the root of the project, lists the ADRs it keeps, one number of four digits per line, such as `0003`. A line that starts with `#` is a comment. The update refuses a number that is not an ADR of groundwork, and accepts `0001`, which changes nothing. Without the file, everything is synchronised, as before. `.groundwork-version` keeps its name and its format. With the file, only the ADRs it lists are, and the ones they need.
- **What follows.** An ADR needs the ADRs that the map of the version the project moves to gives it, and so on in turn. The update adds them to the choice it applies, without changing the file, and says which. The project does not have to list them.
- **ADR 0001.** It is always kept: it defines the ADRs, their numbers and the template that everything else relies on.
- **The files.** The update copies neither the ADR nor the files that the map gives for an ADR that is left out. The files that the map gives to no ADR, such as `docs/practices.md`, are always synchronised.
- **The files that several ADRs share.** A file that carries lines of several ADRs belongs to one of them in the map, and the lines of the other ADRs are delimited by markers per ADR. A file that belongs to no ADR has all its lines of an ADR in blocks. Before it merges, the update removes the blocks of the ADRs that are left out from both versions of groundwork, so that these blocks, removed or not by the project, raise no conflict. The project deletes them from its files.
- **Later ADRs.** An ADR that groundwork adds after the choice is not adopted until the project lists it. An ADR that enters the choice, whether the project lists it or an ADR it keeps now needs it, is applied whole, from nothing. An ADR that leaves the choice is no longer updated, and its files are not deleted: the project deletes them.
- **The numbers.** The check of the ADRs accepts a missing number from `0001` to `0999` only when the choice of the project, with what it needs, leaves it out.
- **Groundwork's own decisions.** An ADR of groundwork numbered `1000` or more is never synchronised.
- **What a project can rely on.** When it keeps some of the ADRs: the `Decision` of the ADRs it keeps and the ones they need, the files that the map gives for them, `.groundwork-version`, and the name and the format of `.groundwork-adrs`. A project that chooses nothing relies on the same as before.

## Consequences

- A project adopts practices one at a time and leaves out the others, and the update raises no conflict for what it left out.
- The unit of the choice is the ADR with its files and its lines. A practice cannot be kept in part.
- Keeping one ADR can bring others. The update says which, and the project can drop the first one rather than keep what it did not want.
- The map and the markers must stay true: the check of the map verifies the files, the texts of the ADRs and, when the markers are checked, the shared lines.
- The shared files carry markers, which are comments, and which a project that chooses nothing can ignore.
- A project that lists ADRs does not receive the later ones by itself. It reads the release notes and adds what it wants.
- The ADRs of a community that builds its own base from groundwork have their own range, which this decision does not set.
- The choice is a file of the project, reviewed like any other change. What a project can rely on depends on it.

## Options considered

- **A list of ignored paths.** It is simple and needs no map. It does not see that an ADR needs another, it leaves the lines of the shared files that name what was left out, and each project has to find the paths.
- **A fork that deletes what it does not want.** It needs no tool, and every update that touches a deleted file is a conflict, which is the problem to solve.
