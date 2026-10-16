import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import check_pull_request  # noqa: E402

SCRIPT = os.path.join(HERE, "open_update_pull_request.py")

V1 = {"README.md": "# groundwork\n", "CONTRIBUTING.md": "one\ntwo\nthree\n"}
V2 = {"README.md": "# groundwork 0.2\n", "CONTRIBUTING.md": "one\ntwo changed\nthree\n", "new.md": "new\n"}

# A stand-in for the `gh` command: it logs its arguments, lists the pull requests of FAKE_PULL_REQUESTS
# and answers the creation of a pull request with a URL.
FAKE_GH = """#!/usr/bin/env python3
import json, os, sys

args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if args[:2] == ["pr", "list"]:
    print(os.environ.get("FAKE_PULL_REQUESTS", "[]"))
elif args[:2] == ["pr", "create"]:
    print("https://github.com/owner/project/pull/1")
"""


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def init(path, bare=False):
    os.makedirs(path)
    git(path, "init", "-q", "-b", "main", *(["--bare"] if bare else []))
    if not bare:
        git(path, "config", "user.email", "test@example.com")
        git(path, "config", "user.name", "Test")
        git(path, "config", "commit.gpgsign", "false")
        git(path, "config", "tag.gpgsign", "false")
        git(path, "config", "core.hooksPath", os.devnull)


def write(path, files):
    for name, content in files.items():
        with open(os.path.join(path, name), "w") as handle:
            handle.write(content)


class OpenUpdatePullRequest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = self.directory.name
        self.source = os.path.join(root, "groundwork")
        init(self.source)
        for version, files in (("0.1.0", V1), ("0.2.0", V2)):
            write(self.source, files)
            git(self.source, "add", "-A")
            git(self.source, "commit", "-q", "-m", f"feat: release {version}")
            git(self.source, "tag", "-a", f"v{version}", "-m", f"v{version}")
        self.remote = os.path.join(root, "remote.git")
        init(self.remote, bare=True)
        self.project = os.path.join(root, "project")
        init(self.project)
        write(self.project, {**V1, ".groundwork-version": "0.1.0\n"})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "Initial commit")
        git(self.project, "remote", "add", "origin", self.remote)
        git(self.project, "push", "-q", "origin", "main")
        self.bin = os.path.join(root, "bin")
        os.makedirs(self.bin)
        gh = os.path.join(self.bin, "gh")
        with open(gh, "w") as handle:
            handle.write(FAKE_GH)
        os.chmod(gh, os.stat(gh).st_mode | stat.S_IEXEC)
        self.log = os.path.join(root, "log")

    def tearDown(self):
        self.directory.cleanup()

    def run_script(self, pull_requests="[]"):
        env = {
            **os.environ,
            "PATH": self.bin + os.pathsep + os.environ["PATH"],
            "FAKE_LOG": self.log,
            "FAKE_PULL_REQUESTS": pull_requests,
        }
        return subprocess.run(
            [sys.executable, SCRIPT, "--source", self.source], cwd=self.project, capture_output=True, text=True, env=env
        )

    def gh_calls(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as handle:
            return [json.loads(line) for line in handle]

    def created(self):
        return [call for call in self.gh_calls() if call[:2] == ["pr", "create"]]

    def remote_branches(self):
        return git(self.remote, "branch", "--format=%(refname:short)").split()

    def value(self, call, option):
        return call[call.index(option) + 1]

    def test_opens_a_pull_request_with_the_update(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("groundwork/update-to-v0-2-0", self.remote_branches())
        self.assertEqual(
            git(self.remote, "log", "-1", "--format=%s", "groundwork/update-to-v0-2-0").strip(),
            "chore: update groundwork to v0.2.0",
        )
        self.assertEqual(git(self.remote, "show", "groundwork/update-to-v0-2-0:.groundwork-version"), "0.2.0\n")
        self.assertIn("https://github.com/owner/project/pull/1", result.stdout)

    def test_the_pull_request_is_ready_and_follows_the_rules_of_pull_requests(self):
        self.run_script()
        (call,) = self.created()
        self.assertNotIn("--draft", call)
        self.assertEqual(self.value(call, "--title"), "chore: update groundwork to v0.2.0")
        self.assertEqual(self.value(call, "--head"), "groundwork/update-to-v0-2-0")
        self.assertEqual(check_pull_request.check(self.value(call, "--head"), "main", self.value(call, "--body")), [])
        self.assertIn("0.1.0", self.value(call, "--body"))
        self.assertIn("0.2.0", self.value(call, "--body"))

    def test_a_conflict_opens_a_draft_that_lists_the_files(self):
        write(self.project, {"CONTRIBUTING.md": "one\ntwo mine\nthree\n"})
        git(self.project, "commit", "-q", "-am", "docs: adjust the project")
        git(self.project, "push", "-q", "origin", "main")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        (call,) = self.created()
        self.assertIn("--draft", call)
        self.assertIn("CONTRIBUTING.md", self.value(call, "--body"))
        self.assertNotIn("new.md", self.value(call, "--body"))
        self.assertIn("groundwork/update-to-v0-2-0", self.remote_branches())

    def test_opens_nothing_when_the_project_is_up_to_date(self):
        write(self.project, {".groundwork-version": "0.2.0\n"})
        git(self.project, "commit", "-q", "-am", "chore: record the version")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("up to date", result.stdout)
        self.assertEqual(self.created(), [])
        self.assertEqual(self.remote_branches(), ["main"])

    def test_opens_no_second_pull_request_while_one_is_open(self):
        result = self.run_script('[{"headRefName": "groundwork/update-to-v0-2-0"}]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already open", result.stdout)
        self.assertEqual(self.created(), [])
        self.assertEqual(self.remote_branches(), ["main"])
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "main")

    def test_another_open_pull_request_does_not_prevent_the_update(self):
        self.run_script('[{"headRefName": "feat/3-add-a-thing"}, {"headRefName": "dependabot/pre_commit/x"}]')
        self.assertEqual(len(self.created()), 1)

    def test_looks_for_an_open_update_among_all_the_open_pull_requests(self):
        self.run_script()
        (call,) = [call for call in self.gh_calls() if call[:2] == ["pr", "list"]]
        self.assertGreaterEqual(int(self.value(call, "--limit")), 1000)

    def test_does_nothing_in_a_project_without_the_version_file(self):
        os.remove(os.path.join(self.project, ".groundwork-version"))
        git(self.project, "commit", "-q", "-am", "chore: remove the version file")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(".groundwork-version", result.stdout)
        self.assertEqual(self.created(), [])

    def test_fails_when_the_update_fails(self):
        write(self.project, {".groundwork-version": "0.9.9\n"})
        git(self.project, "commit", "-q", "-am", "chore: record a wrong version")
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("0.9.9", result.stderr)
        self.assertEqual(self.created(), [])
        self.assertEqual(self.remote_branches(), ["main"])

    def test_replaces_a_branch_left_by_an_earlier_run_that_has_no_pull_request(self):
        git(self.project, "switch", "-q", "-c", "groundwork/update-to-v0-2-0")
        write(self.project, {"stale.md": "stale\n"})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "chore: stale")
        git(self.project, "push", "-q", "origin", "groundwork/update-to-v0-2-0")
        git(self.project, "switch", "-q", "main")
        git(self.project, "branch", "-q", "-D", "groundwork/update-to-v0-2-0")
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            git(self.remote, "log", "-1", "--format=%s", "groundwork/update-to-v0-2-0").strip(),
            "chore: update groundwork to v0.2.0",
        )
        self.assertEqual(len(self.created()), 1)


if __name__ == "__main__":
    unittest.main()
