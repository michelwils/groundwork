# 0010. Security of the code of an application

**Status:** accepted

## Context

groundwork protects the repository of a project: [ADR 0008](0008-automated-checks.md) detects secrets, the workflows are audited, and a policy tells how to report a vulnerability. It says nothing about the security of the code of the application that the project builds. Yet the faults that let an application be taken over are few and well known: input that is trusted, a query built from a string, output that is not encoded, access that is not checked, a password kept in clear, a secret in the code, an error that tells too much, a default credential, a vulnerable dependency. Anyone who looks finds them in minutes. A person, and even more an agent that writes quickly without knowing the threats to the application, needs rules to read a change against.

## Decision

We will apply these rules to the code of an application, wherever the subject exists in it. A change that breaks one is corrected before it is merged. The rules are written to be checked against a diff, and they name no language, framework or tool, so that they hold for any project, which names its own where it needs them.

- **Input.** Data from outside the system is validated where it enters: its type, size, range and format.
- **Interpreters.** A query to a database, a command to a shell or an instruction to any other interpreter is parameterised, and never built by joining strings.
- **Output.** Data put in a page, a document or a message is encoded for the place where it lands.
- **Access.** Authentication and authorisation are checked on the server, for each request and for the resource it reaches, not only for the user. A check made by the client is not a security check.
- **Credentials.** A password is never stored or logged in clear: it is kept only as a hash made for the purpose.
- **Secrets.** A secret is in neither the code, the logs nor the messages of errors. It comes from outside the code, and it can be replaced.
- **Errors.** An error shown to a user does not tell the internals of the system, such as its paths, its queries or its stack. The detail goes to the logs.
- **Rights.** Each component, account and token has only the rights it needs.
- **Defaults.** A default is the safe choice: no default credential, and no debugging feature on in production.
- **Dependencies.** A dependency is chosen for what it does, kept at a pinned version, and updated when a vulnerability is known in it.

The rules are applied by the rules for agents ([ADR 0007](0007-ai-assisted-changes.md)), by the baseline checks ([ADR 0008](0008-automated-checks.md)), for the rules that a tool can check, and by the review. The cases that a hostile input would produce have their tests written first ([ADR 0009](0009-test-first-development.md)).

## Consequences

- A reviewer, and an agent that checks its own work, have a short list of rules to read each change against, wherever it touches a trust boundary.
- The rules remove the most common faults. They do not make an application secure: no rule and no tool proves it, and they replace neither the knowledge of a stack, nor a threat model, nor an audit. An application that follows them can still be taken over.
- Only the review applies the rules that no tool detects. A rule that is not read in a diff is not applied.
- A change that touches a trust boundary takes a reading more. That is the cost of the rules.
- The rules are general. A project that needs more, because of its sort of application or of the data it holds, adds its own in an ADR.
