# 0014. Protecting the files of groundwork in a project

**Status:** accepted

## Context

The update brings the reserved ADRs, `.groundwork/`, the workflows and `.pre-commit-config.yaml` into a project, and any pull request can change them afterwards, including one written by an agent. The ruleset of [ADR 0003](0003-change-workflow.md) requires the `checks` job but no approval, and that job runs the configuration of the branch of the pull request, so a change that weakens a hook passes its own check. [ADR 0007](0007-ai-assisted-changes.md) forbids an agent to bypass a check or to merge on its own, but it relies on the instructions given to the agent.

Some of these files are meant to be changed by the project: its lines outside the blocks of shared files, `CONTRIBUTING.md`, the Project section of `AGENTS.md`, its hooks and its jobs. A lock does not fit. The files that carry trust need a second reader.

The platform cannot tell a maintainer from an agent that holds the maintainer's credentials. A review protects only when the approval comes from another identity.

## Decision

We will let a project require the review of its code owners for the files of groundwork, with an option that is off by default.

- **Protected files.** The reserved ADRs and `docs/adr/template.md`, `.groundwork/`, the files `.groundwork-version`, `.groundwork-adrs`, `.groundwork-source` and `.groundwork-ranges` (the last decides where the next update comes from), `.github/workflows/`, `.pre-commit-config.yaml` and `.github/CODEOWNERS`. `CONTRIBUTING.md`, `AGENTS.md`, the README and the lines of the project in shared files are not.
- **Owners.** groundwork provides `.groundwork/CODEOWNERS.template`. The project copies it to `.github/CODEOWNERS` and replaces `@OWNER` with its reviewers, who need write access. The copy is the project's own: the update does not touch it, and the project merges it into its default branch before it turns the requirement on. A community base that reserves numbers outside 0001-0999 adds its ranges.
- **Requirement.** `apply_settings.py --code-owner-review` makes the ruleset require the approval of a code owner and dismiss an approval when a commit is pushed after it, so that a push after the review needs a new one. `--last-push-approval` goes with it and adds that the approval comes from someone other than the person who pushed last, for a project with several reviewers.
- **Update pull request.** It changes protected files, so it needs the approval of an owner other than its author, which is the owner of the token that opens it.
- **Single maintainer.** A project with one maintainer does not turn the requirement on, since nobody else can approve. It relies on the rule that `AGENTS.md` gives to an agent, on the restrictions of its agent tool and on the approval of every merge ([ADR 0007](0007-ai-assisted-changes.md)). A project that wants the review adds a second account as owner.
- **Agent.** `AGENTS.md` tells an agent to change a file of groundwork only through the update. A project may also restrict its agent tool. For Claude Code, a `permissions.deny` rule `Edit(path)` in the settings of the project stops its edit tools and the file commands it recognises, not a script that writes the file: the sandbox of the tool is the recourse. This is the project's choice, and groundwork configures no tool.

## Consequences

- A change to the files that carry trust has a second reader, who is not the check of the pull request, since that check runs the code of the branch.
- The review costs a second person. A project with one maintainer has no protection on the platform against an agent that uses the maintainer's credentials, only the restrictions of its tool and the maintainer's attention.
- The requirement is off by default, so that adopting groundwork breaks no project: a project with one maintainer could not merge its update pull request. The default is not the safer one, and the README says how to turn the requirement on.
- The documentation that was read when this ADR was written says that a pull request which changes a file with a code owner must be approved by that owner. It does not say whether the author of a pull request can approve it, how that requirement behaves when the ruleset requires no other approval, nor, for each plan, whether a ruleset can require it. `apply_settings.py` stops with an error that names what the platform refused. It also refuses the option when the project has no file of code owners or still names `@OWNER`.
- The options are not remembered. A project that runs `apply_settings.py` again, for example to name a new job of its CI in the ruleset, gives the same options, or the ruleset of the file replaces the one that has them. The script stops when a run would lower an approval setting that the ruleset has, such as the number of approvals or the resolution of threads, unless the project gives `--turn-off-reviews`.
- A rule that blocks the push of changes to given paths was rejected: it is meant for private or internal repositories and it blocks the push of the update branch too. A check that compares the files with the recorded version was rejected too: it runs the code of the branch, so the same pull request can weaken it.
- The copy of the template is the project's. A path that groundwork protects later reaches a project that copied the template only if the project adds the line.
