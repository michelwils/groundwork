# 0011. Protection of confidential and personal data

**Status:** accepted

## Context

[ADR 0010](0010-security-of-the-code-of-an-application.md) gives the rules for the faults of the code of an application. It does not say how an application treats the data it holds: which data it collects, how long it keeps them, who reaches them, where they pass and to whom they go. Those are other decisions, which depend on the sort of data and, for personal data, on the law that applies to the project. groundwork gives no legal advice, but it can state principles and ask a project to name the rules that apply to it. The applications of the projects that adopt it may hold personal and financial data of their users.

## Decision

We will apply these principles to the data of an application. A change that breaks one is corrected before it is merged. These principles name no language, framework, tool, law or jurisdiction, so that they hold for any project, which names its own where it needs them. They are not legal advice.

- **Classification.** The project classifies the data of its application as public, internal, confidential or personal, and says so in its documentation.
- **Minimisation.** Only the data that are needed are collected, for a named purpose, and they are deleted when they are no longer needed.
- **Protection.** Data are protected in transit, always, and at rest when they are confidential or personal, backups included.
- **Leaks.** Personal data are kept out of the places that leak, such as the logs, the addresses, the messages of errors and the tools of measure. Secrets are already kept out of the logs and the messages of errors by [ADR 0010](0010-security-of-the-code-of-an-application.md).
- **Third parties.** The third parties that receive data are listed and reviewed.
- **Test data.** Test data are not production data.
- **Rights of users.** A user can get, and have deleted, the data that the application holds about them.
- **Leaks of data.** A leak of personal data is an incident, handled as [`SECURITY.md`](../../SECURITY.md) says. The project checks the legal duties of notification that apply to it, which this ADR does not state.

The principles are applied by the rules for agents ([ADR 0007](0007-ai-assisted-changes.md)) and by the review.

## Consequences

- A reviewer, and an agent that checks its own work, have a short list of principles to read each change against, wherever it touches data.
- The principles do not make an application lawful or its data safe. They are not legal advice, they do not replace the knowledge of the law that applies, and a project that follows them can still leak data or break the law.
- The classification, the purposes and the periods of retention depend on the application. Each project states them, and the principles are only as good as that statement.
- No tool detects most of these principles. Only the review applies them, and a principle that is not read in a diff is not applied.
- The principles are general. A project that needs more, because of the data it holds or the law that applies to it, adds its own in an ADR.
