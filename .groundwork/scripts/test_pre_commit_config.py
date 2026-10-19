import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "..", "..", ".pre-commit-config.yaml")
WORKFLOW = os.path.join(HERE, "..", "..", ".github", "workflows", "checks.yml")
REQUIREMENTS = ".groundwork/scripts/requirements.txt"


def read(path):
    with open(path) as handle:
        return handle.read()


def audit():
    """Return the text of the entry of the repository of pip-audit, without its comments."""
    text = re.sub(r"^\s*#.*\n", "", read(CONFIG), flags=re.MULTILINE)
    found = re.search(r"^  - repo: https://github.com/pypa/pip-audit\n(?:    .*\n|\n)+", text, flags=re.MULTILINE)
    return found.group(0) if found else ""


class AuditOfTheDependencies(unittest.TestCase):
    def test_the_dependencies_of_the_scripts_are_audited(self):
        self.assertIn("id: pip-audit", audit())

    def test_the_tool_is_pinned_to_a_version(self):
        self.assertRegex(audit(), r"rev: v\d+\.\d+\.\d+\n")

    def test_it_audits_the_requirements_file_without_resolving_it(self):
        entry = audit()
        self.assertIn(REQUIREMENTS, entry)
        for argument in ("-r", "--no-deps", "--disable-pip"):
            self.assertRegex(entry, rf"[\[ ,]{re.escape(argument)}[\],]")

    def test_it_runs_only_when_the_requirements_file_changes(self):
        found = re.search(r"files: (.+)\n", audit())
        self.assertIsNotNone(found)
        pattern = re.compile(found.group(1).strip("'\""))
        self.assertTrue(pattern.search(REQUIREMENTS))
        for other in ("README.md", ".pre-commit-config.yaml", ".groundwork/scripts/release.py"):
            self.assertFalse(pattern.search(other), other)

    def test_it_runs_before_a_commit_and_in_the_stage_that_the_ci_runs(self):
        found = re.search(r"stages: \[(.+)\]", audit())
        self.assertIsNotNone(found)
        stages = [stage.strip() for stage in found.group(1).split(",")]
        self.assertEqual(sorted(stages), ["manual", "pre-commit"])
        self.assertIn("--hook-stage manual", read(WORKFLOW))


if __name__ == "__main__":
    unittest.main()
