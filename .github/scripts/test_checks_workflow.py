import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOW = os.path.join(HERE, "..", "workflows", "checks.yml")
BOT_BRANCH = "!startsWith(github.head_ref, 'dependabot/')"


def steps():
    """Return the text of each step of the workflow, by name."""
    with open(WORKFLOW) as handle:
        text = handle.read()
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
        self.assertIn(BOT_BRANCH, condition.group(1))
        self.assertIn("github.event_name == 'pull_request'", condition.group(1))

    def test_no_other_step_skips_the_pull_requests_of_dependabot(self):
        for name, step in steps().items():
            if name != "Check the pull request title":
                with self.subTest(step=name):
                    self.assertNotIn("dependabot", step)

    def test_the_branch_name_is_still_given_to_the_check_of_the_branch(self):
        step = steps()["Check the branch name and the closing line of the pull request"]
        self.assertIn("check_pull_request.py", step)
        self.assertNotIn("startsWith", step)


if __name__ == "__main__":
    unittest.main()
