# 0015. Logs and diagnostic of an application

**Status:** proposed

## Context

[ADR 0010](0010-security-of-the-code-of-an-application.md) says that the detail of an error goes to the logs and that no debugging feature is on in production by default, and with [ADR 0011](0011-protection-of-confidential-and-personal-data.md) it says what stays out of the logs. Nothing says what the logs hold, in which form, how a project turns diagnostic on, or who reads them. A team with legacy code and several applications gets logs that cannot be searched or compared, and a debugging switch that nobody decided. The libraries, the formats of a stack and the values depend on the project, and groundwork does not choose them.

## Decision

We will apply these principles to the logs and the diagnostic of an application. They name no library, no format of a stack, no retention period and no value, so that they hold for any project, which gives its own where it needs them.

- **Form.** One event per line, with stable fields that the applications of a project name alike: the time, the level, the event, the message and, when the event belongs to a request or a task, the correlation identifier. Each level has one meaning, which the project states: an `error` is a failure that calls for an action, a `warning` an anomaly that was handled, an `info` a notable event of the operation, a `debug` the detail of a diagnostic. A project that names its levels otherwise states their meaning.
- **Correlation.** A request or a task has one identifier, which is in each event it causes and which the application passes to the calls it makes outside.
- **What is recorded.** The security events: authentication, denied access and change of rights. The errors, with their context: the operation and the kind of input, not its value. The calls to what is outside the application: the target, without the secrets and the personal data that it may hold, the duration and the result.
- **What is never recorded.** What [ADR 0010](0010-security-of-the-code-of-an-application.md) and [ADR 0011](0011-protection-of-confidential-and-personal-data.md) keep out of the logs.
- **Diagnostic.** The level can be changed without a new deployment. Diagnostic is off by default in production. A change of level is recorded, with an identifier of who made it and not a name, and the level returns to its default when the need ends: the project says how.
- **Access.** The logs stay confidential data ([ADR 0011](0011-protection-of-confidential-and-personal-data.md)) even when they are cleaned. Only the people who need them read them.
- **Incident.** The logs serve the record and the review of an incident ([ADR 0012](0012-responding-to-an-incident.md)). What the project keeps of them, and for how long, is its own decision.

## Consequences

- A reviewer, and an agent that checks its own work, read a change that logs against a short list.
- The principles do not make logs useful or safe: a project that follows them can still log too little or too much. The fields, the levels and the values are the project's, and the principles are only as good as that statement.
- No tool checks these principles. Only the review applies them.
- The collection, the storage and the retention of the logs, the metrics and the tracing are decisions of the projects.
