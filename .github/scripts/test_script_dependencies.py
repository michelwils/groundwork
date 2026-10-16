import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
PIN = re.compile(r"^[A-Za-z0-9_.\-]+==[0-9][A-Za-z0-9.\-+]*$")


def read(*parts):
    with open(os.path.join(ROOT, *parts)) as handle:
        return handle.read()


def requirements():
    lines = [line.strip() for line in read(".github", "scripts", "requirements.txt").splitlines()]
    return [line for line in lines if line and not line.startswith("#")]


class ScriptDependencies(unittest.TestCase):
    def test_every_requirement_of_the_scripts_is_pinned_to_an_exact_version(self):
        self.assertTrue(requirements())
        for line in requirements():
            with self.subTest(line=line):
                self.assertRegex(line, PIN)

    def test_the_hook_that_checks_the_links_installs_the_pinned_versions(self):
        config = read(".pre-commit-config.yaml")
        hook = config.split("id: markdown-links", 1)[1].split("\n      - id:", 1)[0]
        match = re.search(r"additional_dependencies:\s*\[([^\]]*)\]", hook)
        self.assertIsNotNone(match, "the hook has no additional_dependencies")
        installed = {item.strip().lower() for item in match.group(1).split(",") if item.strip()}
        self.assertEqual(installed, {line.lower() for line in requirements()})

    def test_the_workflow_installs_the_requirements_of_the_scripts_before_testing_them(self):
        workflow = read(".github", "workflows", "checks.yml")
        self.assertIn("pip install -r .github/scripts/requirements.txt", workflow)
        self.assertLess(workflow.index("requirements.txt"), workflow.index("unittest discover"))


if __name__ == "__main__":
    unittest.main()
