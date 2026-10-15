# 0007. AI-assisted changes

**Status:** accepted

## Context

Coding agents write code, documentation, commits and pull requests. A project that uses them needs to know which changes involved an agent, to keep a person responsible for what is merged, and to keep the history readable. Agents also tend to add references to the private session they run in, to describe at length that they followed the rules, and to be verbose, which adds noise to commits, issues and pull requests, and to the conversation with the maintainer.

## Decision

We will accept changes made with a coding agent, under the same rules as any other change ([ADR 0002](0002-conventional-commits.md), [ADR 0003](0003-change-workflow.md)), with the following additions.

- **Disclosure.** A commit made with an agent has a `Co-Authored-By` trailer naming the agent. An issue or a pull request written by an agent ends with a line stating that it was generated, with the name of the tool.
- **No private references.** A commit, an issue or a pull request never contains a link to, or an identifier of, a private agent session or conversation.
- **Approval.** A maintainer approves every merge of a change made with an agent. An agent never merges a pull request on its own initiative, and an approval applies to one pull request only.
- **Reporting.** An agent reports to the maintainer the errors it corrected and the deviations from a rule. It does not report that it followed the rules.
- **Concision.** An agent writes the shortest text that stays clear and precise, in its replies and in what it writes in commits, issues, pull requests and documentation. It does not repeat what was said, introduce what it is about to say or summarise what it just said.

## Consequences

- The history shows which changes involved an agent, and the platform keeps the co-author trailers when it squashes a pull request.
- A person remains accountable for every change, and merging stays a human decision, which makes each merge wait for a maintainer.
- The private conversation stays private, and the repository does not depend on access to it.
- A maintainer reads reports about what went wrong and not about what went right. A silent agent is not proof that a rule was followed: the history is.
- Concise texts are quicker to review, and the maintainer can ask the agent for more detail when needed. Clarity and precision take precedence over brevity: a text is not shortened at the cost of leaving out what a reader needs.
- The rules rely on the instructions given to the agent. Nothing checks them automatically yet, and doing so is left to later tooling.
