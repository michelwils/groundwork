import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_pull_request  # noqa: E402

SCRIPT = os.path.join(HERE, "update_groundwork.py")

V1 = {
    "README.md": "# groundwork\n",
    "LICENSE": "MIT\n",
    "CONTRIBUTING.md": "one\ntwo\nthree\n",
    "SECURITY.md": "security\n",
    "old.md": "old\n",
    "logo.bin": "a\0b",
}
V2 = {
    **V1,
    "README.md": "# groundwork 0.2\n",
    "LICENSE": "MIT 2026\n",
    "CONTRIBUTING.md": "one\ntwo changed\nthree\n",
    "new.md": "new\n",
    "logo.bin": "a\0c",
}
V3 = {name: content for name, content in V2.items() if name != "old.md"}
V3["SECURITY.md"] = "security 0.3\n"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def init(path):
    os.makedirs(path)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")
    git(path, "config", "commit.gpgsign", "false")
    git(path, "config", "tag.gpgsign", "false")
    git(path, "config", "core.hooksPath", os.devnull)


def write(path, files):
    for name, content in files.items():
        with open(os.path.join(path, name), "w") as handle:
            handle.write(content)


def read(path, name):
    with open(os.path.join(path, name)) as handle:
        return handle.read()


class Update(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = self.directory.name
        self.source = os.path.join(root, "groundwork")
        init(self.source)
        for version, files in (("0.1.0", V1), ("0.2.0", V2), ("0.3.0", V3)):
            for name in os.listdir(self.source):
                if name != ".git":
                    os.remove(os.path.join(self.source, name))
            write(self.source, files)
            git(self.source, "add", "-A")
            git(self.source, "commit", "-q", "-m", f"feat: release {version}")
            git(self.source, "tag", "-a", f"v{version}", "-m", f"v{version}")
        self.project = os.path.join(root, "project")
        self.adopt("0.1.0", V1)

    def tearDown(self):
        self.directory.cleanup()

    def adopt(self, version, files):
        init(self.project)
        write(self.project, {**files, ".groundwork-version": f"{version}\n" if version else ""})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "Initial commit")

    def commit_project(self, files):
        write(self.project, files)
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "docs: adjust the project")

    def run_script(self, *args, issue="42"):
        return subprocess.run(
            [sys.executable, SCRIPT, issue, "--source", self.source, *args],
            cwd=self.project,
            capture_output=True,
            text=True,
        )

    def branches(self):
        return git(self.project, "branch", "--format=%(refname:short)").split()

    def test_updates_to_the_latest_version(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "chore/42-update-groundwork-to-v0-3-0")
        self.assertEqual(read(self.project, "new.md"), "new\n")
        self.assertEqual(read(self.project, "CONTRIBUTING.md"), V3["CONTRIBUTING.md"])
        self.assertEqual(read(self.project, "SECURITY.md"), V3["SECURITY.md"])
        self.assertEqual(read(self.project, ".groundwork-version"), "0.3.0\n")

    def test_removes_a_file_that_groundwork_removed(self):
        self.run_script()
        self.assertFalse(os.path.exists(os.path.join(self.project, "old.md")))

    def test_keeps_and_reports_a_file_removed_by_groundwork_that_the_project_changed(self):
        self.commit_project({"old.md": "old, adjusted\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("old.md", result.stdout)
        self.assertEqual(read(self.project, "old.md"), "old, adjusted\n")

    def test_keeps_and_reports_a_binary_file_changed_on_both_sides(self):
        self.commit_project({"logo.bin": "a\0d"})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("logo.bin", result.stdout)
        self.assertEqual(read(self.project, "logo.bin"), "a\0d")

    def test_updates_to_a_given_version(self):
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read(self.project, "SECURITY.md"), V1["SECURITY.md"])
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def test_leaves_out_the_files_of_groundwork_itself(self):
        self.run_script()
        self.assertEqual(read(self.project, "README.md"), V1["README.md"])
        self.assertEqual(read(self.project, "LICENSE"), V1["LICENSE"])

    def test_does_not_commit_nor_leave_the_branch_of_the_project(self):
        head = git(self.project, "rev-parse", "main").strip()
        self.run_script()
        self.assertEqual(git(self.project, "rev-parse", "HEAD").strip(), head)
        self.assertTrue(git(self.project, "status", "--porcelain").strip())

    def test_the_branch_passes_the_check_of_pull_requests(self):
        self.run_script()
        branch = git(self.project, "branch", "--show-current").strip()
        self.assertEqual(check_pull_request.check(branch, "main", "Closes #42"), [])

    def test_keeps_the_changes_of_the_project_that_do_not_conflict(self):
        self.commit_project({"CONTRIBUTING.md": "zero\none\ntwo\nthree\n"})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read(self.project, "CONTRIBUTING.md"), "zero\none\ntwo changed\nthree\n")

    def test_reports_the_files_in_conflict(self):
        self.commit_project({"CONTRIBUTING.md": "one\ntwo mine\nthree\n"})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("CONTRIBUTING.md", result.stdout)
        self.assertNotIn("new.md", result.stdout)
        self.assertIn("<<<<<<<", read(self.project, "CONTRIBUTING.md"))
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def test_accepts_a_project_already_ahead_of_its_recorded_version(self):
        self.commit_project({"new.md": "new\n", "CONTRIBUTING.md": V2["CONTRIBUTING.md"]})
        result = self.run_script("--to", "0.2.0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(read(self.project, ".groundwork-version"), "0.2.0\n")

    def test_does_nothing_when_the_project_is_up_to_date(self):
        self.commit_project({".groundwork-version": "0.3.0\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up to date", result.stdout)
        self.assertEqual(self.branches(), ["main"])

    def test_fails_without_the_version_file(self):
        os.remove(os.path.join(self.project, ".groundwork-version"))
        git(self.project, "commit", "-q", "-am", "chore: remove the version file")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn(".groundwork-version", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_fails_with_a_malformed_version_file(self):
        for content in ("v0.1.0\n", "0.1\n", "0.1.0\n0.2.0\n", "\n"):
            with self.subTest(content=content):
                self.commit_project({".groundwork-version": content})
                result = self.run_script()
                self.assertEqual(result.returncode, 1)
                self.assertIn("X.Y.Z", result.stderr)
                self.assertEqual(self.branches(), ["main"])

    def test_fails_with_an_unknown_recorded_version(self):
        self.commit_project({".groundwork-version": "0.9.9\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("0.9.9", result.stderr)

    def test_fails_when_the_target_is_not_a_later_version(self):
        for target in ("0.1.0", "0.0.9"):
            with self.subTest(target=target):
                result = self.run_script("--to", target)
                self.assertEqual(result.returncode, 1)
                self.assertIn("later", result.stderr)
                self.assertEqual(self.branches(), ["main"])

    def test_fails_with_an_unknown_target(self):
        result = self.run_script("--to", "7.0.0")
        self.assertEqual(result.returncode, 1)
        self.assertIn("7.0.0", result.stderr)

    def test_fails_when_the_working_tree_is_not_clean(self):
        write(self.project, {"SECURITY.md": "edited\n"})
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("clean", result.stderr)
        self.assertEqual(self.branches(), ["main"])

    def test_fails_when_the_branch_already_exists(self):
        git(self.project, "branch", "chore/42-update-groundwork-to-v0-3-0")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("chore/42-update-groundwork-to-v0-3-0", result.stderr)

    def test_fails_with_an_issue_that_is_not_a_number(self):
        result = self.run_script(issue="abc")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.branches(), ["main"])


if __name__ == "__main__":
    unittest.main()
