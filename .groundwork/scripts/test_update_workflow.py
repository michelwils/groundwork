import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOW = os.path.join(HERE, "..", "..", ".github", "workflows", "update-groundwork.yml")


def secret_check():
    """Return the text of the step 'Check the secret', without the comments of the workflow."""
    with open(WORKFLOW, encoding="utf-8") as handle:
        text = re.sub(r"^\s*#.*\n", "", handle.read(), flags=re.MULTILINE)
    step = re.search(r"^      - name: Check the secret\n(.*?)(?=^      - |\Z)", text, flags=re.MULTILINE | re.DOTALL)
    assert step, "the workflow has no step 'Check the secret'"
    return step.group(1)


def error_of_the_secret_check():
    message = re.search(r"::error::(.+)", secret_check())
    assert message, "the step 'Check the secret' prints no error"
    return message.group(1)


class UpdateWorkflow(unittest.TestCase):
    def test_the_error_of_the_secret_does_not_send_to_the_readme_of_the_project(self):
        self.assertNotRegex(error_of_the_secret_check(), r"(?i)readme")

    def test_the_error_of_the_secret_gives_the_command_that_creates_it(self):
        self.assertIn("gh secret set GROUNDWORK_UPDATE_TOKEN --repo $REPOSITORY", error_of_the_secret_check())

    def test_the_step_defines_the_repository_that_the_command_names(self):
        self.assertRegex(secret_check(), r"(?m)^          REPOSITORY: \$\{\{ github\.repository \}\}$")

    def test_the_error_of_the_secret_tells_where_groundwork_describes_it(self):
        self.assertIn("https://github.com/michelwils/groundwork#automatic-update", error_of_the_secret_check())


if __name__ == "__main__":
    unittest.main()
