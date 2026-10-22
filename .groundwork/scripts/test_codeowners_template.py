import fnmatch
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TEMPLATE = os.path.join(ROOT, ".groundwork", "CODEOWNERS.template")
IN_A_PROJECT = os.path.exists(os.path.join(ROOT, ".groundwork-version"))

# What a project cannot change without a review: the files of groundwork, and the file that says who reviews them.
PROTECTED = [
    "/docs/adr/0*",
    "/docs/adr/template.md",
    "/.groundwork*",
    "/.github/workflows/",
    "/.github/zizmor.yml",
    "/.github/dependabot.yml",
    "/.pre-commit-config.yaml",
    "/.github/CODEOWNERS",
]
# What a project is meant to change by itself.
LEFT_TO_THE_PROJECT = ["CONTRIBUTING.md", "AGENTS.md", "README.md", "docs/adr/1000-own-decision.md"]


def rules():
    with open(TEMPLATE) as handle:
        lines = [line.strip() for line in handle if line.strip() and not line.lstrip().startswith("#")]
    return [line.split() for line in lines]


def matches(pattern, path):
    """Tell whether the path falls under the pattern: anchored by a leading slash, a directory by a trailing one."""
    pattern = pattern.lstrip("/")
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return fnmatch.fnmatch(path, pattern)


def tracked():
    return subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split("\n")


class CodeownersTemplate(unittest.TestCase):
    def test_every_line_gives_a_pattern_and_the_one_owner_to_replace(self):
        for fields in rules():
            with self.subTest(fields=fields):
                self.assertEqual(len(fields), 2)
                self.assertEqual(fields[1], "@OWNER")

    def test_it_protects_the_files_of_groundwork(self):
        self.assertEqual([fields[0] for fields in rules()], PROTECTED)

    @unittest.skipIf(IN_A_PROJECT, "a project may have left out the ADRs that own these files")
    def test_each_pattern_but_the_file_itself_matches_a_file_of_groundwork(self):
        files = tracked()
        for pattern in PROTECTED:
            if pattern == "/.github/CODEOWNERS":
                continue  # groundwork does not use the template: a project copies it there
            with self.subTest(pattern=pattern):
                self.assertTrue(any(matches(pattern, path) for path in files))

    def test_it_leaves_to_the_project_the_files_that_it_changes_by_itself(self):
        for path in LEFT_TO_THE_PROJECT:
            with self.subTest(path=path):
                self.assertFalse(any(matches(fields[0], path) for fields in rules()))

    def test_it_covers_the_configuration_of_the_audits_and_of_the_updates_of_dependencies(self):
        for path in (".github/zizmor.yml", ".github/dependabot.yml"):
            with self.subTest(path=path):
                self.assertTrue(any(matches(fields[0], path) for fields in rules()))

    def test_it_covers_the_files_that_decide_where_the_updates_come_from(self):
        for path in (".groundwork-version", ".groundwork-source", ".groundwork-adrs", ".groundwork-ranges", ".groundwork/scripts/update_groundwork.py"):
            with self.subTest(path=path):
                self.assertTrue(any(matches(fields[0], path) for fields in rules()))


class InAProject(unittest.TestCase):
    @unittest.skipIf(IN_A_PROJECT, "it builds the project itself")
    def test_a_project_that_left_out_the_adrs_that_own_other_files_does_not_fail(self):
        # ADR 0014 needs ADR 0003 and ADR 0007 only: a project may keep it without .pre-commit-config.yaml, dependabot.yml or zizmor.yml.
        with tempfile.TemporaryDirectory() as directory:
            scripts = os.path.join(directory, ".groundwork", "scripts")
            os.makedirs(scripts)
            shutil.copy(TEMPLATE, os.path.join(directory, ".groundwork"))
            shutil.copy(os.path.join(HERE, "test_codeowners_template.py"), scripts)
            with open(os.path.join(directory, ".groundwork-version"), "w") as handle:
                handle.write("0.6.0\n")
            subprocess.run(["git", "init", "-q"], cwd=directory, check=True)
            subprocess.run(["git", "add", "-A"], cwd=directory, check=True)
            result = subprocess.run(
                [sys.executable, "-I", "-m", "unittest", "discover", "-s", scripts, "-p", "test_codeowners_template.py"],
                cwd=directory, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("skipped=2", result.stderr)  # this test, and the one that looks for the files of groundwork


if __name__ == "__main__":
    unittest.main()
