# 1003. Giving the result of the update to the pull request script

**Status:** accepted

## Context

`update_groundwork.py` prints a report for a person, and `open_update_pull_request.py` reads it back with patterns: the header at fixed positions, the line `added:` and the lines `- path`. Text from the source, the paths of its files, ends up in that report. A path with a line break added a line to it, which caused [GHSA-5x95-mpmv-37j6](https://github.com/michelwils/groundwork/security/advisories/GHSA-5x95-mpmv-37j6). Since 0.6.0 the header is read at fixed positions and a path with a control character or a line break is refused, and from 0.7.0 so is a path with a bidirectional control. Each new line of the report is a new place to protect by hand.

The two scripts live in the same directory and are released together, so their interface is internal. The report for a person is not the place for it.

## Decision

We will have `update_groundwork.py` write its result as one JSON object to a file that the caller names with `--result PATH`, and `open_update_pull_request.py` read only that file.

- **Fields.** `branch`, `from`, `to` and `source` are strings. `added` is a list of ADR numbers of four digits. `conflicts` is a list of paths. No other field is allowed.
- **When.** The file is written once a branch is prepared, with the status 0 or 3. When the project is up to date, or the script fails, it writes none. Without `--result` the script writes none. The script checks that it can write the file before it creates the branch, and stops with no branch when it cannot.
- **Reading.** `open_update_pull_request.py` refuses a file that is not valid JSON, that lacks a field or has an extra one, that has a value of the wrong type, a `to` that is not `X.Y.Z`, a `from` that is neither `X.Y.Z` nor `X.Y.Z+<commit>` ([ADR 1004](1004-moving-a-project-to-a-commit-of-its-source.md)), a branch that is not the one of the version, or a number of ADR that is not four digits.
- **Status.** The status of the update must agree with the result: 3 when files are in conflict, 0 when none is. `open_update_pull_request.py` refuses any other status, and a status other than 0 without a result.
- **Place.** The caller puts the file outside the working tree of the project, so that the commit of the update cannot hold it.
- **The text for a person** stays as it is. No script reads it, and it is not a format.

## Consequences

- A path of the source is a string of a list, encoded by the JSON library. It cannot add, replace or end a field.
- A field is added to the result with its check, not with a new pattern over text.
- The update gets an option, and the opener a temporary directory. Both belong to the public contract as the behaviour of files that groundwork provides.
- A caller that read the text of the update, other than a person, must read the file. No such caller is known in groundwork.
- A format with fields by position, such as a list separated by NUL, was rejected: adding a field would shift the others.
