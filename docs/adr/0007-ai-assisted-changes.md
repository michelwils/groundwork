# 0007. AI-assisted changes

**Status:** accepted

## Context

Coding agents write code, documentation, commits and pull requests. A project that uses them needs to know which changes involved an agent, to keep a person responsible for what is merged, and to keep the history readable. Agents also tend to add references to the private session they run in, to describe at length that they followed the rules, and to be verbose, which adds noise to commits, issues and pull requests, and to the conversation with the maintainer. They may also present work that they have not checked, which turns the review by the maintainer into the first check.

## Decision

We will accept changes made with a coding agent, under the same rules as any other change ([ADR 0002](0002-conventional-commits.md), [ADR 0003](0003-change-workflow.md)), with the following additions.

- **Disclosure.** A commit made with an agent has a `Co-Authored-By` trailer naming the agent. An issue or a pull request written by an agent ends with a line stating that it was generated, with the name of the tool.
- **No private references.** A commit, an issue or a pull request never contains a link to, or an identifier of, a private agent session or conversation.
- **Approval.** A maintainer approves every merge of a change made with an agent. An agent never merges a pull request on its own initiative, and an approval applies to one pull request only.
- **Reporting.** An agent reports to the maintainer the errors it corrected and the deviations from a rule. It does not report that it followed the rules.
- **Self-review.** An agent checks its own work before presenting it, committing it or marking a pull request ready: it runs the commands that it documents, looks for rules that the change contradicts or repeats, and checks the acceptance criteria against the diff.
- **Checks.** An agent never bypasses a check: it does not skip hooks, disable a rule, or remove or weaken a test to make a check pass. When a check fails, it fixes the cause or reports it.
- **Autonomy.** An agent may commit, push its own branch, open a draft pull request, and update that pull request and its issue. It asks for explicit approval before any other action that is hard to reverse or reaches beyond them, such as changing repository settings or milestones, deleting a branch or rewriting history.
- **Sources.** Before stating a fact about an external tool or service, an agent checks its current documentation, or says that it did not.
- **Record.** A decision taken during the work is recorded where the work is tracked, not left in the conversation: a significant one as an ADR, any other in the issue or in the description of the pull request.
- **Concision.** An agent writes the shortest text that stays clear and precise, in its replies and in what it writes in commits, issues, pull requests and documentation. It does not repeat what was said, introduce what it is about to say or summarise what it just said.

## Consequences

- The history shows which changes involved an agent, and the platform keeps the co-author trailers when it squashes a pull request.
- A person remains accountable for every change, and merging stays a human decision, which makes each merge wait for a maintainer.
- The private conversation stays private, and the repository does not depend on access to it.
- A maintainer reads reports about what went wrong and not about what went right. A silent agent is not proof that a rule was followed: the history is.
- Concise texts are quicker to review, and the maintainer can ask the agent for more detail when needed. Clarity and precision take precedence over brevity: a text is not shortened at the cost of leaving out what a reader needs.
- The review by the maintainer is meant to be the last check. The self-review of the agent reduces the corrections it asks for without replacing it.
- A person or another agent can resume the work from the issue and the pull request, without the conversation that produced them.
- The rules rely on the instructions given to the agent. Only the absence of references to a session is checked automatically, as described in [ADR 0008](0008-automated-checks.md).
