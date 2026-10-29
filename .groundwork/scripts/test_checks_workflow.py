import configparser
import os
import re
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
from test_filtered_trees import is_source  # noqa: E402

WORKFLOW = os.path.join(HERE, "..", "..", ".github", "workflows", "checks.yml")
PROJECT_WORKFLOW = os.path.join(HERE, "..", "..", ".github", "workflows", "project-checks.yml")
BOT_PULL_REQUEST = (
    "!(startsWith(github.head_ref, 'dependabot/') && github.event.pull_request.user.login == 'dependabot[bot]')"
)


def without_comments(path):
    with open(path) as handle:
        return re.sub(r"^\s*#.*\n", "", handle.read(), flags=re.MULTILINE)


def job(name):
    """Return the text of a job of the workflow, without its comments, or an empty text if it has none."""
    found = re.search(rf"^  {name}:\n((?:(?:    .*)?\n?)+)", without_comments(WORKFLOW), flags=re.MULTILINE)
    return found.group(1) if found else ""


def steps():
    """Return the text of each step of the job of groundwork, by name, without its comments."""
    text = job("groundwork")
    parts = re.split(r"^      - (?=name:|uses:)", text, flags=re.MULTILINE)[1:]
    found = {}
    for part in parts:
        match = re.match(r"name: (.+)", part)
        found[match.group(1).strip() if match else part.splitlines()[0]] = part
    return found


class JobsOfTheProject(unittest.TestCase):
    """The job that the ruleset requires, `checks`, waits for the checks of groundwork and for those of the project."""

    def test_the_job_of_the_project_calls_the_workflow_that_the_project_owns(self):
        self.assertRegex(
            job("project"), re.compile(r"^    uses: \$/\.github/workflows/project-checks\.yml$", flags=re.MULTILINE)
        )

    def test_the_required_job_waits_for_the_checks_of_groundwork_and_of_the_project(self):
        self.assertRegex(job("checks"), re.compile(r"^    needs: \[groundwork, project\]$", flags=re.MULTILINE))

    def test_the_required_job_runs_when_a_job_it_waits_for_failed_or_was_skipped_but_not_when_cancelled(self):
        self.assertRegex(job("checks"), re.compile(r"^    if: \$\{\{ !cancelled\(\) \}\}$", flags=re.MULTILINE))

    def test_the_required_job_fails_unless_both_jobs_succeeded(self):
        text = job("checks")
        self.assertIn("GROUNDWORK: ${{ needs.groundwork.result }}", text)
        self.assertIn("PROJECT: ${{ needs.project.result }}", text)
        self.assertIn('[ "$GROUNDWORK" = success ] && [ "$PROJECT" = success ]', text)

    def test_the_required_job_does_not_run_the_checks_itself(self):
        self.assertNotIn("pre-commit", job("checks"))
        self.assertNotIn("actions/checkout", job("checks"))

    def test_the_workflow_of_the_project_is_called_by_the_workflow_and_nothing_else(self):
        text = without_comments(PROJECT_WORKFLOW)
        self.assertRegex(text, re.compile(r"^on:\n  workflow_call:\n(?!  )", flags=re.MULTILINE))

    def test_the_workflow_of_the_project_reads_the_contents_and_nothing_more(self):
        text = without_comments(PROJECT_WORKFLOW)
        self.assertRegex(text, re.compile(r"^permissions:\n  contents: read\n(?!  )", flags=re.MULTILINE))


class Concurrency(unittest.TestCase):
    """An edit of the title or of the description of a pull request has a concurrency group of its own, so that it does not
    cancel the run of a push, which would leave a cancelled run as the last one created, and is not cancelled by it."""

    def workflow(self):
        return without_comments(WORKFLOW)

    def test_an_edit_has_a_group_of_its_own_that_a_push_does_not_share(self):
        group = re.search(r"^  group: (.+)$", self.workflow(), flags=re.MULTILINE).group(1)
        self.assertIn("${{ github.ref }}", group)
        self.assertRegex(group, r"github\.event\.action == 'edited' && '([a-z]+)' \|\| '([a-z]+)'")
        edit, other = re.search(r"github\.event\.action == 'edited' && '([a-z]+)' \|\| '([a-z]+)'", group).groups()
        self.assertNotEqual(edit, other)

    def test_the_group_that_each_event_gets_is_the_one_that_the_expression_gives(self):
        """Follow the expression `condition && edit || other` as the platform does: a text that is empty makes `&&` give
        the other branch, and `github.event.action` has no value on a push."""
        group = re.search(r"^  group: (.+)$", self.workflow(), flags=re.MULTILINE).group(1)
        edit, other = re.search(r"github\.event\.action == 'edited' && '([a-z]+)' \|\| '([a-z]+)'", group).groups()

        def given(action):
            return edit if action == "edited" and edit else other

        self.assertEqual(given("edited"), edit)
        for action in (None, "", "opened", "synchronize", "reopened"):  # None: a push to the main branch
            with self.subTest(action=action):
                self.assertEqual(given(action), other)
        self.assertTrue(edit and other and edit != other)

    def test_the_group_of_the_pull_request_checks_does_not_depend_on_the_commit(self):
        group = re.search(r"^  group: (.+)$", self.workflow(), flags=re.MULTILINE).group(1)
        self.assertNotIn("github.sha", group)
        self.assertNotIn("run_id", group)

    def test_a_run_cancels_the_run_in_progress_of_its_group_for_a_pull_request_only(self):
        self.assertRegex(
            self.workflow(),
            re.compile(r"^  cancel-in-progress: \$\{\{ github\.event_name == 'pull_request' \}\}$", flags=re.MULTILINE),
        )

    def test_an_edit_still_starts_a_run_to_check_the_title_and_the_description_again(self):
        self.assertRegex(
            self.workflow(), re.compile(r"^    types: \[opened, edited, synchronize, reopened\]$", flags=re.MULTILINE)
        )


class ChecksWorkflow(unittest.TestCase):
    def test_the_title_of_a_pull_request_of_dependabot_is_not_checked(self):
        step = steps()["Check the pull request title"]
        condition = re.search(r"^        if: (.+)$", step, flags=re.MULTILINE)
        self.assertIsNotNone(condition)
        self.assertIn(BOT_PULL_REQUEST, condition.group(1))
        self.assertIn("github.event_name == 'pull_request'", condition.group(1))

    def test_a_branch_named_like_those_of_dependabot_is_not_enough_to_skip_the_check(self):
        condition = re.search(r"^        if: (.+)$", steps()["Check the pull request title"], flags=re.MULTILINE).group(
            1
        )
        self.assertNotIn("!startsWith(github.head_ref, 'dependabot/') }}", condition)
        self.assertIn("github.event.pull_request.user.login", condition)

    def test_no_other_step_skips_the_pull_requests_of_dependabot(self):
        for name, step in steps().items():
            if name != "Check the pull request title":
                with self.subTest(step=name):
                    self.assertNotIn("dependabot", step)

    def test_the_branch_name_is_still_given_to_the_check_of_the_branch(self):
        step = steps()["Check the branch name and the closing line of the pull request"]
        self.assertIn("check_pull_request.py", step)
        self.assertNotIn("startsWith", step)

    def test_the_title_is_given_to_the_check_of_the_closing_line_through_the_environment(self):
        step = steps()["Check the branch name and the closing line of the pull request"]
        self.assertIn("PR_TITLE: ${{ github.event.pull_request.title }}", step)
        self.assertIn('"$BRANCH" "$BASE" "$BODY" "$PR_TITLE"', step)

    def test_the_tests_of_the_scripts_receive_the_variable_of_a_source_of_adrs(self):
        step = steps()["Test the scripts"]
        self.assertRegex(
            step,
            re.compile(
                r"^        env:\n          GROUNDWORK_SOURCE: \$\{\{ vars\.GROUNDWORK_SOURCE \}\}$", flags=re.MULTILINE
            ),
        )


RESTORE_STEP = "Restore the environments of pre-commit"
SAVE_STEP = "Save the environments of pre-commit"
KEY_STEP = "Find the key of the cache of pre-commit"


class CacheOfTheHooks(unittest.TestCase):
    """The environments of the hooks depend only on the configuration and on pre-commit, so the CI keeps them."""

    def test_the_cache_is_restored_before_the_checks_and_saved_after_them(self):
        names = list(steps())
        self.assertLess(names.index("Install pre-commit"), names.index(KEY_STEP))
        self.assertEqual(names.index(KEY_STEP) + 1, names.index(RESTORE_STEP))
        self.assertEqual(names.index(RESTORE_STEP) + 1, names.index("Run every check"))
        self.assertEqual(names.index("Run every check") + 1, names.index(SAVE_STEP))

    def test_the_two_steps_use_the_same_pinned_commit_with_its_version_in_a_comment(self):
        commits = set()
        for name, action in ((RESTORE_STEP, "restore"), (SAVE_STEP, "save")):
            with self.subTest(step=name):
                match = re.search(
                    rf"^        uses: actions/cache/{action}@([0-9a-f]{{40}}) # v[0-9]+\.[0-9]+\.[0-9]+$",
                    steps()[name],
                    flags=re.MULTILINE,
                )
                self.assertIsNotNone(match)
                commits.add(match.group(1))
        self.assertEqual(len(commits), 1)

    def test_the_cache_holds_the_folder_that_pre_commit_is_told_to_use(self):
        """Pre-commit reads PRE_COMMIT_HOME before its default, so the folder is not a guess."""
        self.assertIn('echo "PRE_COMMIT_HOME=$RUNNER_TEMP/pre-commit" >> "$GITHUB_ENV"', command(KEY_STEP))
        for name in (RESTORE_STEP, SAVE_STEP):
            with self.subTest(step=name):
                self.assertRegex(
                    steps()[name], re.compile(r"^          path: \$\{\{ env\.PRE_COMMIT_HOME \}\}$", flags=re.MULTILINE)
                )

    def test_the_two_steps_use_the_one_key_that_the_step_before_computes(self):
        self.assertIn("id: key", steps()[KEY_STEP])
        for name in (RESTORE_STEP, SAVE_STEP):
            with self.subTest(step=name):
                self.assertRegex(
                    steps()[name],
                    re.compile(r"^          key: \$\{\{ steps\.key\.outputs\.key \}\}$", flags=re.MULTILINE),
                )

    def test_no_cache_of_another_configuration_is_restored(self):
        for name in (RESTORE_STEP, SAVE_STEP):
            with self.subTest(step=name):
                self.assertNotIn("restore-keys", steps()[name])

    def test_the_environments_are_saved_after_a_failed_check_but_not_after_a_hit(self):
        """A push to the main branch whose check fails still saves what it installed."""
        self.assertIn("id: cache", steps()[RESTORE_STEP])
        self.assertRegex(
            steps()[SAVE_STEP],
            re.compile(
                r"^        if: \$\{\{ !cancelled\(\) && steps\.cache\.outputs\.cache-hit != 'true' \}\}$",
                flags=re.MULTILINE,
            ),
        )

    def test_no_other_step_uses_a_cache(self):
        for name, step in steps().items():
            if name not in (RESTORE_STEP, SAVE_STEP):
                with self.subTest(step=name):
                    self.assertNotIn("actions/cache", step)


class KeyOfTheCache(unittest.TestCase):
    """The step that computes the key, with the interpreter that pre-commit runs with and not the one of the PATH."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = self.directory.name
        os.makedirs(os.path.join(self.root, "bin"))
        os.makedirs(os.path.join(self.root, "venv", "bin"))
        self.executable("bin/python3", "#!/bin/sh\necho 'Python of the PATH'\n")

    def tearDown(self):
        self.directory.cleanup()

    def executable(self, name, text):
        path = os.path.join(self.root, name)
        with open(path, "w") as handle:
            handle.write(text)
        os.chmod(path, 0o755)

    def run_step(self, version="Python 3.12.3", config="c0ffee", temp="/tmp/runner"):
        """Return the lines written to the output and to the environment of the job."""
        self.executable("venv/bin/python", f"#!/bin/sh\necho '{version}'\n")
        self.executable("bin/pre-commit", f"#!{self.root}/venv/bin/python -E\nprint('pre-commit')\n")
        paths = {name: os.path.join(self.root, name) for name in ("output", "environment")}
        env = {
            **os.environ,
            "PATH": os.path.join(self.root, "bin") + os.pathsep + os.environ["PATH"],
            "GITHUB_OUTPUT": paths["output"],
            "GITHUB_ENV": paths["environment"],
            "RUNNER_OS": "Linux",
            "RUNNER_TEMP": temp,
            "PRE_COMMIT_VERSION": "4.7.0",
            "CONFIG_HASH": config,
        }
        result = subprocess.run(
            ["bash", "-e", "-c", command(KEY_STEP)], env=env, check=True, capture_output=True, text=True
        )
        found = {}
        for name, path in paths.items():
            with open(path) as handle:
                found[name] = handle.read().strip()
            os.remove(path)
        return found, result.stdout

    def test_the_key_has_the_system_pre_commit_the_python_of_pre_commit_and_the_configuration(self):
        found, _ = self.run_step(config="c0ffee")
        self.assertRegex(found["output"], r"^key=pre-commit-Linux-4\.7\.0-[0-9a-f]{64}-c0ffee$")

    def test_the_key_follows_the_python_of_pre_commit_and_not_the_one_of_the_path(self):
        first, _ = self.run_step("Python 3.12.3")
        self.assertNotEqual(first["output"], self.run_step("Python 3.13.1")[0]["output"])
        self.assertEqual(first["output"], self.run_step("Python 3.12.3")[0]["output"])

    def test_the_key_follows_the_folder_of_the_environments(self):
        """The environments of the hooks hold absolute paths, so a cache is not restored into another folder."""
        self.assertNotEqual(self.run_step(temp="/tmp/a")[0]["output"], self.run_step(temp="/tmp/b")[0]["output"])

    def test_the_key_follows_the_configuration(self):
        self.assertNotEqual(self.run_step(config="aaa")[0]["output"], self.run_step(config="bbb")[0]["output"])

    def test_the_log_names_the_python_that_the_key_was_computed_from(self):
        _, log = self.run_step("Python 3.12.3 (the build)")
        self.assertIn("Python 3.12.3 (the build)", log)

    def test_the_folder_of_pre_commit_is_set_for_the_next_steps(self):
        found, _ = self.run_step()
        self.assertEqual(found["environment"], "PRE_COMMIT_HOME=/tmp/runner/pre-commit")

    def test_the_configuration_hash_comes_to_the_step_through_the_environment(self):
        self.assertRegex(
            steps()[KEY_STEP],
            re.compile(
                r"^          CONFIG_HASH: \$\{\{ hashFiles\('\.pre-commit-config\.yaml'\) \}\}$", flags=re.MULTILINE
            ),
        )
        self.assertNotIn("${{", command(KEY_STEP))


SCRIPTS_STEP = "Find whether the scripts changed"
CONFIGURATION_STEP = "Test the configuration of the project"
READS_THE_REPOSITORY = re.compile(r'^ROOT = |"\.\.", "\.\."|os\.getcwd\(\)|dirname\(HERE\)', flags=re.MULTILINE)


def configuration_patterns():
    """Return the patterns of the tests that a project runs when its scripts did not change."""
    return re.findall(r"-k '([^']+)'", command(CONFIGURATION_STEP))


def modules_reading_the_repository():
    """Return the test modules that read a file of the repository, which a project edits. A module reads it
    when it defines ROOT, builds a path up from its folder with "..", "..", or uses the working directory."""
    found = []
    for name in sorted(os.listdir(HERE)):
        if name.startswith("test_") and name.endswith(".py"):
            with open(os.path.join(HERE, name), encoding="utf-8") as handle:
                if READS_THE_REPOSITORY.search(handle.read()):
                    found.append(name[:-3])
    return found


def command(name):
    """Return the shell script of the `run:` block of a step."""
    block = re.search(r"^        run: \|\n((?:          .*\n?)+)", steps()[name], flags=re.MULTILINE).group(1)
    return "\n".join(line[10:] for line in block.splitlines()) + "\n"


class ScriptsChanged(unittest.TestCase):
    """The step that tells the steps of the tests whether the coverage can have changed."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = self.directory.name
        self.git("init", "-q", "-b", "main")
        self.write({".groundwork/scripts/tool.py": "a\n", "README.md": "a\n", ".github/workflows/checks.yml": "a\n"})
        self.commit("initial")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")

    def tearDown(self):
        self.directory.cleanup()

    def git(self, *arguments):
        return subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", *arguments],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )

    def write(self, files):
        for name, content in files.items():
            path = os.path.join(self.root, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as handle:
                handle.write(content)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def changed(self, event="pull_request"):
        output = os.path.join(self.root, "..", os.path.basename(self.root) + ".output")
        env = {**os.environ, "GITHUB_EVENT_NAME": event, "BASE_REF": "main", "GITHUB_OUTPUT": output}
        subprocess.run(
            ["bash", "-e", "-c", command(SCRIPTS_STEP)],
            cwd=self.root,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            with open(output) as handle:
                return handle.read().strip()
        finally:
            os.remove(output)

    def test_a_push_to_main_always_measures(self):
        self.assertEqual(self.changed("push"), "changed=true")

    def test_a_change_of_a_script_measures(self):
        self.write({".groundwork/scripts/tool.py": "b\n"})
        self.commit("change")
        self.assertEqual(self.changed(), "changed=true")

    def test_a_change_of_the_workflow_measures(self):
        self.write({".github/workflows/checks.yml": "b\n"})
        self.commit("change")
        self.assertEqual(self.changed(), "changed=true")

    def test_a_script_moved_out_of_the_folder_measures(self):
        self.git("mv", ".groundwork/scripts/tool.py", "tool.py")
        self.commit("move")
        self.assertEqual(self.changed(), "changed=true")

    def test_a_change_of_a_text_does_not_measure(self):
        self.write({"README.md": "b\n", "docs/adr/0001-x.md": "# x\n"})
        self.commit("change")
        self.assertEqual(self.changed(), "changed=false")

    def test_a_base_that_cannot_be_compared_measures(self):
        self.git("update-ref", "-d", "refs/remotes/origin/main")
        self.assertEqual(self.changed(), "changed=true")

    def test_a_base_that_moved_on_is_not_a_change_of_the_pull_request(self):
        """The CI tests the merge of the pull request into the base, as it is when the CI runs."""
        self.git("switch", "-q", "-c", "pr")
        self.write({"README.md": "b\n"})
        self.commit("the pull request")
        self.git("switch", "-q", "main")
        self.write({".groundwork/scripts/tool.py": "c\n"})
        self.commit("the base moves on")
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.git("switch", "-q", "-c", "merge")
        self.git("merge", "-q", "--no-edit", "pr")
        self.assertEqual(self.changed(), "changed=false")


KIND_STEP = "Find whether the repository is a source of ADRs"
SOURCE_CONDITION = "hashFiles('.groundwork-version') == '' || vars.GROUNDWORK_SOURCE == 'true'"
RCFILE = ".groundwork/scripts/coveragerc"
COVERAGE_STEP = "Test the scripts and measure the coverage"
MEASURE = "steps.kind.outputs.source == 'true' && steps.scripts.outputs.changed == 'true'"
COMMANDS = [
    f"-m coverage run --rcfile={RCFILE} -m unittest discover -s .groundwork/scripts -p 'test_*.py'",
    f"-m coverage combine --rcfile={RCFILE}",
    f"-m coverage report --rcfile={RCFILE}",
]


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return handle.read()


@unittest.skipUnless(
    is_source(ROOT, os.environ), "the coverage is required of the scripts of a source of ADRs, not of a project"
)
class CoverageGate(unittest.TestCase):
    """The scripts of groundwork must be covered by their unit tests at a minimal level, in the CI of a source."""

    def condition(self, name):
        return re.search(r"^        if: (.+)$", steps()[name], flags=re.MULTILINE).group(1)

    def test_the_measure_runs_in_a_source_when_the_scripts_changed_and_the_plain_tests_do_not_then(self):
        self.assertEqual(self.condition(COVERAGE_STEP), "${{ " + MEASURE + " }}")
        self.assertEqual(
            self.condition("Test the scripts"), "${{ steps.kind.outputs.source != steps.scripts.outputs.changed }}"
        )

    def test_the_step_that_decides_receives_the_base_by_the_environment_only(self):
        step = steps()[SCRIPTS_STEP]
        self.assertNotIn("GITHUB_EVENT_NAME:", step)  # a default variable: GitHub ignores an assignment of it
        self.assertRegex(step, re.compile(r"^          BASE_REF: \$\{\{ github\.base_ref \}\}$", flags=re.MULTILINE))
        self.assertNotIn("${{", command(SCRIPTS_STEP))

    def test_the_step_that_decides_runs_before_the_tests(self):
        names = list(steps())
        self.assertLess(names.index(SCRIPTS_STEP), names.index(COVERAGE_STEP))
        self.assertLess(names.index(SCRIPTS_STEP), names.index("Test the scripts"))

    def test_the_two_steps_receive_the_variable_of_a_source_of_adrs(self):
        for name in (COVERAGE_STEP, "Test the scripts"):
            with self.subTest(step=name):
                self.assertRegex(
                    steps()[name],
                    re.compile(
                        r"^        env:\n          GROUNDWORK_SOURCE: \$\{\{ vars\.GROUNDWORK_SOURCE \}\}$",
                        flags=re.MULTILINE,
                    ),
                )

    def test_the_measure_runs_the_tests_combines_the_data_and_reports(self):
        step = steps()[COVERAGE_STEP]
        for command in COMMANDS:
            with self.subTest(command=command):
                self.assertIn(command, step)
        self.assertLess(step.index(COMMANDS[0]), step.index(COMMANDS[1]))
        self.assertLess(step.index(COMMANDS[1]), step.index(COMMANDS[2]))
        self.assertNotIn("--fail-under", step)

    def test_a_project_runs_all_the_tests_when_the_scripts_changed_and_those_of_its_configuration_otherwise(self):
        self.assertEqual(
            self.condition("Test the scripts"), "${{ steps.kind.outputs.source != steps.scripts.outputs.changed }}"
        )
        self.assertEqual(
            self.condition(CONFIGURATION_STEP),
            "${{ steps.kind.outputs.source != 'true' && steps.scripts.outputs.changed != 'true' }}",
        )

    def test_the_kind_of_the_repository_is_decided_once_from_the_files_and_the_variable(self):
        step = steps()[KIND_STEP]
        self.assertIn("id: kind", step)
        self.assertIn("SOURCE: ${{ " + SOURCE_CONDITION + " }}", step)
        self.assertNotIn("${{", command(KIND_STEP))
        self.assertLess(list(steps()).index(KIND_STEP), list(steps()).index(COVERAGE_STEP))

    def test_each_pattern_of_the_tests_of_the_configuration_matches_a_test(self):
        """A pattern that matches nothing runs nothing, and the step fails only when no pattern matches."""
        names = []

        def collect(suite):
            for item in suite:
                collect(item) if isinstance(item, unittest.TestSuite) else names.append(item.id())

        collect(unittest.defaultTestLoader.discover(HERE, "test_*.py"))
        for pattern in configuration_patterns():
            with self.subTest(pattern=pattern):
                self.assertTrue(any(pattern in name for name in names))

    def test_the_tests_of_the_configuration_run_after_the_step_that_decides_and_do_not_measure(self):
        names = list(steps())
        self.assertLess(names.index(SCRIPTS_STEP), names.index(CONFIGURATION_STEP))
        self.assertNotIn("coverage", steps()[CONFIGURATION_STEP])
        self.assertRegex(
            steps()[CONFIGURATION_STEP],
            re.compile(
                r"^        env:\n          GROUNDWORK_SOURCE: \$\{\{ vars\.GROUNDWORK_SOURCE \}\}$", flags=re.MULTILINE
            ),
        )

    def test_the_tests_of_the_configuration_name_each_module_that_reads_the_files_of_the_repository(self):
        """A test that reads a file of the repository, such as the workflow or the map of the practices, checks
        something that a project edits, so it runs on every pull request. A module that does not read one is
        left out, since the update brings the scripts and the source has already run their tests."""
        patterns = configuration_patterns()
        for module in modules_reading_the_repository():
            with self.subTest(module=module):
                self.assertTrue(any(pattern.startswith(module + ".") for pattern in patterns))

    def test_the_tests_of_the_configuration_name_only_modules_that_exist(self):
        for pattern in configuration_patterns():
            with self.subTest(pattern=pattern):
                self.assertTrue(os.path.isfile(os.path.join(HERE, pattern.split(".")[0] + ".py")))

    def test_the_plain_step_does_not_measure(self):
        self.assertIn("unittest discover", steps()["Test the scripts"])
        self.assertNotIn("coverage", steps()["Test the scripts"])

    def test_readme_gives_the_same_commands_as_the_workflow(self):
        readme = read("README.md")
        for command in COMMANDS:
            with self.subTest(command=command):
                self.assertIn("python3 " + command, readme)

    def test_the_configuration_measures_the_scripts_and_their_subprocesses_with_a_minimal_level(self):
        parser = configparser.ConfigParser()
        parser.read(os.path.join(ROOT, RCFILE), encoding="utf-8")
        self.assertEqual(parser["run"]["source"].strip(), ".groundwork/scripts")
        self.assertIn("*/test_*.py", parser["run"]["omit"])
        self.assertEqual(parser["run"]["patch"].strip(), "subprocess")
        self.assertTrue(parser["run"].getboolean("parallel"))
        self.assertTrue(parser["run"].getboolean("branch"))
        self.assertEqual(parser["report"].getfloat("fail_under"), 95)

    def test_the_tool_is_required_at_an_exact_version(self):
        self.assertRegex(
            read(".groundwork/scripts/requirements.txt"), re.compile(r"^coverage==[0-9][0-9.]*$", flags=re.MULTILINE)
        )

    def test_the_data_of_the_measure_are_not_tracked(self):
        self.assertRegex(read(".gitignore"), re.compile(r"^\.coverage\*$", flags=re.MULTILINE))

    def test_readme_states_the_licenses_that_groundwork_accepts_for_its_dependencies(self):
        readme = read("README.md")
        for name in ("MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "PSF-2.0"):
            with self.subTest(license=name):
                self.assertIn(name, readme)


LINT_STEP = "Lint and format the scripts"
RUFF_CONFIG = ".groundwork/scripts/ruff.toml"
LINT_COMMANDS = [
    "-m ruff check --config .groundwork/scripts/ruff.toml .groundwork/scripts",
    "-m ruff format --check --config .groundwork/scripts/ruff.toml .groundwork/scripts",
]


@unittest.skipUnless(
    is_source(ROOT, os.environ), "the lint is required of the scripts of a source of ADRs, not of a project"
)
class LintGate(unittest.TestCase):
    """The Python of groundwork is linted and formatted in the CI of a source, with Ruff (ADR 1005)."""

    def test_the_step_runs_in_a_source_only(self):
        condition = re.search(r"^        if: (.+)$", steps()[LINT_STEP], flags=re.MULTILINE).group(1)
        self.assertEqual(condition, "${{ steps.kind.outputs.source == 'true' }}")

    def test_the_step_checks_and_formats_with_the_tool_of_the_scripts(self):
        step = steps()[LINT_STEP]
        for lint in LINT_COMMANDS:
            with self.subTest(command=lint):
                self.assertIn('"$RUNNER_TEMP/scripts/bin/python" ' + lint, step)
        self.assertLess(step.index(LINT_COMMANDS[0]), step.index(LINT_COMMANDS[1]))

    def test_the_step_runs_after_the_dependencies_and_the_kind_of_the_repository(self):
        names = list(steps())
        self.assertLess(names.index("Install the dependencies of the scripts"), names.index(LINT_STEP))
        self.assertLess(names.index(KIND_STEP), names.index(LINT_STEP))

    def test_the_step_does_not_wait_for_the_tests_or_the_measure(self):
        names = list(steps())
        self.assertLess(names.index(LINT_STEP), names.index(COVERAGE_STEP))

    def test_the_tool_is_required_at_an_exact_version(self):
        self.assertRegex(
            read(".groundwork/scripts/requirements.txt"), re.compile(r"^ruff==[0-9][0-9.]*$", flags=re.MULTILINE)
        )

    def test_the_configuration_sets_the_length_of_the_lines_and_the_rules(self):
        config = read(RUFF_CONFIG)
        self.assertRegex(config, re.compile(r"^line-length = 120$", flags=re.MULTILINE))
        self.assertRegex(config, re.compile(r'^select = \["E4", "E7", "E9", "F", "I"\]$', flags=re.MULTILINE))

    def test_the_tool_is_not_a_hook_of_the_pre_commit_configuration(self):
        self.assertNotIn("ruff", read(".pre-commit-config.yaml"))

    def test_readme_gives_the_same_commands_as_the_workflow(self):
        readme = read("README.md")
        for lint in LINT_COMMANDS:
            with self.subTest(command=lint):
                self.assertIn("python3 " + lint, readme)


if __name__ == "__main__":
    unittest.main()
