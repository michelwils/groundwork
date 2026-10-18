# Practices of groundwork

This map tells what each ADR of groundwork is made of, so that a project can see what it takes when it keeps an ADR and what it leaves when it drops one. It is checked by [`check_practices.py`](../.github/scripts/check_practices.py) with the other checks.

For each ADR, an entry gives:

- **Needs**: the ADRs that it cannot be applied without. The text of an ADR names and links only these, so that the ADRs a project keeps, with the ADRs they need, hold together with no reference to an ADR the project does not have. The check reads the text of the ADRs to verify it.
- **Files**: the files that apply it. The file of the ADR itself is not listed. A file that several ADRs share belongs to one of them, which owns it and leaves with it, and only the lines of the other ADRs are in blocks.
- **Shared lines**: the files where the ADR has a block of lines, delimited by the markers `<!-- groundwork:NNNN -->` … `<!-- /groundwork -->` in Markdown and `# groundwork:NNNN` … `# /groundwork` in YAML. The check verifies that the list is the list of the files that have a block of the ADR, and that a block names only its ADR and the ADRs it needs.

The ADRs of groundwork numbered `1000` or more are its own decisions, not practices, and have no entry. A file belongs to one entry, or to the shared files, or to the files that are not part of a practice. In groundwork, the check fails for a file that is tracked by git and that the map does not name. In a project, which has a `.groundwork-version`, it does not look for such files, since a project has files of its own, and it reports a file of the map that the project lacks.

## Practices

### 0001. [Record architecture decisions](adr/0001-record-architecture-decisions.md)

- Needs: none
- Files:
  - `docs/adr/template.md`
  - `.github/scripts/check_adrs.py`
  - `.github/scripts/test_check_adrs.py`
- Shared lines:
  - `CONTRIBUTING.md`
  - `AGENTS.md`
  - `.pre-commit-config.yaml`

### 0002. [Conventional Commits](adr/0002-conventional-commits.md)

- Needs: none
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`
  - `.pre-commit-config.yaml`

### 0003. [Change workflow](adr/0003-change-workflow.md)

- Needs: ADR 0002
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
  - `.github/PULL_REQUEST_TEMPLATE.md`
- Shared lines:
  - `CONTRIBUTING.md`

### 0004. [Repository language is English](adr/0004-repository-language-english.md)

- Needs: none
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`

### 0005. [Semantic Versioning and releases](adr/0005-semantic-versioning-and-releases.md)

- Needs: ADR 0002
- Files:
  - `.github/workflows/release.yml`
  - `.github/scripts/release.py`
  - `.github/scripts/update_groundwork.py`
  - `.github/scripts/test_release.py`
  - `.github/scripts/test_update_groundwork.py`
- Shared lines:
  - `CONTRIBUTING.md`

### 0006. [Trunk-based development](adr/0006-trunk-based-development.md)

- Needs: ADR 0003, ADR 0005
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`
  - `.github/PULL_REQUEST_TEMPLATE.md`

### 0007. [AI-assisted changes](adr/0007-ai-assisted-changes.md)

- Needs: ADR 0002, ADR 0003
- Files:
  - `AGENTS.md`
- Shared lines:
  - `CONTRIBUTING.md`
  - `.github/PULL_REQUEST_TEMPLATE.md`
  - `.pre-commit-config.yaml`

### 0008. [Automated checks](adr/0008-automated-checks.md)

- Needs: none
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
  - `.pre-commit-config.yaml`
  - `.github/scripts/test_shared_files.py`
- Shared lines:
  - `CONTRIBUTING.md`

### 0009. [Test-first development](adr/0009-test-first-development.md)

- Needs: none
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`
  - `AGENTS.md`

### 0010. [Security of the code of an application](adr/0010-security-of-the-code-of-an-application.md)

- Needs: none
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`
  - `AGENTS.md`

### 0011. [Protection of confidential and personal data](adr/0011-protection-of-confidential-and-personal-data.md)

- Needs: ADR 0010, ADR 0012
- Files:
  - none
- Shared lines:
  - `CONTRIBUTING.md`
  - `AGENTS.md`

### 0012. [Responding to an incident](adr/0012-responding-to-an-incident.md)

- Needs: none
- Files:
  - `SECURITY.md`
- Shared lines:
  - none

### 0013. [Licenses of the dependencies](adr/0013-licenses-of-the-dependencies.md)

- Needs: none
- Files:
  - none
- Shared lines:
  - `AGENTS.md`

## Shared files

This file belongs to no ADR, and all its lines that belong to an ADR are in a block.

- `CONTRIBUTING.md`

## Not part of a practice

These files concern groundwork itself, or the repository as a whole.

- `.gitattributes`
- `.gitignore`
- `.github/scripts/markers.py`
- `.github/scripts/test_markers.py`
- `LICENSE`
- `README.md`
- `docs/practices.md`
