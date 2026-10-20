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
BOT_PULL_REQUEST = "!(startsWith(github.head_ref, 'dependabot/') && github.event.pull_request.user.login == 'dependabot[bot]')"


def steps():
    """Return the text of each step of the workflow, by name, without its comments."""
    with open(WORKFLOW) as handle:
        text = re.sub(r"^\s*#.*\n", "", handle.read(), flags=re.MULTILINE)
    parts = re.split(r"^      - (?=name:|uses:)", text, flags=re.MULTILINE)[1:]
    found = {}
    for part in parts:
        match = re.match(r"name: (.+)", part)
        found[match.group(1).strip() if match else part.splitlines()[0]] = part
    return found


class ChecksWorkflow(unittest.TestCase):
    def test_the_title_of_a_pull_request_of_dependabot_is_not_checked(self):
        step = steps()["Check the pull request title"]
        condition = re.search(r"^        if: (.+)$", step, flags=re.MULTILINE)
        self.assertIsNotNone(condition)
        self.assertIn(BOT_PULL_REQUEST, condition.group(1))
        self.assertIn("github.event_name == 'pull_request'", condition.group(1))

    def test_a_branch_named_like_those_of_dependabot_is_not_enough_to_skip_the_check(self):
        condition = re.search(r"^        if: (.+)$", steps()["Check the pull request title"], flags=re.MULTILINE).group(1)
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
        self.assertRegex(step, re.compile(r"^        env:\n          GROUNDWORK_SOURCE: \$\{\{ vars\.GROUNDWORK_SOURCE \}\}$", flags=re.MULTILINE))


SCRIPTS_STEP = "Find whether the scripts changed"


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
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *arguments], cwd=self.root, check=True, capture_output=True, text=True)

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
        subprocess.run(["bash", "-e", "-c", command(SCRIPTS_STEP)], cwd=self.root, env=env, check=True, capture_output=True, text=True)
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


SOURCE_CONDITION = "hashFiles('.groundwork-version') == '' || vars.GROUNDWORK_SOURCE == 'true'"
RCFILE = ".groundwork/scripts/coveragerc"
COVERAGE_STEP = "Test the scripts and measure the coverage"
MEASURE = f"({SOURCE_CONDITION}) && steps.scripts.outputs.changed == 'true'"
COMMANDS = [
    f"-m coverage run --rcfile={RCFILE} -m unittest discover -s .groundwork/scripts -p 'test_*.py'",
    f"-m coverage combine --rcfile={RCFILE}",
    f"-m coverage report --rcfile={RCFILE}",
]


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as handle:
        return handle.read()


@unittest.skipUnless(is_source(ROOT, os.environ), "the coverage is required of the scripts of a source of ADRs, not of a project")
class CoverageGate(unittest.TestCase):
    """The scripts of groundwork must be covered by their unit tests at a minimal level, in the CI of a source."""

    def condition(self, name):
        return re.search(r"^        if: (.+)$", steps()[name], flags=re.MULTILINE).group(1)

    def test_the_measure_runs_in_a_source_when_the_scripts_changed_and_the_plain_tests_everywhere_else(self):
        self.assertEqual(self.condition(COVERAGE_STEP), "${{ " + MEASURE + " }}")
        self.assertEqual(self.condition("Test the scripts"), "${{ !(" + MEASURE + ") }}")

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
                self.assertRegex(steps()[name], re.compile(r"^        env:\n          GROUNDWORK_SOURCE: \$\{\{ vars\.GROUNDWORK_SOURCE \}\}$", flags=re.MULTILINE))

    def test_the_measure_runs_the_tests_combines_the_data_and_reports(self):
        step = steps()[COVERAGE_STEP]
        for command in COMMANDS:
            with self.subTest(command=command):
                self.assertIn(command, step)
        self.assertLess(step.index(COMMANDS[0]), step.index(COMMANDS[1]))
        self.assertLess(step.index(COMMANDS[1]), step.index(COMMANDS[2]))
        self.assertNotIn("--fail-under", step)

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
        self.assertRegex(read(".groundwork/scripts/requirements.txt"), re.compile(r"^coverage==[0-9][0-9.]*$", flags=re.MULTILINE))

    def test_the_data_of_the_measure_are_not_tracked(self):
        self.assertRegex(read(".gitignore"), re.compile(r"^\.coverage\*$", flags=re.MULTILINE))

    def test_readme_states_the_licenses_that_groundwork_accepts_for_its_dependencies(self):
        readme = read("README.md")
        for name in ("MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "PSF-2.0"):
            with self.subTest(license=name):
                self.assertIn(name, readme)


if __name__ == "__main__":
    unittest.main()
