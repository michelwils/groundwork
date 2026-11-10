import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SCRIPT = os.path.join(HERE, "check_branch.py")
GIT_ENV = {
    **{name: value for name, value in os.environ.items() if not name.startswith("GIT_")},
    "GIT_AUTHOR_NAME": "A",
    "GIT_AUTHOR_EMAIL": "a@example.com",
    "GIT_COMMITTER_NAME": "A",
    "GIT_COMMITTER_EMAIL": "a@example.com",
}


def git(directory, *arguments):
    return subprocess.run(
        ["git", *arguments], cwd=directory, env=GIT_ENV, check=True, capture_output=True, text=True
    ).stdout


def run(directory, environment=None):
    return subprocess.run(
        [sys.executable, "-I", SCRIPT], cwd=directory, env=environment or GIT_ENV, capture_output=True, text=True
    )


class Repository(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)
        git(self.directory, "init", "-q", "-b", "main")
        git(self.directory, "commit", "-q", "--allow-empty", "-m", "chore: start")

    def on(self, branch):
        git(self.directory, "switch", "-q", "-c", branch)
        return run(self.directory)


class Accepted(Repository):
    def test_a_name_of_the_workflow(self):
        for branch in ("fix/243-a-slug", "feat/243-reject-a-wrongly-named-branch", "docs/1-bootstrap"):
            with self.subTest(branch=branch):
                result = self.on(branch)
                self.assertEqual(result.returncode, 0, result.stderr)
                git(self.directory, "switch", "-q", "main")

    def test_the_branch_of_the_fix_of_a_vulnerability_that_is_not_public_yet(self):
        self.assertEqual(self.on("fix/0-a-slug").returncode, 0)

    def test_the_branches_of_the_bots(self):
        for branch in ("dependabot/pre_commit/hooks-1a6e794268", "groundwork/update-to-v0-3-0"):
            with self.subTest(branch=branch):
                self.assertEqual(self.on(branch).returncode, 0)
                git(self.directory, "switch", "-q", "main")

    def test_the_main_branch(self):
        result = run(self.directory)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_maintenance_branch(self):
        self.assertEqual(self.on("maintenance/v1").returncode, 0)

    def test_the_other_usual_name_of_the_default_branch(self):
        git(self.directory, "branch", "-m", "master")
        self.assertEqual(run(self.directory).returncode, 0)

    def test_the_default_branch_that_the_remote_names(self):
        git(self.directory, "branch", "-m", "trunk")
        self.assertEqual(run(self.directory).returncode, 1)
        git(self.directory, "update-ref", "refs/remotes/origin/trunk", "HEAD")
        git(self.directory, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
        self.assertEqual(run(self.directory).returncode, 0)

    def test_git_that_is_not_installed(self):
        result = run(self.directory, {**GIT_ENV, "PATH": ""})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_detached_head(self):
        git(self.directory, "checkout", "-q", "--detach")
        result = run(self.directory)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_directory_that_is_not_a_repository(self):
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(run(other).returncode, 0)


class Rejected(Repository):
    def test_a_name_that_is_not_of_the_workflow(self):
        for branch in ("my-branch", "Fix/243-x", "feature/243-x", "fix/x", "fix/243", "fix/243-Slug", "wip/243-x"):
            with self.subTest(branch=branch):
                result = self.on(branch)
                self.assertEqual(result.returncode, 1)
                git(self.directory, "switch", "-q", "main")

    def test_the_message_gives_the_branch_the_expected_name_and_the_command_to_rename(self):
        result = self.on("my-branch")
        self.assertEqual(result.stdout, "")
        self.assertIn("error: ", result.stderr)
        self.assertIn("'my-branch'", result.stderr)
        self.assertIn("<type>/<issue-number>-<slug>", result.stderr)
        self.assertIn("git branch -m <type>/<issue-number>-<slug>", result.stderr)

    def test_a_branch_that_only_looks_like_a_bot_branch(self):
        self.assertEqual(self.on("groundwork-update/v0-3-0").returncode, 1)

    def test_a_maintenance_branch_of_no_major_version(self):
        self.assertEqual(self.on("maintenance/latest").returncode, 1)


class Hook(Repository):
    """The hook of the configuration of the repository, run by git at a commit."""

    def setUp(self):
        super().setUp()
        if not shutil.which("pre-commit"):
            self.skipTest("pre-commit is not installed")
        os.makedirs(os.path.join(self.directory, ".groundwork", "scripts"))
        for name in ("check_branch.py", "check_pull_request.py"):
            shutil.copy(os.path.join(HERE, name), os.path.join(self.directory, ".groundwork", "scripts", name))
        with open(os.path.join(ROOT, ".pre-commit-config.yaml"), encoding="utf-8") as handle:
            text = handle.read()
        start = text.index("      - id: branch-name\n")
        end = text.index("      # /groundwork", start)
        with open(os.path.join(self.directory, ".pre-commit-config.yaml"), "w", encoding="utf-8") as handle:
            handle.write("repos:\n  - repo: local\n    hooks:\n" + text[start:end])
        git(self.directory, "add", ".")
        git(self.directory, "commit", "-q", "-m", "chore: add the hook")
        subprocess.run(
            ["pre-commit", "install", "-t", "pre-commit"], cwd=self.directory, check=True, capture_output=True
        )

    def commit(self):
        with open(os.path.join(self.directory, "file.txt"), "w", encoding="utf-8") as handle:
            handle.write("a\n")
        git(self.directory, "add", "file.txt")
        return subprocess.run(
            ["git", "commit", "-q", "-m", "chore: a change"],
            cwd=self.directory,
            env=GIT_ENV,
            capture_output=True,
            text=True,
        )

    def test_a_commit_on_a_wrongly_named_branch_is_rejected(self):
        git(self.directory, "switch", "-q", "-c", "my-branch")
        result = self.commit()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("my-branch", result.stdout + result.stderr)

    def test_a_commit_on_a_branch_of_the_workflow_passes(self):
        git(self.directory, "switch", "-q", "-c", "fix/243-a-slug")
        result = self.commit()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
