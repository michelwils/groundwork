# 0014. Protecting the files of groundwork in a project

**Status:** accepted

## Context

The update brings the reserved ADRs, `.groundwork/`, the workflows and `.pre-commit-config.yaml` into a project, with the configuration of the audit of its workflows and of the updates of its dependencies, and any pull request can change them afterwards, including one written by an agent. The ruleset of [ADR 0003](0003-change-workflow.md) requires the `checks` job but no approval, and that job runs the configuration of the branch of the pull request, so a change that weakens a hook passes its own check. [ADR 0007](0007-ai-assisted-changes.md) forbids an agent to bypass a check or to merge on its own, but it relies on the instructions given to the agent.

Some of these files are meant to be changed by the project: its lines outside the blocks of shared files, `CONTRIBUTING.md`, the Project section of `AGENTS.md`, its hooks and its jobs. A lock does not fit. The files that carry trust need a second reader.

The platform cannot tell a maintainer from an agent that holds the maintainer's credentials. A review protects only when the approval comes from another identity.

## Decision

We will let a project require the review of its code owners for the files of groundwork, with an option that is off by default.

- **Protected files.** "Protected" does not mean locked: when the project requires the review of its code owners, a change to one of these files needs the approval of an owner. The project makes its changes in its own pull requests.
  - The reserved ADRs and `docs/adr/template.md`.
  - `.groundwork/`.
  - `.groundwork-version`, `.groundwork-adrs`, `.groundwork-source` and `.groundwork-ranges`, the last of which decides where the next update comes from.
  - `.github/workflows/`.
  - `.github/zizmor.yml` and `.github/dependabot.yml`, which hold the rules of the audit of the workflows and of the updates of the dependencies.
  - `.pre-commit-config.yaml` and `.github/CODEOWNERS`.
  - Not protected: `CONTRIBUTING.md`, `AGENTS.md`, `README.md`, and the lines of the project in a shared file that is not in this list.
  - The platform matches whole files, so the lines of the project in a protected file, such as its hooks, its jobs and its Dependabot entries, which go where [ADR 0008](0008-automated-checks.md) says, are protected with it.
- **Owners.** groundwork provides `.groundwork/CODEOWNERS.template`. The project copies it to `.github/CODEOWNERS` and replaces `@OWNER` with its reviewers, who need write access. The copy is the project's own: the update does not touch it, and the project merges it into its default branch before it turns the requirement on. A community base that reserves numbers outside 0001-0999 adds its ranges.
- **Requirement.** `apply_settings.py --code-owner-review` sets in the ruleset at least one required approval, and more if the ruleset already requires more, the review of code owners (`require_code_owner_review`) and the dismissal of an approval when a commit is pushed after it, so that a push after the review needs a new one. A pull request that changes a file with a code owner then needs the approval of that owner. `--last-push-approval` goes with it and adds that the approval comes from someone other than the person who pushed last, for a project with several reviewers.
- **Update pull request.** It changes protected files, so the review of code owners applies to it, and it is meant to need the approval of an owner other than its author, which is the owner of the token that opens it.
- **Single maintainer.** A project with one maintainer does not turn the requirement on, since nobody else can approve, and the script refuses the option when the only code owner is the person who runs it. It relies on the rule that `AGENTS.md` gives to an agent, on the restrictions of its agent tool and on the approval of every merge ([ADR 0007](0007-ai-assisted-changes.md)). A project that wants the review adds a second account as owner.
- **Agent.** `AGENTS.md` tells an agent to change a file of groundwork only through the update, except the lines that belong to the project. A project may also restrict its agent tool. For Claude Code, a `permissions.deny` rule `Edit(path)` in the settings of the project stops its edit tools and the file commands it recognises, not a script that writes the file: the sandbox of the tool is the recourse. This is the project's choice, and groundwork configures no tool.

## Consequences

- A change to the files that carry trust is meant to have a second reader, who is not the check of the pull request, since that check runs the code of the branch.
- The review costs a second person. A project with one maintainer has no protection on the platform against an agent that uses the maintainer's credentials, only the restrictions of its tool and the maintainer's attention.
- The requirement is off by default, so that adopting groundwork breaks no project: if the requirement holds as meant, a project with one maintainer could not merge its update pull request. The default is not the safer one, and the README says how to turn the requirement on.
- The documentation that was read when this ADR was written says that a pull request which changes a file with a code owner must be approved by that owner. It does not say whether the author of a pull request can approve it, how that requirement behaves when the ruleset requires no other approval, nor, for each plan, whether a ruleset can require it.
- A test after the release of 0.7.0 gave this observation. On a private repository of a personal account, the ruleset had the parameters of `--code-owner-review` (`required_approving_review_count: 0`, which is the count of `.groundwork/rulesets/main.json` that the script keeps, `require_code_owner_review: true` and `dismiss_stale_reviews_on_push: true`). The file of code owners named the only user as the owner of `docs/adr/0*`, and a pull request from that user changed a file of that path. GitHub showed the pull request as mergeable with no review decision, and it was merged with no approval. A direct push to the branch was refused, so the ruleset was enforced.
- The test does not tell why: either the review of code owners is not required when the ruleset requires no approval, or it is required but not of an author who is the owner. No second account was available to separate the two. The case of a project with several reviewers, with an approval required, is not verified on a repository either.
- The documentation does not say that the review of code owners is required when the ruleset requires no approval, and the test merged a pull request in that case, so the option requires at least one approval, which rests on the number of approvals that the ruleset requires. That approval applies to every pull request of the project, not only to those that change a protected file, including the pull requests of Dependabot and of the update. A project with only one account would have nobody to approve them, and the script refuses the option for it.
- `apply_settings.py` stops with an error that names what the platform refused. It also refuses the option when the project has no file of code owners, or when that file names no owner, still names `@OWNER` or names only the person who runs the script.
- The options are not remembered. A project that runs `apply_settings.py` again, for example after it changed a setting of the repository, gives the same options, or the ruleset of the file replaces the one that has them. The script stops when a run would lower an approval setting that the ruleset has, such as the number of approvals or the resolution of threads, unless the project gives `--turn-off-reviews`.
- A rule that blocks the push of changes to given paths was rejected: it is meant for private or internal repositories and it blocks the push of the update branch too. A check that compares the files with the recorded version was rejected too: it runs the code of the branch, so the same pull request can weaken it.
- The copy of the template is the project's. A path that groundwork protects later reaches a project that copied the template only if the project adds the line.
- The line `/.github/workflows/` of the template also covers `.github/workflows/project-checks.yml`, where the project writes its own jobs. With the requirement on, a change to those jobs needs the approval of an owner, as a change to the jobs of groundwork does, since a job that is weakened passes its own check. A project that does not want that review edits its copy of the template.
