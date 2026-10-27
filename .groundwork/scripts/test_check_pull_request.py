import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_pull_request  # noqa: E402
import open_update_pull_request  # noqa: E402

SCRIPT = os.path.join(HERE, "check_pull_request.py")
TYPES = ["feat", "fix", "docs", "style", "refactor", "perf", "test", "build", "ci", "chore", "revert"]
TEMPLATE = """Closes #12

<!-- The backport of a fix to a maintained version has `Refs #<issue-number>` instead of `Closes`, and no checklist. -->

## Plan

<!-- Optional. The files, tests and risks agreed before the work. -->

## Acceptance criteria

- [x] A criterion
"""


def check(branch="feat/12-add-a-check", base="main", body="Closes #12", title="feat: add a check"):
    return check_pull_request.check(branch, base, body, title)


class Accepted(unittest.TestCase):
    def test_every_type(self):
        for kind in TYPES:
            with self.subTest(kind=kind):
                self.assertEqual(check(branch=f"{kind}/12-add-a-check"), [])

    def test_filled_template(self):
        self.assertEqual(check(body=TEMPLATE), [])

    def test_dependency_update_bot_is_skipped(self):
        self.assertEqual(check(branch="dependabot/pre_commit/hooks-1a6e794268", body=""), [])

    def test_groundwork_update_is_skipped(self):
        self.assertEqual(check(branch="groundwork/update-to-v0-3-0", body=""), [])

    def test_a_branch_that_only_looks_like_a_bot_branch_is_not_skipped(self):
        self.assertNotEqual(check(branch="groundwork-update/v0-3-0", body=""), [])

    def test_direct_fix_on_a_maintenance_branch_closes_its_issue(self):
        self.assertEqual(check(branch="fix/12-handle-empty-input", base="maintenance/v1"), [])

    def test_backport_refers_to_its_issue(self):
        self.assertEqual(
            check(branch="fix/12-handle-empty-input-v1", base="maintenance/v1", body="Refs #12"), []
        )


class UpdateOfGroundwork(unittest.TestCase):
    """The pull request that moves a project to a later groundwork, and the branches of the update script."""

    def test_the_branch_without_an_issue_and_its_body_are_accepted(self):
        for added in ([], ["0002"]):
            for conflicts in ([], ["a.md"]):
                with self.subTest(added=added, conflicts=conflicts):
                    body = open_update_pull_request.body("0.1.0", "0.2.0", conflicts, "https://github.com/o/g.git", added)
                    self.assertEqual(check_pull_request.check("groundwork/update-to-v0-2-0", "main", body, "chore: update"), [])

    def test_the_branch_with_an_issue_is_accepted_with_its_closing_line(self):
        self.assertEqual(check_pull_request.check("chore/42-update-groundwork-to-v0-2-0", "main", "Closes #42", "chore: update"), [])


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


class BreakingChange(unittest.TestCase):
    BODY = "Closes #12\n\nBREAKING CHANGE: clients must read `account`."

    def test_a_title_with_a_bang_needs_the_footer(self):
        for title in ["feat!: rename it", "refactor(api)!: rename it", "revert!: add x"]:
            with self.subTest(title=title):
                self.assertEqual(len(check(title=title)), 1)
                self.assertIn("BREAKING CHANGE:", check(title=title)[0])
                self.assertEqual(check(body=self.BODY, title=title), [])

    def test_the_footer_is_a_line_of_its_own(self):
        self.assertEqual(len(check(body="Closes #12\nThe BREAKING CHANGE: is told.", title="feat!: rename it")), 1)

    def test_a_footer_without_text_is_not_enough(self):
        self.assertEqual(len(check(body="Closes #12\nBREAKING CHANGE:", title="feat!: rename it")), 1)

    def test_a_title_without_a_bang_needs_no_footer(self):
        for title in ["feat: rename it", "feat: rename it!", "feat(api): rename it (#4)"]:
            with self.subTest(title=title):
                self.assertEqual(check(title=title), [])

    def test_a_title_with_a_type_that_is_not_one_of_ADR_0002_is_not_a_breaking_change(self):
        self.assertEqual(check(title="wip!: rename it"), [])

    def test_a_backport_needs_it_too(self):
        branch = "fix/12-handle-empty-input-v1"
        self.assertEqual(len(check(branch=branch, base="maintenance/v1", body="Refs #12", title="fix!: change it")), 1)
        self.assertEqual(
            check(branch=branch, base="maintenance/v1", body="Refs #12\nBREAKING CHANGE: read `account`.", title="fix!: change it"),
            [],
        )

    def test_the_problems_of_the_branch_and_of_the_footer_are_both_given(self):
        self.assertEqual(len(check(body="", title="feat!: rename it")), 2)

    def test_the_branches_of_bots_are_skipped(self):
        self.assertEqual(check(branch="dependabot/pip/x-1", body="", title="Bump x!: y"), [])


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
        result = self.run_script("feat/12-add-a-check", "main", "Closes #12", "feat: add a check")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")

    def test_failing_pull_request(self):
        result = self.run_script("feat/12-add-a-check", "main", "", "feat: add a check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("error:", result.stderr)

    def test_wrong_number_of_arguments_gives_an_error_line_and_the_usage(self):
        result = self.run_script("feat/12-add-a-check")
        self.assertEqual(result.returncode, 2)
        self.assertTrue(result.stderr.startswith("error: expected 4 arguments, got 1\n"), result.stderr)
        self.assertIn("Usage:", result.stderr)

    def test_wrong_number_of_arguments(self):
        self.assertEqual(self.run_script("feat/12-add-a-check").returncode, 2)
        self.assertEqual(self.run_script("feat/12-add-a-check", "main", "Closes #12").returncode, 2)


if __name__ == "__main__":
    unittest.main()
