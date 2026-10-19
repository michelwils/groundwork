# 1001. Naming the files of groundwork

**Status:** accepted

## Context

A project that synchronises groundwork holds two projects in one: its own, and the part of groundwork it takes. The files of groundwork sit among its own, and only the map of the practices says which are which.

The map names 55 files besides the ADRs. 19 have a conventional name and a place that a platform, a tool or a convention fixes, such as `CONTRIBUTING.md`, `AGENTS.md`, `.editorconfig`, the workflows and the templates, so groundwork's version and the project's own are the same file by design. The other 36 have no such name or no such place: the scripts and their tests, which share `.github/scripts/` with whatever a project keeps there, the file of their dependencies, `requirements.txt`, the ruleset that the settings script applies, which GitHub does not read from the repository, the map `docs/practices.md` and the guide of the bases. Nothing in their name or place says that they are groundwork's, and a project may have a file of the same name. The update and the command that applies the choice report such a collision, as a conflict or a file kept, but they do not prevent it, and a reader of the tree cannot tell.

The mechanism files of a project, `.groundwork-version`, `.groundwork-adrs`, `.groundwork-source` and `.groundwork-ranges`, already carry the name of groundwork.

No project is based on groundwork yet, so a change of place costs nobody now. It would cost every project that has adopted groundwork later.

## Decision

We will keep every file of groundwork that has no conventional name in one directory, `.groundwork/`.

- **In it:** the scripts, their tests and `requirements.txt`, in `.groundwork/scripts/`, the ruleset, `.groundwork/rulesets/main.json`, the map of the practices, `.groundwork/practices.md`, and the guide of the bases, `.groundwork/community-base.md`.
- **Not in it:** a file whose name or place a platform, a tool or a convention fixes, such as the workflows, the templates, `dependabot.yml`, `.pre-commit-config.yaml` and `CONTRIBUTING.md`, and the ADRs with their template in `docs/adr/`.
- **At the root of the project:** the mechanism files `.groundwork-version`, `.groundwork-adrs`, `.groundwork-source` and `.groundwork-ranges`. The first three belong to the project, the last to a base.
- **A test** names the files that have a conventional name, and checks that every other file the map names is in `.groundwork/`, so that a new file is placed by a decision and not by habit.

## Consequences

- The directory tells whose a file is, and a file of groundwork cannot collide with a file of a project.
- The paths of 21 files that a published release holds change, and every reference to them: the hooks, the workflows, the configuration of Dependabot, the tests and the texts. The release notes say so. No project depends on them yet.
- The tools read the directory although its name starts with a dot: the hooks that check Markdown and editor settings take the names of the files that git tracks, and they flagged a mistake that was put there on purpose.
- Dependabot already updates a dot-prefixed directory, `/.github/scripts` (the pull request #57 did), and its documentation does not say that another one is refused; the first run after the move confirms it.
- The scripts keep importing each other from their own directory, and a project that adds scripts of its own keeps them in `.github/scripts/`.
- The list of the conventional names in the test is a judgement, and a new file has to be added to it or put in `.groundwork/`.
- A project root holds a directory `.groundwork/` and files `.groundwork-*`, which are the project's. The two names are close, and the first is the files of groundwork, the second the state of the project.

## Options considered

- **A prefix on the names**, `groundwork_check_adrs.py`. It changes 35 names, 21 of them published, and the prefix goes into every import since a Python module cannot have a hyphen. It makes the tree noisy and marks each file instead of saying once whose a directory is.
- **A prefix on the pages of `docs/` only.** One rename, but two rules, and the scripts stay mixed with the ones of the project.
- **Nothing, with the map as the only record.** It costs nothing and the collisions are reported, but the tree stays unreadable and the best moment to move the files passes with the first adoption.
