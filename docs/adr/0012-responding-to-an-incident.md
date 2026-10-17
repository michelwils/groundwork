# 0012. Responding to an incident

**Status:** accepted

## Context

A deployed project can face an incident that is not a vulnerability reported to it: a leak of data, an outage, a compromised account. [`SECURITY.md`](../../SECURITY.md) tells the maintainer what to do from the report of a vulnerability to its disclosure, and [ADR 0011](0011-protection-of-confidential-and-personal-data.md) makes a leak of personal data an incident. Nothing says who acts, how the people affected are told, and what is learned afterwards. Under pressure, those questions are answered in a hurry, and often by nobody. The tools, the channels and the contacts depend on the project, and groundwork does not choose them.

## Decision

We will respond to an incident by these principles. They apply to a project of any size, including one with a single maintainer, and they name no tool and no channel.

- **Who decides.** One person leads the response and decides, and it is the maintainer when there is only one. The project says who it is before an incident, not during it.
- **Contain first.** The harm is stopped before its cause is sought: a credential is revoked, a system is isolated or switched off.
- **Inform.** The people affected are told what happened, what is concerned and what they should do, as soon as it is known.
- **Record.** The facts and the decisions are written where the work is tracked, such as the report or an issue, as they happen.
- **Review.** After the incident, a review that blames no one records what happened and what was missing, and opens an issue for the check or the rule that was missing, if there was one.

A vulnerability that is reported to the project is handled as `SECURITY.md` says, which these principles do not repeat. They apply to every other incident, and to a leak of personal data ([ADR 0011](0011-protection-of-confidential-and-personal-data.md)).

## Consequences

- A project that follows them has answered, before an incident, who decides and what is done first, and it has a record to learn from after.
- The principles do not prevent an incident or limit its damage by themselves. They replace neither monitoring, nor a roster, nor a deadline, nor the exercise of a response, which depend on the project and are not stated here.
- The review is only worth what the project does with its findings. A review whose issues are never handled changes nothing.
- A project with a single maintainer decides, informs and reviews alone. The principles give it a list to follow, not a second person.
