# How the scripts of groundwork work

The scripts in this folder prepare the update of a project, apply its choice of ADRs, check its files and release it. This page tells how they fit together, where to change each step of an update, and what the words of the code mean. It does not repeat the ADRs: it names them, and the ADR holds the rule.

The page is copied into every project with the scripts, and a project does not have all the files and ADRs of groundwork, so it holds no link. The commands run from the root of the repository.

## What the folder holds

- One script per job, and `test_<script>.py` for its tests. The tests that read the files of the repository, such as `test_checks_workflow.py`, check the configuration of groundwork and of a project.
- `requirements.txt` pins the dependencies of the scripts, and Dependabot updates it. `coveragerc` sets the coverage that the tests must reach (ADR 1002), and `ruff.toml` the lint and the format of the Python (ADR 1005).
- The commands that run the checks, the tests and the coverage are those of the steps of the workflow `checks.yml`. The README of groundwork gives them too, in its section Working on groundwork.

## Who runs what

| Script | What it does | Run by |
| --- | --- | --- |
| `update_groundwork.py` | Prepares on a branch the update of a project to a later version of groundwork, and keeps the changes of the project | A person, or `open_update_pull_request.py` |
| `open_update_pull_request.py` | Runs the update with no issue, commits it, pushes it and opens its pull request (ADR 1003) | The workflow `update-groundwork.yml` |
| `apply_choice.py` | Makes the files of a project agree with the ADRs that it keeps (ADR 1000) | A person |
| `apply_settings.py` | Applies the settings of the repository on GitHub: merge method, private vulnerability reporting and the ruleset (ADR 0003) | A person |
| `check_adrs.py` | Checks the ADRs against their template and their numbering (ADR 0001) | The hook `adrs` and the CI |
| `check_practices.py` | Checks the map of the practices, and that the texts name only the ADRs that they need (ADR 0008) | The hook `practices` and the CI |
| `check_links.py` | Checks the relative links and the anchors of the Markdown files (ADR 0008) | The hook `markdown-links`, through `run_with_requirements.py` |
| `check_pull_request.py` | Checks the branch name, the closing line and the breaking change of a pull request (ADR 0003, ADR 0006) | The workflow `checks.yml` |
| `release.py` | Computes the next version and the release notes (ADR 0005, ADR 0006) | The workflow `release.yml`, or a person to see the next version |
| `run_with_requirements.py` | Runs a script in an environment made from `requirements.txt` | The hook `markdown-links` |
| `choice.py`, `markers.py`, `practices_map.py` | Hold what several scripts share: the choice, the blocks of lines and the map | They are imported, not run |

## How the modules fit together

Each script finds the others in its own folder. The second column is what it imports, and a test compares it with the real imports.

| Module | Imports | Note |
| --- | --- | --- |
| `markers.py` | none | |
| `practices_map.py` | none | |
| `choice.py` | `markers`, `practices_map` | |
| `update_groundwork.py` | `choice`, `markers`, `practices_map` | |
| `apply_choice.py` | `update_groundwork`, `choice`, `markers`, `practices_map` | It imports `update_groundwork` as `update` |
| `check_adrs.py` | `choice`, `practices_map` | |
| `check_links.py` | `choice`, `practices_map` | |
| `check_practices.py` | `choice`, `markers`, `practices_map` | |
| `open_update_pull_request.py` | none | It runs `update_groundwork.py` as a process, and reads the JSON file that it writes |
| `run_with_requirements.py` | none | It runs another script as a process |
| `apply_settings.py` | none | |
| `release.py` | none | |
| `check_pull_request.py` | none | |

- `markers.py` reads the blocks of lines that an ADR owns in a file that several ADRs share (`parse`), and takes out the blocks of the ADRs that a project did not keep (`remove`).
- `practices_map.py` reads the map `.groundwork/practices.md` (`parse`) and the ranges of numbers that a source reserves (`read_ranges`).
- `choice.py` reads `.groundwork-adrs` (`read`) and says which ADRs a project keeps (`Kept`) and which files that takes (`included`, `content`).

## How an update runs

Each row is one step of `run` in `update_groundwork.py`, in order, then the steps that `open_update_pull_request.py` adds. The last column is the script that defines the function.

| What happens | Functions | Script |
| --- | --- | --- |
| The arguments are checked | `check_arguments` | `update_groundwork.py` |
| The version that the project records is read, with the commit if it names one | `recorded_version`, `commit_of` | `update_groundwork.py` |
| The source is chosen: `--source`, else the file of the project, else groundwork | `source_of`, `recorded_source` | `update_groundwork.py` |
| The tags, and the head when asked, are fetched, and the source must know the recorded version | `fetch_base`, `fetch_releases`, `fetch_head`, `unknown_message` | `update_groundwork.py` |
| The version to move to is chosen, or the update stops because the project is up to date | `target`, `target_head`, `target_release`, `target_latest`, `up_to_date` | `update_groundwork.py` |
| The working tree must be clean, and the branch is named and must not exist yet: checks made in `run` itself | `run`, `branch_name` | `update_groundwork.py` |
| What the choice of the project asks for between the two versions is read, and nothing is written | `plan`, `Side`, `adrs_entering`, `paths_with_a_block_of`, `text_of`, `Without` | `update_groundwork.py` |
| A path that leaves the repository or lands in a directory .git is refused, and so is a result file that cannot be written | `refuse_steps_outside`, `paths_of`, `inside`, `in_git_directory`, `check_result_path` | `update_groundwork.py` |
| The branch is created and each step is applied with a three-way merge | `apply_path`, `decide`, `merge`, `read`, `write`, `remove` | `update_groundwork.py` |
| The report is printed and the JSON result is written | `report`, `write_result` | `update_groundwork.py` |
| The update runs as a process, and its status must agree with its result | `run_the_update`, `result`, `agree` | `open_update_pull_request.py` |
| A version whose pull request was closed without a merge is not proposed again | `rejected`, `undo` | `open_update_pull_request.py` |
| The update is committed, pushed and opened as a pull request, a draft when files are in conflict | `open_the_pull_request`, `body`, `propose` | `open_update_pull_request.py` |

## How a choice is applied

`apply_choice.py` makes the files agree with the ADRs that a project keeps. It takes the project for a new one when it has no `.groundwork-version`.

| What happens | Functions | Script |
| --- | --- | --- |
| A new project is told from an existing one | `run`, `new_project`, `existing_project` | `apply_choice.py` |
| The choice comes from the ADRs named on the command, or from the file of the project | `choice_of_the_command`, `release_to_record` | `apply_choice.py` |
| A new project loses the files and the blocks of the ADRs that it leaves out | `leave_out_of_a_new_project`, `removable_blocks`, `blocks_of` | `apply_choice.py` |
| An existing project reads the same plan as an update, from its recorded version to itself | `plan` | `update_groundwork.py` |
| An existing project loses what it left out, gets what entered and keeps what it changed | `files_left_out`, `bring_into_line`, `add_the_files_of_no_practice` | `apply_choice.py` |
| The paths are checked and the writes are made | `refuse_paths_outside`, `apply`, `Changes` | `apply_choice.py` |

## The data

The values that pass from one function to another have a name.

| What it holds | Type | Script |
| --- | --- | --- |
| A block of lines of an ADR in a shared file: the ADR and its first and last lines | `Block` | `markers.py` |
| An entry of the map: the ADR, its line Needs, its files and its shared lines, with `Needs` and `Listed` for a line and a path | `Entry`, `Needs`, `Listed` | `practices_map.py` |
| The ADRs that a project keeps | `Kept` | `choice.py` |
| What a version of groundwork says about the ADRs | `Side` | `update_groundwork.py` |
| What to do to one path: its base and its new content | `Step` | `update_groundwork.py` |
| What the choice asks for at a version | `Plan` | `update_groundwork.py` |
| A write of the choice: a path, its content or its deletion, and its mode | `Write` | `apply_choice.py` |
| A commit of the range of a release | `Commit` | `release.py` |

## Glossary

The words of the code, with the ADR that defines what they stand for.

| Word | Meaning | ADR |
| --- | --- | --- |
| `adopted` | The ranges of numbers that the file `.groundwork-adrs` lists, or no value when the project has no file, in which case it keeps everything that the source reserves | ADR 1000 |
| `kept` | The ADRs that the project keeps: the adopted ones, those that they need, and ADR 0001, or every ADR that the source reserves when the project has no file | ADR 1000 |
| `listed` | An ADR that a range of the file holds, as opposed to one that is kept because another needs it | ADR 1000 |
| `needs` | For each ADR, the numbers of the ADRs that it cannot be applied without, from the map | ADR 1000, ADR 0008 |
| `needed` | The listed ADRs and ADR 0001, with the ADRs that they need, and those in turn | ADR 1000 |
| `reserved` | The ranges of numbers that the source reserves: 0001 to 0999 for groundwork, and those of `.groundwork-ranges` for a base | ADR 1000, ADR 0001 |
| `owners` | For each file of the map, the number of the ADR whose entry lists it | ADR 1000, ADR 0008 |
| `shared` | A file that carries lines of several ADRs, in blocks | ADR 1000 |
| `apart` | A file that belongs to no practice: the update brings it whatever the choice, except the README and the license, which are the project's own | ADR 1000 |
| `block` | The lines of one ADR in a shared file, between two markers | ADR 1000 |
| `side` | What a version of groundwork says about the ADRs: its reserved ranges and its map | ADR 1000 |
| `entering` | The ADRs that enter the choice at a version: kept now and not before, or kept by a choice that has no file for them | ADR 1000 |
| `candidates` | The paths that an update considers: those that changed, those that start from nothing, and those with a block of an ADR that enters | ADR 1000 |
| `from_nothing` | A path whose base is empty, because its ADR enters the choice or was left out before, so that its file is not taken for a deletion | ADR 1000 |
| `said` | The ADRs that enter the choice and that the project does not list, which the update names in its line added. A project with no file has none | ADR 1000 |
| `base`, `theirs`, `ours` | The three versions of a file in a merge: the version that the project is based on, the new version of groundwork, and the file of the project | ADR 1000 |
| `source` | The repository of groundwork that an update reads: `--source`, else `.groundwork-source`, else groundwork | ADR 1000, ADR 1004 |
| `head` | The default branch of the source, to which `--to head` moves a project to try a change before its release | ADR 1004 |

## Tests

Each script has its test module. The tests run a script as a process when they check what it prints and its exit status, and the coverage counts that code (ADR 1002). The modules that read the files of the repository run in a project at each pull request, whatever changed, because the project edits what they read; the step Test the configuration of the project of the workflow `checks.yml` lists them, and a test checks the list.
