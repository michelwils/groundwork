import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_pull_request  # noqa: E402

SCRIPT = os.path.join(HERE, "check_pull_request.py")
TYPES = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"]
TEMPLATE = """Closes #12

<!-- The backport of a fix to a maintained version has `Refs #<issue-number>` instead of `Closes`, and no checklist. -->

## Plan

<!-- Optional. The files, tests and risks agreed before the work. -->

## Acceptance criteria

- [x] A criterion
"""


def check(branch="feat/12-add-a-check", base="main", body="Closes #12"):
    return check_pull_request.check(branch, base, body)


class Accepted(unittest.TestCase):
    def test_every_type(self):
        for kind in TYPES:
            with self.subTest(kind=kind):
                self.assertEqual(check(branch=f"{kind}/12-add-a-check"), [])

    def test_filled_template(self):
        self.assertEqual(check(body=TEMPLATE), [])

    def test_dependency_update_bot_is_skipped(self):
        self.assertEqual(check(branch="dependabot/pre_commit/hooks-1a6e794268", body=""), [])

    def test_direct_fix_on_a_maintenance_branch_closes_its_issue(self):
        self.assertEqual(check(branch="fix/12-handle-empty-input", base="maintenance/v1"), [])

    def test_backport_refers_to_its_issue(self):
        self.assertEqual(
            check(branch="fix/12-handle-empty-input-v1", base="maintenance/v1", body="Refs #12"), []
        )


class BranchName(unittest.TestCase):
    def test_rejected_names(self):
        for branch in [
            "main",
            "feature/12-add-a-check",
            "feat/add-a-check-12",
            "feat/12",
            "feat/12-",
            "feat/12-Add-a-check",
            "feat/12-add_a_check",
            "feat/12-add-a-check-",
            "feat/12--add",
            "feat/12-add/a-check",
        ]:
            with self.subTest(branch=branch):
                self.assertEqual(len(check(branch=branch)), 1)


class ClosingLine(unittest.TestCase):
    def test_missing_description(self):
        self.assertEqual(len(check(body="")), 1)
        self.assertEqual(len(check(body=None)), 1)

    def test_no_closes(self):
        self.assertEqual(len(check(body="Adds a check.")), 1)

    def test_another_issue(self):
        self.assertEqual(len(check(body="Closes #13")), 1)

    def test_two_issues(self):
        self.assertEqual(len(check(body="Closes #12\nCloses #13")), 1)

    def test_refs_is_not_enough(self):
        self.assertEqual(len(check(body="Refs #12")), 1)


class Backport(unittest.TestCase):
    BRANCH = "fix/12-handle-empty-input-v1"

    def test_closes_is_rejected(self):
        self.assertEqual(len(check(branch=self.BRANCH, base="maintenance/v1", body="Closes #12\nRefs #12")), 1)

    def test_missing_refs(self):
        self.assertEqual(len(check(branch=self.BRANCH, base="maintenance/v1", body="")), 1)

    def test_refs_to_another_issue(self):
        self.assertEqual(len(check(branch=self.BRANCH, base="maintenance/v1", body="Refs #13")), 1)

    def test_other_major_version_is_not_a_backport(self):
        self.assertEqual(len(check(branch=self.BRANCH, base="maintenance/v2", body="Refs #12")), 1)
        self.assertEqual(check(branch=self.BRANCH, base="maintenance/v2", body="Closes #12"), [])


class CommandLine(unittest.TestCase):
    def run_script(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)

    def test_conforming_pull_request(self):
        result = self.run_script("feat/12-add-a-check", "main", "Closes #12")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

    def test_failing_pull_request(self):
        result = self.run_script("feat/12-add-a-check", "main", "")
        self.assertEqual(result.returncode, 1)
        self.assertIn("error:", result.stderr)

    def test_wrong_number_of_arguments(self):
        self.assertEqual(self.run_script("feat/12-add-a-check").returncode, 2)


if __name__ == "__main__":
    unittest.main()
