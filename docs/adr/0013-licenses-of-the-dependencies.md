# 0013. Licenses of the dependencies

**Status:** accepted

## Context

The dependencies of a project come with licenses, which set what the project may do with them and what it owes. A dependency added without reading its license can force a project to relicense, to disclose code, or to give the dependency up later, at a cost. Which licenses a project can accept depends on its own license, on the sort of application it builds and on the rules of its organisation, which groundwork does not know. The dependency audit that a project runs looks for known vulnerabilities, not for licenses. groundwork gives no legal advice.

## Decision

We will ask each project to state which licenses it accepts in its dependencies, and to apply that statement. The list is the project's own: this ADR names no license, no tool and no law, and it decides none of them.

- **List.** The project writes, in its documentation, the licenses it accepts for its dependencies, or the rule by which it accepts them.
- **New dependency.** The license of a new dependency is named in the pull request that adds it, with the dependency itself, and is read against the list.
- **Outside the list.** A dependency whose license is not on the list, or that has none, is not added as it stands. The project extends its list, or records the exception and its reason in an ADR of its own. The decision is always the project's.
- **Tools.** A project whose stack has a tool that lists licenses may add a check for it to its check configuration. None is required.

## Consequences

- A project that follows this ADR can say, for each dependency, why its license was accepted, and a reviewer has a list to read each new dependency against.
- A license on the list does not make the project compliant. The compatibility between licenses, the duties of attribution, the patents and the law that applies are not settled by this ADR, which is not legal advice.
- Only the review applies it, unless the project adds a tool. A rule that is not read in a diff is not applied.
- It sees the dependencies that are added, not a license that changes in a later version of one already used. The project decides whether to read the license again when it updates a dependency.
- The dependencies of a dependency are covered too, but without a tool for the stack they are hard to see.
- Each new dependency costs a reading of its license, and the list costs one statement.
- A project that needs more, or something else, adds its own in an ADR.
