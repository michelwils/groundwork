# Practices of groundwork

This map tells what each ADR of groundwork is made of, so that a project can see what it takes when it keeps an ADR and what it leaves when it drops one. It is checked by [`check_practices.py`](../.github/scripts/check_practices.py) with the other checks.

For each ADR, an entry gives:

- **Needs**: the ADRs that it cannot be applied without.
- **Mentions**: the ADRs that its text names and that it does not need to be applied. A project that leaves one out keeps a reference to an ADR it does not have.
- **Files**: the files that apply it. The file of the ADR itself is not listed.
- **Shared lines**: the files that carry lines of several ADRs, with the section or the bullet of the lines. A section or a bullet, not a line number, since a line moves. The check does not verify them.

A file belongs to one entry, or to the shared files, or to the files that are not part of a practice. In groundwork, the check fails for a file that is tracked by git and that the map does not name. In a project, which has a `.groundwork-version`, it does not look for such files, since a project has files of its own, and it reports a file of the map that the project lacks.

## Practices

### 0001. [Record architecture decisions](adr/0001-record-architecture-decisions.md)

- Needs: none
- Mentions: none
- Files:
  - `docs/adr/template.md`
  - `.github/scripts/check_adrs.py`
  - `.github/scripts/test_check_adrs.py`
- Shared lines:
  - `CONTRIBUTING.md`, section "Decisions"
  - `AGENTS.md`, section "Before a change", the bullet on a significant decision
  - `.pre-commit-config.yaml`, hook `adrs`

### 0002. [Conventional Commits](adr/0002-conventional-commits.md)

- Needs: none
- Mentions: ADR 0005, ADR 0008
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`, section "Commit messages"
  - `.pre-commit-config.yaml`, hook `commit-title`

### 0003. [Change workflow](adr/0003-change-workflow.md)

- Needs: ADR 0002
- Mentions: ADR 0006, ADR 0007
- Files:
  - `.github/ISSUE_TEMPLATE/change.md`
  - `.github/rulesets/main.json`
  - `.github/workflows/update-groundwork.yml`
  - `.github/scripts/apply_settings.py`
  - `.github/scripts/check_pull_request.py`
  - `.github/scripts/open_update_pull_request.py`
  - `.github/scripts/test_apply_settings.py`
  - `.github/scripts/test_check_pull_request.py`
  - `.github/scripts/test_open_update_pull_request.py`
- Shared lines:
  - `CONTRIBUTING.md`, section "Workflow"
  - `.github/PULL_REQUEST_TEMPLATE.md`, the line `Closes` and the sections "Plan" and "Acceptance criteria"

### 0004. [Repository language is English](adr/0004-repository-language-english.md)

- Needs: none
- Mentions: none
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`, section "Language"

### 0005. [Semantic Versioning and releases](adr/0005-semantic-versioning-and-releases.md)

- Needs: ADR 0002
- Mentions: ADR 0006
- Files:
  - `.github/workflows/release.yml`
  - `.github/scripts/release.py`
  - `.github/scripts/update_groundwork.py`
  - `.github/scripts/test_release.py`
  - `.github/scripts/test_update_groundwork.py`
- Shared lines:
  - `CONTRIBUTING.md`, section "Releases"

### 0006. [Trunk-based development](adr/0006-trunk-based-development.md)

- Needs: ADR 0005
- Mentions: ADR 0008
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`, section "Releases", the backport of a fix

### 0007. [AI-assisted changes](adr/0007-ai-assisted-changes.md)

- Needs: ADR 0002, ADR 0003
- Mentions: ADR 0006, ADR 0008, ADR 0010, ADR 0011, ADR 0013
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`, sections "Review checklist" and "AI-assisted changes"
  - `AGENTS.md`, section "Rules for agents", and the bullet on the plan in "Before a change"
  - `.github/PULL_REQUEST_TEMPLATE.md`, section "Plan"
  - `.pre-commit-config.yaml`, hook `no-agent-session`

### 0008. [Automated checks](adr/0008-automated-checks.md)

- Needs: none
- Mentions: ADR 0002, ADR 0003, ADR 0006, ADR 0007
- Files:
  - `.editorconfig`
  - `.github/dependabot.yml`
  - `.github/workflows/checks.yml`
  - `.github/zizmor.yml`
  - `.markdownlint.yaml`
  - `.markdownlintignore`
  - `.github/scripts/requirements.txt`
  - `.github/scripts/check_links.py`
  - `.github/scripts/check_practices.py`
  - `.github/scripts/run_with_requirements.py`
  - `.github/scripts/test_check_links.py`
  - `.github/scripts/test_check_practices.py`
  - `.github/scripts/test_run_with_requirements.py`
  - `.github/scripts/test_checks_workflow.py`
  - `.github/scripts/test_pre_commit_config.py`
  - `.github/scripts/test_script_dependencies.py`
- Shared lines:
  - `CONTRIBUTING.md`, section "Checks"
  - `AGENTS.md`, section "Project"
  - `.pre-commit-config.yaml`, the hooks `gitleaks`, `markdownlint`, `editorconfig-checker`, `zizmor`, `pip-audit`, `markdown-links` and the configuration at its top

### 0009. [Test-first development](adr/0009-test-first-development.md)

- Needs: none
- Mentions: ADR 0006, ADR 0007
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`, section "Tests"
  - `AGENTS.md`, section "Before a change", the bullet on the test written first

### 0010. [Security of the code of an application](adr/0010-security-of-the-code-of-an-application.md)

- Needs: none
- Mentions: ADR 0007, ADR 0008, ADR 0009
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`, section "Review checklist", the bullet on the trust boundaries
  - `AGENTS.md`, section "Rules for agents", the bullet on a trust boundary
  - `.github/PULL_REQUEST_TEMPLATE.md`, section "Security"

### 0011. [Protection of confidential and personal data](adr/0011-protection-of-confidential-and-personal-data.md)

- Needs: ADR 0010
- Mentions: ADR 0007, ADR 0012
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`, section "Review checklist", the bullet on the trust boundaries
  - `AGENTS.md`, section "Rules for agents", the bullet on a trust boundary
  - `.github/PULL_REQUEST_TEMPLATE.md`, section "Security"

### 0012. [Responding to an incident](adr/0012-responding-to-an-incident.md)

- Needs: none
- Mentions: ADR 0011
- Files:
  - `SECURITY.md`
- Shared lines:
  - none

### 0013. [Licenses of the dependencies](adr/0013-licenses-of-the-dependencies.md)

- Needs: none
- Mentions: ADR 0007, ADR 0008
- Files:
  - none
- Shared lines:
  - `AGENTS.md`, section "Rules for agents", the bullet on a trust boundary
  - `.github/PULL_REQUEST_TEMPLATE.md`, section "Security"

## Shared files

These files carry lines of several ADRs, and a project adjusts them to its own.

- `.github/PULL_REQUEST_TEMPLATE.md`
- `.pre-commit-config.yaml`
- `AGENTS.md`
- `CONTRIBUTING.md`

## Not part of a practice

These files concern groundwork itself, or the repository as a whole.

- `.gitattributes`
- `.gitignore`
- `LICENSE`
- `README.md`
- `docs/practices.md`
