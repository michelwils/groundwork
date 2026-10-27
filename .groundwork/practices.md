# Practices of groundwork

This map tells what each ADR of groundwork is made of, so that a project can see what it takes when it keeps an ADR and what it leaves when it drops one. It is checked by [`check_practices.py`](scripts/check_practices.py) with the other checks.

For each ADR, an entry gives:

- **Needs**: the ADRs that it cannot be applied without. The text of an ADR names and links only these, so that the ADRs a project keeps, with the ADRs they need, hold together with no reference to an ADR the project does not have. The check reads the text of the ADRs to verify it.
- **Files**: the files that apply it. The file of the ADR itself is not listed. A file that several ADRs share belongs to one of them, which owns it and leaves with it, and only the lines of the other ADRs are in blocks.
- **Shared lines**: the files where the ADR has a block of lines, delimited by the markers `<!-- groundwork:NNNN -->` … `<!-- /groundwork -->` in Markdown and `# groundwork:NNNN` … `# /groundwork` in YAML. The check verifies that the list holds exactly the files that have a block of the ADR, and that a block names only its ADR and the ADRs it needs. In groundwork, the lines outside the blocks of a shared file name no ADR, and those of an owner name only it and the ADRs it needs. In a project, these lines are the project's own and may name any ADR.

The ADRs outside the ranges that groundwork reserves, which are its own decisions numbered from `1000`, are not practices and have no entry. A file belongs to one entry, or to the shared files, or to the files that are not part of a practice. In groundwork, the check fails for a file that is tracked by git and that the map does not name. In a project, which has a `.groundwork-version`, the check does not look for such files, since a project has files of its own. It reports a file of the map that the project lacks, other than `README.md` and `LICENSE`, which are the project's own.

## Practices

### 0001. [Record architecture decisions](../docs/adr/0001-record-architecture-decisions.md)

- Needs: none
- Files:
  - `docs/adr/template.md`
  - `.groundwork/scripts/check_adrs.py`
  - `.groundwork/scripts/test_check_adrs.py`
- Shared lines:
  - `CONTRIBUTING.md`
  - `AGENTS.md`
  - `.pre-commit-config.yaml`

### 0002. [Conventional Commits](../docs/adr/0002-conventional-commits.md)

- Needs: none
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`
  - `.pre-commit-config.yaml`

### 0003. [Change workflow](../docs/adr/0003-change-workflow.md)

- Needs: ADR 0002
- Files:
  - `.github/ISSUE_TEMPLATE/change.md`
  - `.groundwork/rulesets/main.json`
  - `.groundwork/scripts/apply_settings.py`
  - `.groundwork/scripts/check_pull_request.py`
  - `.groundwork/scripts/test_apply_settings.py`
  - `.groundwork/scripts/test_check_pull_request.py`
  - `.github/PULL_REQUEST_TEMPLATE.md`
- Shared lines:
  - `CONTRIBUTING.md`

### 0004. [Repository language is English](../docs/adr/0004-repository-language-english.md)

- Needs: none
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`

### 0005. [Semantic Versioning and releases](../docs/adr/0005-semantic-versioning-and-releases.md)

- Needs: ADR 0002
- Files:
  - `.github/workflows/release.yml`
  - `.groundwork/scripts/release.py`
  - `.groundwork/scripts/test_release.py`
- Shared lines:
  - `CONTRIBUTING.md`

### 0006. [Trunk-based development](../docs/adr/0006-trunk-based-development.md)

- Needs: ADR 0003, ADR 0005
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`
  - `.github/PULL_REQUEST_TEMPLATE.md`

### 0007. [AI-assisted changes](../docs/adr/0007-ai-assisted-changes.md)

- Needs: ADR 0002, ADR 0003
- Files:
  - `AGENTS.md`
- Shared lines:
  - `CONTRIBUTING.md`
  - `.github/PULL_REQUEST_TEMPLATE.md`
  - `.pre-commit-config.yaml`

### 0008. [Automated checks](../docs/adr/0008-automated-checks.md)

- Needs: none
- Files:
  - `.editorconfig`
  - `.github/dependabot.yml`
  - `.github/workflows/checks.yml`
  - `.github/workflows/project-checks.yml`
  - `.github/zizmor.yml`
  - `.markdownlint.yaml`
  - `.markdownlintignore`
  - `.groundwork/scripts/requirements.txt`
  - `.groundwork/scripts/check_links.py`
  - `.groundwork/scripts/check_practices.py`
  - `.groundwork/scripts/run_with_requirements.py`
  - `.groundwork/scripts/test_check_links.py`
  - `.groundwork/scripts/test_check_practices.py`
  - `.groundwork/scripts/test_run_with_requirements.py`
  - `.groundwork/scripts/test_checks_workflow.py`
  - `.groundwork/scripts/test_pre_commit_config.py`
  - `.groundwork/scripts/test_script_dependencies.py`
  - `.pre-commit-config.yaml`
  - `.groundwork/scripts/test_shared_files.py`
  - `.groundwork/scripts/test_apply_choice_on_the_real_files.py`
  - `.groundwork/scripts/test_filtered_trees.py`
- Shared lines:
  - `CONTRIBUTING.md`

### 0009. [Test-first development](../docs/adr/0009-test-first-development.md)

- Needs: none
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`
  - `AGENTS.md`

### 0010. [Security of the code of an application](../docs/adr/0010-security-of-the-code-of-an-application.md)

- Needs: none
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`
  - `AGENTS.md`

### 0011. [Protection of confidential and personal data](../docs/adr/0011-protection-of-confidential-and-personal-data.md)

- Needs: ADR 0010, ADR 0012
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`
  - `AGENTS.md`

### 0012. [Responding to an incident](../docs/adr/0012-responding-to-an-incident.md)

- Needs: none
- Files:
  - `SECURITY.md`
- Shared lines:
  - none

### 0013. [Licenses of the dependencies](../docs/adr/0013-licenses-of-the-dependencies.md)

- Needs: none
- Files:
  - none
- Shared lines:
  - `AGENTS.md`

### 0014. [Protecting the files of groundwork in a project](../docs/adr/0014-protecting-the-files-of-groundwork-in-a-project.md)

- Needs: ADR 0003, ADR 0007
- Files:
  - `.groundwork/CODEOWNERS.template`
  - `.groundwork/scripts/test_codeowners_template.py`
- Shared lines:
  - `AGENTS.md`

### 0015. [Logs and diagnostic of an application](../docs/adr/0015-logs-and-diagnostic-of-an-application.md)

- Needs: ADR 0010, ADR 0011, ADR 0012
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`
  - `AGENTS.md`

## Shared files

This file belongs to no ADR, and all its lines that belong to an ADR are in a block.

- `CONTRIBUTING.md`

## Not part of a practice

These files concern groundwork itself, or the repository as a whole, or are the tool that moves a project to a later version, which a project keeps whatever it leaves out.

- `.gitattributes`
- `.gitignore`
- `.groundwork/scripts/apply_choice.py`
- `.groundwork/scripts/choice.py`
- `.groundwork/scripts/coveragerc`
- `.groundwork/scripts/markers.py`
- `.groundwork/scripts/open_update_pull_request.py`
- `.groundwork/scripts/practices_map.py`
- `.groundwork/scripts/test_apply_choice.py`
- `.groundwork/scripts/test_choice.py`
- `.groundwork/scripts/test_markers.py`
- `.groundwork/scripts/test_open_update_pull_request.py`
- `.groundwork/scripts/test_practices_map.py`
- `.groundwork/scripts/test_update_groundwork.py`
- `.groundwork/scripts/test_update_workflow.py`
- `.groundwork/scripts/update_groundwork.py`
- `.github/workflows/update-groundwork.yml`
- `LICENSE`
- `README.md`
- `.groundwork/community-base.md`
- `.groundwork/practices.md`
