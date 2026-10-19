import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
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

    def test_the_tests_of_the_scripts_receive_the_variable_of_a_source_of_adrs(self):
        step = steps()["Test the scripts"]
        self.assertRegex(step, re.compile(r"^        env:\n          GROUNDWORK_SOURCE: \$\{\{ vars\.GROUNDWORK_SOURCE \}\}$", flags=re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
