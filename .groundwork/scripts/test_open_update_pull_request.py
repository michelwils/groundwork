import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import open_update_pull_request as opener  # noqa: E402

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
    state = args[args.index("--state") + 1]
    print(os.environ.get("FAKE_PULL_REQUESTS" if state == "open" else "FAKE_CLOSED_PULL_REQUESTS", "[]"))
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

    def run_script(self, pull_requests="[]", closed="[]", recorded=None):
        """Run the script; with `recorded`, the project has recorded this address as its source and git reaches it at the source."""
        env = {
            **os.environ,
            "PATH": self.bin + os.pathsep + os.environ["PATH"],
            "FAKE_LOG": self.log,
            "FAKE_PULL_REQUESTS": pull_requests,
            "FAKE_CLOSED_PULL_REQUESTS": closed,
        }
        if recorded:
            env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.{self.source}.insteadOf", "GIT_CONFIG_VALUE_0": recorded})
        return subprocess.run(
            [sys.executable, SCRIPT, *([] if recorded else ["--source", self.source])], cwd=self.project, capture_output=True, text=True, env=env
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

    def test_the_pull_request_is_ready_and_named_after_the_version(self):
        self.run_script()
        (call,) = self.created()
        self.assertNotIn("--draft", call)
        self.assertEqual(self.value(call, "--title"), "chore: update groundwork to v0.2.0")
        self.assertEqual(self.value(call, "--head"), "groundwork/update-to-v0-2-0")
        self.assertIn("0.1.0", self.value(call, "--body"))
        self.assertIn("0.2.0", self.value(call, "--body"))

    def test_the_release_notes_are_those_of_the_source_that_the_project_recorded(self):
        write(self.project, {".groundwork-source": "https://example.org/team/base.git\n"})
        git(self.project, "add", "-A")
        git(self.project, "commit", "-q", "-m", "chore: record the source")
        git(self.project, "push", "-q", "origin", "main")
        result = self.run_script(recorded="https://example.org/team/base.git")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (call,) = self.created()
        self.assertIn("Release notes: https://example.org/team/base/releases/tag/v0.2.0", self.value(call, "--body"))

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
        calls = [call for call in self.gh_calls() if call[:2] == ["pr", "list"]]
        self.assertEqual({self.value(call, "--state") for call in calls}, {"open", "closed"})
        for call in calls:
            self.assertGreaterEqual(int(self.value(call, "--limit")), 1000)

    def test_does_not_propose_again_a_version_whose_pull_request_was_closed_without_a_merge(self):
        result = self.run_script(closed='[{"headRefName": "groundwork/update-to-v0-2-0", "mergedAt": null}]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("closed without being merged", result.stdout)
        self.assertEqual(self.created(), [])
        self.assertEqual(self.remote_branches(), ["main"])
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "main")
        self.assertEqual(git(self.project, "branch", "--format=%(refname:short)").split(), ["main"])
        self.assertEqual(git(self.project, "status", "--porcelain").strip(), "")

    def test_goes_back_to_a_detached_commit_when_the_version_was_rejected(self):
        head = git(self.project, "rev-parse", "HEAD").strip()
        git(self.project, "switch", "-q", "--detach")
        self.run_script(closed='[{"headRefName": "groundwork/update-to-v0-2-0", "mergedAt": null}]')
        self.assertEqual(git(self.project, "rev-parse", "HEAD").strip(), head)
        self.assertEqual(git(self.project, "branch", "--show-current").strip(), "")

    def test_a_version_rejected_earlier_does_not_prevent_a_later_one(self):
        self.run_script(closed='[{"headRefName": "groundwork/update-to-v0-1-5", "mergedAt": null}]')
        self.assertEqual(len(self.created()), 1)

    def test_a_merged_pull_request_does_not_count_as_rejected(self):
        self.run_script(closed='[{"headRefName": "groundwork/update-to-v0-2-0", "mergedAt": "2026-10-16T00:00:00Z"}]')
        self.assertEqual(len(self.created()), 1)

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


class Body(unittest.TestCase):
    def test_it_names_the_adrs_that_the_update_added(self):
        text = opener.body("0.1.0", "0.2.0", [], "https://github.com/o/g.git", ["0002", "0003"])
        self.assertIn("ADR 0002, ADR 0003", text)

    def test_it_says_nothing_of_the_adrs_when_none_was_added(self):
        text = opener.body("0.1.0", "0.2.0", [], "https://github.com/o/g.git", [])
        self.assertNotIn("ADR", text)
        self.assertEqual(text, opener.body("0.1.0", "0.2.0", [], "https://github.com/o/g.git"))

    def test_the_added_adrs_are_read_from_the_line_of_the_update(self):
        output = "branch: b\nfrom: 0.1.0\nto: 0.2.0\nadded: 0002, 0003\n"
        self.assertEqual(opener.added(output), ["0002", "0003"])
        self.assertEqual(opener.added("branch: b\n"), [])

    def test_a_line_that_looks_like_the_report_is_not_read_in_the_middle_of_a_line(self):
        self.assertEqual(opener.added("- file added: 0002\n"), [])

    def test_the_added_adrs_are_not_taken_for_conflicts(self):
        output = "branch: b\nfrom: 0.1.0\nto: 0.2.0\nadded: 0002\nResolve the conflicts in these files:\n- a.md\n"
        self.assertEqual(opener.conflicts(output), ["a.md"])


if __name__ == "__main__":
    unittest.main()
